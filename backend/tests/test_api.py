import asyncio
import io
import json
import os
import subprocess
import sys

import httpx
import pytest
from fastapi.testclient import TestClient
from google.genai.errors import APIError
from PIL import Image
from rewind.analysis.provider import InvalidModelOutput
from rewind.config import ROOT, Settings
from rewind.main import create_app
from rewind.models import Analysis, Case, Event, validate_analysis


def settings(tmp_path, **kwargs):
    return Settings(
        _env_file=None,
        data_dir=tmp_path,
        seed_demo=kwargs.pop("seed_demo", True),
        **kwargs,
    )


def jpeg():
    buffer = io.BytesIO()
    Image.new("RGB", (8, 8), "red").save(buffer, format="JPEG")
    return buffer.getvalue()


def test_import_does_not_initialize_storage_or_interrupt_other_jobs(tmp_path):
    target = tmp_path / "must-not-be-created"
    subprocess.run(
        [sys.executable, "-c", "import rewind.main"],
        env={**os.environ, "DATA_DIR": str(target)},
        cwd=ROOT,
        check=True,
    )
    assert not target.exists()


def test_workspace_opens_selected_real_case_and_keeps_fixture_out_of_case_picker(
    tmp_path,
):
    with TestClient(create_app(settings(tmp_path))) as client:
        assert client.get("/api/workspace").json()["case_id"] == "demo"
        created = client.post(
            "/api/cases", files=[("files", ("evidence.jpg", jpeg()))]
        ).json()
        (tmp_path / "workspace.json").write_text(
            json.dumps({"case_id": created["case_id"]})
        )
        assert client.get("/api/workspace").json()["case_id"] == created["case_id"]
        assert [case["case_id"] for case in client.get("/api/cases").json()] == [
            created["case_id"]
        ]
        assert (
            client.get("/api/cases/demo").status_code == 200
        )  # Explicit test-fixture access.
        (tmp_path / "workspace.json").write_text('{"case_id":"missing-case"}')
        assert client.get("/api/workspace").json()["case_id"] == created["case_id"]


def test_normal_workspace_starts_blank_and_remains_blank_after_restart(tmp_path):
    for _ in range(2):
        with TestClient(create_app(settings(tmp_path, seed_demo=False))) as client:
            assert client.get("/api/cases").json() == []
            assert client.get("/api/workspace").status_code == 200
            assert client.get("/api/workspace").json() is None
            assert client.get("/api/cases/demo").status_code == 404


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


@pytest.mark.parametrize(
    ("failure", "expected_code", "expected_message"),
    [
        (
            RuntimeError("secret-provider-token"),
            "analysis_failed",
            "could not be completed",
        ),
        (TimeoutError("secret-provider-token"), "timeout", "timed out"),
        (
            InvalidModelOutput("secret-provider-token"),
            "invalid_model_output",
            "failed validation",
        ),
        (
            APIError(401, {"message": "secret-provider-token"}),
            "provider_authentication",
            "rejected access",
        ),
        (
            APIError(403, {"message": "secret-provider-token"}),
            "provider_authentication",
            "rejected access",
        ),
        (
            APIError(404, {"message": "secret-provider-token"}),
            "provider_model_unavailable",
            "model is unavailable",
        ),
        (
            APIError(429, {"message": "secret-provider-token"}),
            "provider_rate_limit",
            "rate or quota limit",
        ),
        (
            APIError(503, {"message": "secret-provider-token"}),
            "provider_unavailable",
            "temporarily unavailable",
        ),
        (
            httpx.HTTPStatusError(
                "secret-provider-token",
                request=httpx.Request("POST", "https://secret-provider-token.test"),
                response=httpx.Response(429),
            ),
            "provider_rate_limit",
            "rate or quota limit",
        ),
        (
            InvalidModelOutput(
                "Gemini returned invalid evidence data after one retry: Extraction exceeds source duration"
            ),
            "invalid_model_output",
            "failed validation",
        ),
    ],
)
def test_failed_job_can_retry_without_leaking_exception(
    tmp_path, caplog, failure, expected_code, expected_message
):
    calls = 0

    async def analyze(case, paths, progress):
        nonlocal calls
        calls += 1
        if calls == 1:
            await progress("synthesizing", 80)
            raise failure
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
        assert failed.stage == "failed"
        assert failed.progress == 80
        assert "secret" not in failed.error
        assert expected_message in failed.error
        assert "synthesizing" in failed.error
        assert first["job_id"] in failed.error
        assert "synthetic" not in failed.error
        assert "secret" not in caplog.text
        assert f"code={expected_code}" in caplog.text
        assert "stage=synthesizing progress=80" in caplog.text
        if isinstance(failure, InvalidModelOutput):
            assert "validation=" in caplog.text
            if "Extraction exceeds source duration" in str(failure):
                assert "validation=Extraction exceeds source duration" in caplog.text
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

    async def capture_analysis(
        case, paths, progress, *, settings, intelligence_sink=None
    ):
        assert settings.api_key == "configured-test-key"
        received_modes.append(settings.mode)
        return Analysis(events=[], summary=[], mode="mock")

    monkeypatch.setattr("rewind.analysis.analyze", capture_analysis)
    app = create_app(
        settings(
            tmp_path,
            analysis_mode=configured_mode,
            gemini_api_key="configured-test-key",
        )
    )
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


