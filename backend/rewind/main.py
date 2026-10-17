"""Local HTTP API. Storage, ingestion and analysis stay behind explicit boundaries."""

import asyncio
import hashlib
import json
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

from rewind.analysis.errors import classify_failure
from rewind.config import ROOT, Settings
from rewind.memory import project_memory
from rewind.models import (
    Analysis,
    AnalysisRevision,
    AnalyzeRequest,
    Case,
    Job,
    SourceMetadata,
    validate_analysis,
)
from rewind.storage import Store
from rewind.uploads import ingest_batch

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
    case.analyzed_revision = case.evidence_revision
    case.analyzed_at = case.created_at
    case.analyzed_source_ids = [item.source_id for item in case.media_files]
    case.analyzed_media_files = [
        item.model_copy(deep=True) for item in case.media_files
    ]
    if case.analysis is not None:
        case.memory = project_memory(
            None, case.analysis, case.evidence_revision, case.created_at
        )
    paths = {}
    for media in case.media_files:
        path = ROOT / "demo/media" / media.filename
        if path.is_file():
            media.size_bytes = path.stat().st_size
            media.sha256 = hashlib.sha256(path.read_bytes()).hexdigest()
            paths[media.source_id] = path
    validate_analysis(case.analysis, case.media_files)
    case.analyzed_media_files = [
        item.model_copy(deep=True) for item in case.media_files
    ]
    store.save_case(case, paths)


