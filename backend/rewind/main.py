"""Local HTTP API. Storage, ingestion and analysis stay behind explicit boundaries."""

import asyncio
import hashlib
import logging
import shutil
from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated
from uuid import uuid4

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from rewind.config import ROOT, Settings
from rewind.models import Analysis, AnalyzeRequest, Case, Job, validate_analysis
from rewind.storage import Store
from rewind.uploads import ingest

logger = logging.getLogger(__name__)
Progress = Callable[[str, int], Awaitable[None]]
Analyzer = Callable[[Case, dict[str, Path], Progress], Awaitable[Analysis]]


class UploadLimit:
    def __init__(self, app: ASGIApp, limit: int):
        self.app, self.limit = app, limit

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        headers = dict(scope.get("headers", []))
        try:
            declared = int(headers.get(b"content-length", b"0"))
        except ValueError:
            declared = self.limit + 1
        if declared > self.limit:
            from starlette.responses import JSONResponse

            return await JSONResponse(
                {"detail": "Upload exceeds the total request limit."}, status_code=413
            )(scope, receive, send)
        total = 0

        async def bounded_receive():
            nonlocal total
            message = await receive()
            total += len(message.get("body", b""))
            if total > self.limit:
                raise HTTPException(413, "Upload exceeds the total request limit.")
            return message

        await self.app(scope, bounded_receive, send)


def seed_demo(store: Store):
    fixture = ROOT / "shared/sample_case.json"
    if not fixture.exists():
        return
    case = Case.model_validate_json(fixture.read_text())
    paths = {}
    for media in case.media_files:
        path = ROOT / "demo/media" / media.filename
        if path.is_file():
            media.size_bytes = path.stat().st_size
            media.sha256 = hashlib.sha256(path.read_bytes()).hexdigest()
            paths[media.source_id] = path
    validate_analysis(case.analysis, case.media_files)
    store.save_case(case, paths)


def create_app(
    settings: Settings | None = None, analyzer: Analyzer | None = None
) -> FastAPI:
    config = settings or Settings()
    store = Store(config.data_dir)
    seed_demo(store)
    tasks: set[asyncio.Task] = set()
    analysis_lock = asyncio.Lock()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        yield
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

    app = FastAPI(title="Rewind API", version="0.1.0", lifespan=lifespan)
    app.add_middleware(UploadLimit, limit=config.max_request_bytes)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type", "Range"],
    )
    app.state.store = store

    def require_case(case_id: str) -> Case:
        case = store.get_case(case_id)
        if case is None:
            raise HTTPException(404, "Case not found.")
        return case

    @app.get("/api/health")
    async def health():
        return {
            "status": "ok",
            "analysis_mode": config.analysis_mode,
            "provider_configured": bool(config.gemini_api_key),
        }

    @app.get("/api/cases", response_model=list[Case])
    async def cases():
        return store.list_cases()

    @app.get("/api/cases/{case_id}", response_model=Case)
    async def get_case(case_id: str):
        return require_case(case_id)

    @app.post("/api/cases", response_model=Case, status_code=201)
    async def upload_case(
        files: Annotated[list[UploadFile], File()],
        title: Annotated[str, Form(max_length=160)] = "Untitled reconstruction",
    ):
        if not files or len(files) > config.max_files:
            raise HTTPException(422, f"Upload between 1 and {config.max_files} files.")
        case_id = uuid4().hex
        directory = config.data_dir / "media" / case_id
        directory.mkdir(parents=True)
        media, paths = [], {}
        total = 0
        try:
            for file in files:
                item, path = await ingest(file, directory, config)
                total += item.size_bytes
                if total > config.max_request_bytes:
                    raise HTTPException(413, "Upload exceeds the total request limit.")
                media.append(item)
                paths[item.source_id] = path
            case = Case(
                case_id=case_id,
                title=title.strip() or "Untitled reconstruction",
                created_at=datetime.now(UTC),
                media_files=media,
            )
            store.save_case(case, paths)
            return case
        except BaseException:
            shutil.rmtree(directory, ignore_errors=True)
            raise
        finally:
            for file in files:
                await file.close()

    async def run_analysis(job: Job, case: Case, mode: str):
        async def progress(stage: str, percent: int):
            # Validate service progress before writing it to persistent state.
            updated = Job(
                job_id=job.job_id,
                case_id=case.case_id,
                status="running",
                stage=stage,
                progress=percent,
            )
            store.save_job(updated)

        try:
            async with analysis_lock:
                await progress("uploading", 5)
                if analyzer:
                    analysis = await analyzer(case, store.paths(case.case_id), progress)
                else:
                    from rewind.analysis import AnalysisSettings, analyze

                    analysis = await analyze(
                        case,
                        store.paths(case.case_id),
                        progress,
                        settings=AnalysisSettings(
                            api_key=config.gemini_api_key.get_secret_value()
                            if config.gemini_api_key
                            else None,
                            model=config.gemini_model,
                            mode=mode,
                            cache_dir=config.data_dir / "cache",
                        ),
                    )
                validate_analysis(analysis, case.media_files)
                case.analysis = analysis
                store.save_case(case)
                store.save_job(
                    job.model_copy(
                        update={
                            "status": "completed",
                            "stage": "completed",
                            "progress": 100,
                        }
                    )
                )
        except asyncio.CancelledError:
            store.save_job(
                job.model_copy(
                    update={
                        "status": "failed",
                        "stage": "failed",
                        "error": "Analysis interrupted. Retry analysis.",
                    }
                )
            )
            raise
        except Exception:  # noqa: BLE001 - job boundary isolates provider failures
            # Provider exceptions can contain request headers or source paths. Keep them out of API responses.
            logger.error("Analysis failed for job %s", job.job_id)
            store.save_job(
                job.model_copy(
                    update={
                        "status": "failed",
                        "stage": "failed",
                        "error": "Analysis could not be completed. Check provider configuration and retry, or open the synthetic demo.",
                    }
                )
            )

    @app.post("/api/cases/{case_id}/analyze", response_model=Job, status_code=202)
    async def start_analysis(case_id: str, request: AnalyzeRequest | None = None):
        case = require_case(case_id)
        existing = store.active_job(case_id)
        if existing:
            return existing
        job = Job(
            job_id=uuid4().hex,
            case_id=case_id,
            status="queued",
            stage="uploading",
            progress=0,
        )
        store.save_job(job)
        task = asyncio.create_task(
            run_analysis(job, case, request.mode if request else config.analysis_mode)
        )
        tasks.add(task)
        task.add_done_callback(tasks.discard)
        return job

    @app.get("/api/jobs/{job_id}", response_model=Job)
    async def get_job(job_id: str):
        job = store.get_job(job_id)
        if job is None:
            raise HTTPException(404, "Analysis job not found.")
        return job

    @app.get("/api/media/{source_id}")
    async def get_media(source_id: str):
        result = store.media(source_id)
        if result is None or result[0] is None or not result[1].is_file():
            raise HTTPException(404, "Media not found.")
        media, path = result
        return FileResponse(
            path,
            media_type=media.mime_type,
            filename=media.filename,
            content_disposition_type="inline",
            headers={"X-Content-Type-Options": "nosniff"},
        )

    return app


app = create_app()