def finish_job(client, app, case_id):
    job = client.post(f"/api/cases/{case_id}/analyze", json={"mode": "mock"}).json()

    async def wait():
        for _ in range(100):
            current = app.state.store.get_job(job["job_id"])
            if current.status in ("failed", "completed"):
                return current
            await asyncio.sleep(0.01)
        pytest.fail("Analysis did not finish")

    completed = client.portal.call(wait)
    assert completed.status == "completed", completed.error
    return client.get(f"/api/cases/{case_id}").json()


def test_incremental_video_then_photo_preserves_history_and_restart(
    tmp_path, monkeypatch
):
    import shutil
    import subprocess

    if shutil.which("ffmpeg") is None:
        pytest.skip("FFmpeg is supplied by devbox")
    video = tmp_path / "initial.mp4"
    subprocess.run(
        [
            "ffmpeg",
            "-loglevel",
            "error",
            "-f",
            "lavfi",
            "-i",
            "color=black:size=64x64:rate=5",
            "-t",
            "2",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            str(video),
        ],
        check=True,
        timeout=20,
    )
    config = settings(tmp_path / "data", analysis_mode="mock")
    app = create_app(config)
    from rewind.main import project_memory

    memory_updates = []

    def record_memory(*args):
        memory_updates.append(args[2])
        return project_memory(*args)

    monkeypatch.setattr("rewind.main.project_memory", record_memory)
    with TestClient(app) as client:
        initial = client.post(
            "/api/cases", files=[("files", ("initial.mp4", video.read_bytes()))]
        ).json()
        case_id = initial["case_id"]
        first = finish_job(client, app, case_id)
        assert first["evidence_revision"] == first["analyzed_revision"] == 1
        assert len(first["analysis"]["events"]) == 1
        original_ids = first["analyzed_source_ids"]
        assert first["memory"]["revision"] == 1
        initial_memory = first["memory"]
        for _ in range(3):
            assert (
                client.get(f"/api/cases/{case_id}").json()["memory"] == initial_memory
            )
        appended = client.post(
            f"/api/cases/{case_id}/media",
            files=[("files", ("later-photo.jpg", jpeg()))],
        )
        assert appended.status_code == 200
        stale = appended.json()
        assert stale["evidence_revision"] == 2
        assert stale["analyzed_revision"] == 1
        assert stale["analysis"] == first["analysis"]
        assert stale["analyzed_source_ids"] == original_ids
        assert stale["analysis_history"] == []
        assert stale["memory"] == initial_memory
        assert memory_updates == [1]  # Reads and uploads never regenerate recollection.
        second = finish_job(client, app, case_id)
        assert second["analyzed_revision"] == 2
        assert len(second["analysis"]["events"]) == 2
        assert len(second["analyzed_source_ids"]) == 2
        assert second["memory"]["revision"] == 2
        assert memory_updates == [1, 2]
        prior_inference = next(
            entry for entry in initial_memory["entries"] if entry["kind"] == "inference"
        )
        remembered = next(
            entry
            for entry in second["memory"]["entries"]
            if entry["entry_id"] == prior_inference["entry_id"]
        )
        assert remembered["first_revision"] == 1
        assert remembered["last_revision"] == 2
        assert remembered["status"] == "active"
        assert any(
            entry["status"] == "superseded" for entry in second["memory"]["entries"]
        )
        snapshot = second["analysis_history"][0]
        assert snapshot["revision"] == 1
        assert snapshot["media_count"] == 1
        assert snapshot["media_source_ids"] == original_ids
        assert snapshot["analysis"] == first["analysis"]
        assert snapshot["created_at"] == first["analyzed_at"]
        repeated = finish_job(client, app, case_id)
        assert repeated["analysis_history"] == second["analysis_history"]
    with TestClient(create_app(config)) as client:
        restored = client.get(f"/api/cases/{case_id}").json()
        assert restored == repeated
        for media in restored["media_files"]:
            assert client.get(media["url"]).status_code == 200


