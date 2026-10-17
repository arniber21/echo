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
    altered = case.analysis.model_copy(deep=True)
    altered.events[0] = Event.model_validate(event)
    with pytest.raises(ValueError, match="source clock"):
        validate_analysis(altered, case.media_files)


def test_unknown_ids_return_actionable_404(tmp_path):
    with TestClient(create_app(settings(tmp_path))) as client:
        for url in ("/api/cases/missing", "/api/jobs/missing", "/api/media/missing"):
            assert client.get(url).status_code == 404
        assert client.post("/api/cases/missing/analyze").status_code == 404


def test_secondary_video_has_its_own_seek_clock():
    case = Case.model_validate_json((ROOT / "shared/sample_case.json").read_text())
    second = case.media_files[0].model_copy(
        update={"source_id": "secondary", "sha256": "zzzz"}
    )
    case.media_files.append(second)
    secondary_event = case.analysis.events[0].model_copy(
        update={
            "event_id": "second-view",
            "source_id": "secondary",
            "source_start": 2,
            "source_end": 3,
            "case_min": 7,
            "case_best": 8,
            "case_max": 9,
            "alignment_basis": "Contact matched to the primary video; estimated offset +6 seconds.",
        }
    )
    case.analysis.events.append(secondary_event)
    valid = validate_analysis(case.analysis, case.media_files)
    assert valid.events[-1].source_start == 2
    assert valid.events[-1].case_best == 8
    # Reordering uploads cannot change the primary clock.
    validate_analysis(case.analysis, list(reversed(case.media_files)))
    invalid = case.analysis.model_copy(deep=True)
    invalid.events[-1].case_min = -1
    with pytest.raises(ValueError, match="nonnegative"):
        validate_analysis(invalid, case.media_files)


def test_photo_exif_requires_explicit_timezone(tmp_path):
    from rewind.uploads import captured_at

    for offset in (None, "+02:00", "invalid"):
        exif = Image.Exif()
        values = {0x9003: "2026:10:17 12:34:56"}
        if offset:
            values[0x9011] = offset
        exif[0x8769] = values
        path = tmp_path / f"photo-{offset}.jpg"
        Image.new("RGB", (8, 8), "blue").save(path, exif=exif)
        result = captured_at(path)
        if offset == "+02:00":
            assert result.isoformat() == "2026-10-17T12:34:56+02:00"
        else:
            assert result is None


def test_audio_detected_from_bytes_instead_of_filename(tmp_path):
    import shutil
    import wave

    if shutil.which("ffprobe") is None:
        pytest.skip("ffprobe is supplied by the devbox environment")
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(8000)
        audio.writeframes(b"\x00\x00" * 800)
    with TestClient(create_app(settings(tmp_path))) as client:
        response = client.post(
            "/api/cases",
            files=[("files", ("pretend-photo.jpg", buffer.getvalue(), "image/jpeg"))],
        )
        assert response.status_code == 201
        source = response.json()["media_files"][0]
        assert source["source_type"] == "audio"
        assert source["mime_type"] == "audio/wav"
        assert source["duration_seconds"] == pytest.approx(0.1)


@pytest.mark.parametrize(
    ("configured_mode", "requested_mode", "expected_mode"),
    [
        ("mock", "auto", "mock"),
        ("mock", "live", "mock"),
        ("auto", "mock", "mock"),
        ("live", "auto", "live"),
        ("auto", "live", "live"),
    ],
)
def test_operator_mock_mode_prevents_live_requests(
    tmp_path, monkeypatch, configured_mode, requested_mode, expected_mode
):
    received_modes = []

    async def capture_analysis(case, paths, progress, *, settings):
        assert settings.api_key == "configured-test-key"
        received_modes.append(settings.mode)
        return Analysis(events=[], summary=[], mode="mock")

    monkeypatch.setattr("rewind.analysis.analyze", capture_analysis)
    app = create_app(settings(
        tmp_path, analysis_mode=configured_mode, gemini_api_key="configured-test-key"
    ))
    with TestClient(app) as client:
        started = client.post("/api/cases/demo/analyze", json={"mode": requested_mode})
        assert started.status_code == 202

        async def wait_for_job():
            for _ in range(100):
                job = app.state.store.get_job(started.json()["job_id"])
                if job.status in ("completed", "failed"):
                    return job
                await asyncio.sleep(0.01)
            pytest.fail("Background job did not finish")

        assert client.portal.call(wait_for_job).status == "completed"
    assert received_modes == [expected_mode]
