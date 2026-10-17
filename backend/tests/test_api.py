import asyncio
import io

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from rewind.config import ROOT, Settings
from rewind.main import create_app
from rewind.models import Analysis, Case, Event, validate_analysis


def settings(tmp_path, **kwargs):
    return Settings(_env_file=None, data_dir=tmp_path, **kwargs)


def jpeg():
    buffer = io.BytesIO()
    Image.new("RGB", (8, 8), "red").save(buffer, format="JPEG")
    return buffer.getvalue()


def test_upload_is_content_validated_and_path_safe(tmp_path):
    with TestClient(create_app(settings(tmp_path))) as client:
        response = client.post(
            "/api/cases",
            data={"title": "Inspection"},
            files=[("files", ("../../photo.jpg", jpeg(), "text/plain"))],
        )
        assert response.status_code == 201
        case = response.json()
        media = case["media_files"][0]
        assert media["filename"] == "photo.jpg"
        assert media["source_type"] == "photo"
        assert media["mime_type"] == "image/jpeg"
        assert len(media["sha256"]) == 64
        fetched = client.get(media["url"], headers={"Range": "bytes=0-9"})
        assert fetched.status_code == 206
        assert fetched.content == jpeg()[:10]
        assert fetched.headers["content-range"].startswith("bytes 0-9/")
        assert client.get(f"/api/cases/{case['case_id']}").json() == case


def test_reject_spoof_empty_corrupt_and_oversized_with_cleanup(tmp_path):
    app = create_app(settings(tmp_path, max_file_bytes=1000, max_request_bytes=10000))
    with TestClient(app) as client:
        for payload in (
            b"<script>alert(1)</script>",
            b"",
            b"\xff\xd8\xffgarbage",
            b"x" * 1001,
        ):
            response = client.post(
                "/api/cases", files=[("files", ("image.jpg", payload, "image/jpeg"))]
            )
            assert response.status_code in (413, 415)
        assert list((tmp_path / "media").iterdir()) == []
        assert len(client.get("/api/cases").json()) == 1  # synthetic fixture only
        assert client.post("/api/cases", content=b"x" * 10001).status_code == 413


def test_transaction_discards_earlier_valid_file(tmp_path):
    with TestClient(create_app(settings(tmp_path))) as client:
        response = client.post(
            "/api/cases",
            files=[("files", ("a.jpg", jpeg())), ("files", ("b.mp4", b"fake"))],
        )
        assert response.status_code == 415
        assert list((tmp_path / "media").iterdir()) == []


def test_job_completes_and_persists_analysis(tmp_path):
    async def analyze(case, paths, progress):
        await progress("analyzing_photos", 60)
        assert paths[case.media_files[0].source_id].exists()
        return Analysis(events=[], summary=[], mode="mock", notice="Simulated analysis")

    app = create_app(settings(tmp_path), analyze)
    with TestClient(app) as client:
        case = client.post("/api/cases", files=[("files", ("a.jpg", jpeg()))]).json()
        started = client.post(f"/api/cases/{case['case_id']}/analyze")
        assert started.status_code == 202

        async def wait_for_job():
            for _ in range(50):
                job = app.state.store.get_job(started.json()["job_id"])
                if job.status in ("completed", "failed"):
                    return job
                await asyncio.sleep(0.01)
            pytest.fail("Background job did not complete")

        job = client.portal.call(wait_for_job)
        assert job.status == "completed"
        assert (
            client.get(f"/api/cases/{case['case_id']}").json()["analysis"]["mode"]
            == "mock"
        )
    with TestClient(create_app(settings(tmp_path), analyze)) as client:
        assert (
            client.get(f"/api/cases/{case['case_id']}").json()["analysis"] is not None
        )


def test_failed_job_can_retry_without_leaking_exception(tmp_path):
    calls = 0

    async def analyze(case, paths, progress):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("secret-provider-token")
        return Analysis(events=[], summary=[], mode="mock")

    app = create_app(settings(tmp_path), analyze)
    with TestClient(app) as client:

        async def wait_for_job(job_id):
            for _ in range(100):
                job = app.state.store.get_job(job_id)
                if job.status in ("completed", "failed"):
                    return job
                await asyncio.sleep(0.01)
            pytest.fail("Background job did not finish")

        first = client.post("/api/cases/demo/analyze").json()
        failed = client.portal.call(wait_for_job, first["job_id"])
        assert failed.status == "failed"
        assert "secret" not in failed.error
        retry = client.post("/api/cases/demo/analyze").json()
        assert retry["job_id"] != first["job_id"]
        assert client.portal.call(wait_for_job, retry["job_id"]).status == "completed"


def test_fixture_and_reference_integrity():
    case = Case.model_validate_json((ROOT / "shared/sample_case.json").read_text())
    validate_analysis(case.analysis, case.media_files)
    broken = case.analysis.model_copy(deep=True)
    broken.events[0].source_id = "missing"
    with pytest.raises(ValueError, match="Unknown source"):
        validate_analysis(broken, case.media_files)
    broken = case.analysis.model_copy(deep=True)
    broken.contradictions[0].source_refs = broken.contradictions[0].source_refs[:1]
    with pytest.raises(ValueError, match="both conflicting"):
        validate_analysis(broken, case.media_files)
    broken = case.analysis.model_copy(deep=True)
    broken.events[0].source_end = 999
    with pytest.raises(ValueError, match="exceeds media duration"):
        validate_analysis(broken, case.media_files)
    event = case.analysis.events[0].model_dump()
    event["case_best"] = 4.25
    with pytest.raises(ValueError, match="source clock"):
        Event.model_validate(event)


def test_unknown_ids_return_actionable_404(tmp_path):
    with TestClient(create_app(settings(tmp_path))) as client:
        for url in ("/api/cases/missing", "/api/jobs/missing", "/api/media/missing"):
            assert client.get(url).status_code == 404
        assert client.post("/api/cases/missing/analyze").status_code == 404