def test_failed_append_rolls_back_only_new_batch(tmp_path):
    with TestClient(create_app(settings(tmp_path))) as client:
        first = client.post(
            "/api/cases", files=[("files", ("original.jpg", jpeg()))]
        ).json()
        case_id = first["case_id"]
        response = client.post(
            f"/api/cases/{case_id}/media",
            files=[("files", ("new.jpg", jpeg())), ("files", ("fake.mp4", b"invalid"))],
        )
        assert response.status_code == 415
        assert client.get(f"/api/cases/{case_id}").json() == first
        assert client.get(first["media_files"][0]["url"]).content == jpeg()
        directory = tmp_path / "media" / case_id
        assert len(list(directory.iterdir())) == 1


def test_append_rejected_while_job_active_and_demo_is_readonly(tmp_path):
    from threading import Event as ThreadEvent

    entered, release = ThreadEvent(), ThreadEvent()

    async def analyze(case, paths, progress):
        entered.set()
        while not release.is_set():
            await asyncio.sleep(0.01)
        return Analysis(events=[], summary=[], mode="mock")

    app = create_app(settings(tmp_path), analyze)
    with TestClient(app) as client:
        case = client.post("/api/cases", files=[("files", ("a.jpg", jpeg()))]).json()
        client.post(f"/api/cases/{case['case_id']}/analyze")
        assert entered.wait(timeout=2)
        response = client.post(
            f"/api/cases/{case['case_id']}/media", files=[("files", ("b.jpg", jpeg()))]
        )
        assert response.status_code == 409
        assert client.get(f"/api/cases/{case['case_id']}").json() == case
        release.set()
        assert (
            client.post(
                "/api/cases/demo/media", files=[("files", ("a.jpg", jpeg()))]
            ).status_code
            == 409
        )
        demo = client.get("/api/cases/demo").json()
        assert demo["analyzed_revision"] == demo["evidence_revision"] == 1
        assert len(demo["analyzed_source_ids"]) == len(demo["media_files"])


def test_concurrent_appends_do_not_lose_evidence(tmp_path):
    from concurrent.futures import ThreadPoolExecutor

    with TestClient(create_app(settings(tmp_path))) as client:
        case = client.post(
            "/api/cases", files=[("files", ("original.jpg", jpeg()))]
        ).json()
        case_id = case["case_id"]

        def append(index):
            return client.post(
                f"/api/cases/{case_id}/media",
                files=[("files", (f"photo-{index}.jpg", jpeg()))],
            )

        with ThreadPoolExecutor(max_workers=2) as pool:
            responses = list(pool.map(append, range(2)))
        assert all(response.status_code == 200 for response in responses)
        combined = client.get(f"/api/cases/{case_id}").json()
        assert combined["evidence_revision"] == 3
        assert len(combined["media_files"]) == 3
        assert {item["filename"] for item in combined["media_files"]} == {
            "original.jpg",
            "photo-0.jpg",
            "photo-1.jpg",
        }