def create_app(
    settings: Settings | None = None, analyzer: Analyzer | None = None
) -> FastAPI:
    config = settings or Settings()
    store = Store(config.data_dir)
    if config.seed_demo:
        seed_demo(store)
    tasks: set[asyncio.Task] = set()
    analysis_lock = asyncio.Lock()
    case_locks: dict[str, asyncio.Lock] = {}

    def case_lock(case_id: str) -> asyncio.Lock:
        return case_locks.setdefault(case_id, asyncio.Lock())

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
        allow_methods=["GET", "POST", "PATCH"],
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
        items = store.list_cases()
        default_id = workspace_case_id()
        return [
            case for case in items if default_id == "demo" or case.case_id != "demo"
        ]

    def workspace_case_id() -> str | None:
        """A local preference selects the real case opened on the workspace home."""
        try:
            value = json.loads((config.data_dir / "workspace.json").read_text())
            case_id = value.get("case_id")
            if isinstance(case_id, str) and store.get_case(case_id) is not None:
                return case_id
        except (OSError, ValueError, TypeError, AttributeError):
            pass
        candidates = store.list_cases()
        return next(
            (case.case_id for case in candidates if case.case_id != "demo"),
            "demo" if store.get_case("demo") is not None else None,
        )

    @app.get("/api/workspace", response_model=Case | None)
    async def workspace():
        case_id = workspace_case_id()
        return require_case(case_id) if case_id else None

    @app.get("/api/cases/{case_id}", response_model=Case)
    async def get_case(case_id: str):
        return require_case(case_id)

    @app.post("/api/cases", response_model=Case, status_code=201)
    async def upload_case(
        files: Annotated[list[UploadFile], File()],
        title: Annotated[str, Form(max_length=160)] = "Untitled reconstruction",
        metadata: Annotated[str | None, Form(max_length=512000)] = None,
    ):
        case_id = uuid4().hex
        directory = config.data_dir / "media" / case_id
        media, paths = await ingest_batch(files, directory, config, metadata)
        try:
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

    @app.post("/api/cases/{case_id}/media", response_model=Case)
    async def append_media(
        case_id: str,
        files: Annotated[list[UploadFile], File()],
        metadata: Annotated[str | None, Form(max_length=512000)] = None,
    ):
        require_case(case_id)
        async with case_lock(case_id):
            try:
                if case_id == "demo":
                    raise HTTPException(
                        409,
                        "The synthetic demo is read-only. Start a new reconstruction to add evidence.",
                    )
                if store.active_job(case_id):
                    raise HTTPException(
                        409,
                        "Analysis is running. Wait for it to finish before adding evidence.",
                    )
                directory = config.data_dir / "media" / case_id / uuid4().hex
                media, paths = await ingest_batch(files, directory, config, metadata)
                try:
                    case = require_case(case_id)
                    preserve_analyzed_media(case)
                    case.media_files.extend(media)
                    case.evidence_revision += 1
                    store.save_case(case, paths)
                    return case
                except BaseException:
                    shutil.rmtree(directory, ignore_errors=True)
                    raise
            finally:
                for file in files:
                    await file.close()

    def preserve_analyzed_media(case: Case) -> None:
        """Backfill legacy snapshots before a user can replace their annotations."""
        if case.analysis is not None and not case.analyzed_media_files:
            analyzed_ids = set(case.analyzed_source_ids)
            case.analyzed_media_files = [
                item.model_copy(deep=True)
                for item in case.media_files
                if not analyzed_ids or item.source_id in analyzed_ids
            ]

    @app.patch("/api/cases/{case_id}/media/{source_id}", response_model=Case)
    async def update_source_metadata(
        case_id: str, source_id: str, metadata: SourceMetadata
    ):
        require_case(case_id)
        async with case_lock(case_id):
            case = require_case(case_id)
            media = next(
                (item for item in case.media_files if item.source_id == source_id), None
            )
            if media is None:
                raise HTTPException(404, "Evidence source not found in this case.")
            if case_id == "demo":
                raise HTTPException(
                    409,
                    "The synthetic demo is read-only. Start a new reconstruction to annotate evidence.",
                )
            if store.active_job(case_id):
                raise HTTPException(
                    409,
                    "Analysis is running. Wait for it to finish before editing evidence.",
                )
            if media.metadata == metadata:
                return case
            preserve_analyzed_media(case)
            media.metadata = metadata
            case.evidence_revision += 1
            store.save_case(case)
            return case

    async def run_analysis(job: Job, case: Case, mode: str):
        current_job = job

        async def progress(stage: str, percent: int):
            nonlocal current_job
            # Validate service progress before writing it to persistent state.
            updated = Job(
                job_id=job.job_id,
                case_id=case.case_id,
                status="running",
                stage=stage,
                progress=percent,
            )
            store.save_job(updated)
            current_job = updated

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
                async with case_lock(case.case_id):
                    current = require_case(case.case_id)
                    if current.evidence_revision != case.evidence_revision:
                        raise ValueError(
                            "Evidence changed during analysis; retry on the latest revision"
                        )
                    preserve_analyzed_media(current)
                    if (
                        current.analysis is not None
                        and current.analyzed_revision is not None
                        and current.analyzed_revision != current.evidence_revision
                        and not any(
                            snapshot.revision == current.analyzed_revision
                            for snapshot in current.analysis_history
                        )
                    ):
                        current.analysis_history.append(
                            AnalysisRevision(
                                revision=current.analyzed_revision,
                                created_at=current.analyzed_at or current.created_at,
                                media_count=len(current.analyzed_source_ids),
                                media_source_ids=current.analyzed_source_ids.copy(),
                                media_files=[
                                    item.model_copy(deep=True)
                                    for item in current.analyzed_media_files
                                ],
                                analysis=current.analysis,
                            )
                        )
                    current.analysis = analysis
                    current.analyzed_revision = current.evidence_revision
                    current.analyzed_at = datetime.now(UTC)
                    current.memory = project_memory(
                        current.memory,
                        analysis,
                        current.evidence_revision,
                        current.analyzed_at,
                    )
                    current.analyzed_source_ids = [
                        item.source_id for item in current.media_files
                    ]
                    current.analyzed_media_files = [
                        item.model_copy(deep=True) for item in current.media_files
                    ]
                    store.save_case(current)
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
                current_job.model_copy(
                    update={
                        "status": "failed",
                        "stage": "failed",
                        "error": f"Analysis interrupted during {current_job.stage}. Retry analysis. Reference: {job.job_id}.",
                    }
                )
            )
            raise
        except Exception as error:  # noqa: BLE001 - job boundary isolates provider failures
            failure = classify_failure(error)
            # Deliberately omit exception text, traceback, headers and model output.
            logger.error(
                "Analysis failed job=%s stage=%s progress=%s code=%s validation=%s",
                job.job_id,
                current_job.stage,
                current_job.progress,
                failure.code,
                failure.validation or "none",
            )
            store.save_job(
                current_job.model_copy(
                    update={
                        "status": "failed",
                        "stage": "failed",
                        "error": f"{failure.message} Stage: {current_job.stage}. Reference: {job.job_id}.",
                    }
                )
            )

    @app.post("/api/cases/{case_id}/analyze", response_model=Job, status_code=202)
    async def start_analysis(case_id: str, request: AnalyzeRequest | None = None):
        require_case(case_id)
        async with case_lock(case_id):
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
            requested_mode = request.mode if request else "auto"
            # An operator-forced offline session must never transfer evidence to Gemini.
            effective_mode = requested_mode
            if config.analysis_mode == "mock":
                effective_mode = "mock"
            elif requested_mode == "auto":
                effective_mode = config.analysis_mode
            task = asyncio.create_task(run_analysis(job, case, effective_mode))
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