def test_create_and_append_accept_ordered_source_annotations(tmp_path):
    annotation = {
        "label": "Northbound dashcam",
        "recorded_by": "Alex",
        "location": "Oak and First",
        "recorded_at": "Around 9 pm, yesterday",
        "notes": "User recollection; timestamp uncertain.",
    }
    with TestClient(create_app(settings(tmp_path))) as client:
        response = client.post(
            "/api/cases",
            data={"metadata": json.dumps([annotation, {"label": "Second view"}])},
            files=[("files", ("first.jpg", jpeg())), ("files", ("second.jpg", jpeg()))],
        )
        assert response.status_code == 201
        case = response.json()
        first, second = case["media_files"]
        assert first["metadata"] == annotation
        assert second["metadata"]["label"] == "Second view"
        assert second["metadata"]["recorded_by"] == ""
        assert first["captured_at"] is None  # Reported time never becomes EXIF time.
        appended = client.post(
            f"/api/cases/{case['case_id']}/media",
            data={"metadata": json.dumps([{"label": "Later evidence"}])},
            files=[("files", ("third.jpg", jpeg()))],
        )
        assert appended.status_code == 200
        assert (
            appended.json()["media_files"][-1]["metadata"]["label"] == "Later evidence"
        )
        assert appended.json()["media_files"][0] == first


@pytest.mark.parametrize(
    "metadata",
    [
        "not-json",
        "{}",
        "[]",
        '[{"unexpected":"value"}]',
        json.dumps([{"notes": "x" * 4001}]),
        json.dumps([{"label": 123}]),
    ],
)
def test_invalid_metadata_rejected_before_writing(tmp_path, metadata):
    with TestClient(create_app(settings(tmp_path))) as client:
        initial = client.post(
            "/api/cases",
            data={"metadata": metadata},
            files=[("files", ("initial.jpg", jpeg()))],
        )
        assert initial.status_code == 422
        assert "metadata" in initial.json()["detail"].lower()
        assert not (tmp_path / "media").exists()
        case = client.post(
            "/api/cases", files=[("files", ("original.jpg", jpeg()))]
        ).json()
        response = client.post(
            f"/api/cases/{case['case_id']}/media",
            data={"metadata": metadata},
            files=[("files", ("new.jpg", jpeg()))],
        )
        assert response.status_code == 422
        assert client.get(f"/api/cases/{case['case_id']}").json() == case
        assert len(list((tmp_path / "media" / case["case_id"]).iterdir())) == 1


def test_annotation_edit_retains_analysis_memory_and_exact_snapshot(tmp_path):
    app = create_app(settings(tmp_path, analysis_mode="mock"))
    original_metadata = {
        "label": "Original label",
        "recorded_by": "Original reporter",
        "location": "Original corner",
        "recorded_at": "Uncertain",
        "notes": "Original note",
    }
    with TestClient(app) as client:
        initial = client.post(
            "/api/cases",
            data={"metadata": json.dumps([original_metadata])},
            files=[("files", ("evidence.jpg", jpeg()))],
        ).json()
        case_id = initial["case_id"]
        first = finish_job(client, app, case_id)
        source = first["media_files"][0]
        revised_metadata = {
            **original_metadata,
            "label": "Revised label",
            "recorded_at": "2025-01-01T12:00:00Z",
        }
        route = f"/api/cases/{case_id}/media/{source['source_id']}"
        edited = client.patch(route, json=revised_metadata)
        assert edited.status_code == 200
        stale = edited.json()
        assert stale["evidence_revision"] == 2
        assert stale["analyzed_revision"] == 1
        assert stale["analysis"] == first["analysis"]
        assert stale["memory"] == first["memory"]
        assert stale["analyzed_media_files"] == first["media_files"]
        assert stale["media_files"][0] == {**source, "metadata": revised_metadata}
        assert stale["media_files"][0]["captured_at"] is None
        # Saving identical context does not invalidate another reconstruction.
        assert client.patch(route, json=revised_metadata).json() == stale
        second = finish_job(client, app, case_id)
        archived_source = second["analysis_history"][0]["media_files"][0]
        assert archived_source["metadata"] == original_metadata
        assert second["analyzed_media_files"][0]["metadata"] == revised_metadata
        assert client.get(source["url"]).content == jpeg()


def test_legacy_annotation_snapshot_backfilled_before_edit(tmp_path):
    app = create_app(settings(tmp_path, analysis_mode="mock"))
    with TestClient(app) as client:
        initial = client.post(
            "/api/cases",
            data={"metadata": '[{"label":"Original"}]'},
            files=[("files", ("evidence.jpg", jpeg()))],
        ).json()
        first = finish_job(client, app, initial["case_id"])
        legacy = app.state.store.get_case(first["case_id"])
        legacy.analyzed_media_files = []
        app.state.store.save_case(legacy)
        source_id = first["media_files"][0]["source_id"]
        patched = client.patch(
            f"/api/cases/{first['case_id']}/media/{source_id}",
            json={"label": "Changed"},
        )
        assert patched.status_code == 200
        assert (
            patched.json()["analyzed_media_files"][0]["metadata"]["label"] == "Original"
        )


def test_metadata_patch_checks_case_ownership_readonly_and_active_job(tmp_path):
    from rewind.models import Job

    app = create_app(settings(tmp_path))
    with TestClient(app) as client:
        first = client.post("/api/cases", files=[("files", ("a.jpg", jpeg()))]).json()
        second = client.post("/api/cases", files=[("files", ("b.jpg", jpeg()))]).json()
        source_id = first["media_files"][0]["source_id"]
        assert (
            client.patch(
                f"/api/cases/{second['case_id']}/media/{source_id}",
                json={"label": "Wrong case"},
            ).status_code
            == 404
        )
        assert (
            client.patch(f"/api/cases/unknown/media/{source_id}", json={}).status_code
            == 404
        )
        assert (
            client.patch(
                "/api/cases/demo/media/demo-video", json={"label": "Edit demo"}
            ).status_code
            == 409
        )
        app.state.store.save_job(
            Job(
                job_id="blocked",
                case_id=first["case_id"],
                status="queued",
                stage="uploading",
                progress=0,
            )
        )
        assert (
            client.patch(
                f"/api/cases/{first['case_id']}/media/{source_id}",
                json={"label": "Wait"},
            ).status_code
            == 409
        )
        assert client.get(f"/api/cases/{first['case_id']}").json() == first


def test_annotation_parser_closes_uploads_on_validation_error(tmp_path):
    from fastapi import HTTPException, UploadFile
    from rewind.uploads import ingest_batch

    upload = UploadFile(file=io.BytesIO(jpeg()), filename="image.jpg")
    with pytest.raises(HTTPException, match="422"):
        asyncio.run(
            ingest_batch([upload], tmp_path / "never-created", settings(tmp_path), "[]")
        )
    assert upload.file.closed
    assert not (tmp_path / "never-created").exists()


@pytest.mark.parametrize("provider_fails", [False, True])
def test_classifier_observations_persist_without_becoming_accepted_claims(
    tmp_path, monkeypatch, provider_fails
):
    from rewind.intelligence.models import EvidenceIntelligence, SourceIntelligence

    async def analyze_with_signals(
        case, paths, progress, *, settings, intelligence_sink
    ):
        assert settings.typesafe_api_key == "configured-classifier-key"
        await progress("classifying_evidence", 8)
        await intelligence_sink(
            EvidenceIntelligence(
                model="jev-1.14.0",
                version="test",
                status="complete",
                sources=[
                    SourceIntelligence(
                        source_id=case.media_files[0].source_id,
                        labels={
                            "incident_relevant": 0.4
                            if case.evidence_revision == 1
                            else 0.9
                        },
                    )
                ],
            )
        )
        if provider_fails:
            raise TimeoutError
        return Analysis(events=[], summary=[], mode="live")

    monkeypatch.setattr("rewind.analysis.analyze", analyze_with_signals)
    app = create_app(settings(tmp_path, typesafe_api_key="configured-classifier-key"))
    with TestClient(app) as client:
        created = client.post(
            "/api/cases", files=[("files", ("source.jpg", jpeg()))]
        ).json()
        case_id = created["case_id"]
        if provider_fails:
            job = client.post(f"/api/cases/{case_id}/analyze").json()

            async def wait():
                for _ in range(100):
                    current = app.state.store.get_job(job["job_id"])
                    if current.status == "failed":
                        return
                    await asyncio.sleep(0.01)
                pytest.fail("Expected failed generation job")

            client.portal.call(wait)
            current = client.get(f"/api/cases/{case_id}").json()
            assert current["analysis"] is None and current["memory"] is None
        else:
            current = finish_job(client, app, case_id)
        assert (
            current["intelligence"]["sources"][0]["labels"]["incident_relevant"] == 0.4
        )
        if not provider_fails:
            client.post(
                f"/api/cases/{case_id}/media", files=[("files", ("more.jpg", jpeg()))]
            )
            updated = finish_job(client, app, case_id)
            assert (
                updated["intelligence"]["sources"][0]["labels"]["incident_relevant"]
                == 0.9
            )
            assert (
                updated["analysis_history"][0]["intelligence"]["sources"][0]["labels"][
                    "incident_relevant"
                ]
                == 0.4
            )
    with TestClient(create_app(settings(tmp_path))) as client:
        saved = client.get(f"/api/cases/{case_id}").json()
        assert saved["intelligence"] is not None


def test_preview_is_readable_while_job_runs_without_replacing_accepted_state(
    tmp_path, monkeypatch
):
    from rewind.intelligence.models import (
        EvidenceIntelligence,
        FrameAssessment,
        SourceIntelligence,
    )

    release = asyncio.Event()

    async def delayed_analysis(case, paths, progress, *, settings, intelligence_sink):
        await progress("classifying_evidence", 8)
        await intelligence_sink(
            EvidenceIntelligence(
                model="jev-1.14.0",
                version="test",
                status="complete",
                sources=[
                    SourceIntelligence(
                        source_id=case.media_files[0].source_id,
                        frames=[
                            FrameAssessment(
                                source_time=3.25, signals={"vehicle_visible": 0.95}
                            )
                        ],
                    )
                ],
            )
        )
        await progress("synthesizing", 80)
        await release.wait()
        return case.analysis

    monkeypatch.setattr("rewind.analysis.analyze", delayed_analysis)
    app = create_app(settings(tmp_path))
    with TestClient(app) as client:
        before = client.get("/api/cases/demo").json()
        job = client.post("/api/cases/demo/analyze").json()

        async def wait_preview():
            for _ in range(100):
                if app.state.store.get_case("demo").preview is not None:
                    return
                await asyncio.sleep(0.01)
            pytest.fail("Preview was not published")

        client.portal.call(wait_preview)
        during = client.get("/api/cases/demo").json()
        assert during["preview"]["analysis"]["events"][0]["source_start"] == 3.25
        assert during["analysis"] == before["analysis"]
        assert during["memory"] == before["memory"]
        assert during["analysis_history"] == before["analysis_history"]
        assert client.get(f"/api/jobs/{job['job_id']}").json()["status"] == "running"
        client.portal.call(release.set)

        async def wait_complete():
            for _ in range(100):
                if app.state.store.get_job(job["job_id"]).status == "completed":
                    return
                await asyncio.sleep(0.01)
            pytest.fail("Analysis did not finish")

        client.portal.call(wait_complete)
        assert client.get("/api/cases/demo").json()["preview"] is None
