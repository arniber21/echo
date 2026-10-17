"""Classifier seam tests: wire protocol, cache, source clocks and fail-open behavior."""

import asyncio
import io
import json
from pathlib import Path

import httpx
import pytest
from PIL import Image
from pydantic import ValidationError
from rewind.intelligence.frames import normalize_image, sample_times
from rewind.intelligence.models import (
    BoxEdges,
    EvidenceIntelligence,
    SourceIntelligence,
)
from rewind.intelligence.service import JevIntelligence
from rewind.models import Analysis, Claim, MediaFile, SourceRef


def photo() -> bytes:
    output = io.BytesIO()
    Image.new("RGB", (90, 60), "green").save(output, "PNG")
    return output.getvalue()


def source(kind="photo", source_id="photo-1"):
    return MediaFile(
        source_id=source_id,
        filename="test.png",
        source_type=kind,
        mime_type="image/png",
        url="/test",
        sha256="a" * 64,
        size_bytes=100,
        duration_seconds=2 if kind == "video" else None,
    )


def client(tmp_path, handler):
    service = JevIntelligence("not-a-real-key", cache_dir=tmp_path)
    asyncio.run(service.close())
    service._client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        headers={
            "Authorization": "Bearer not-a-real-key",
            "TypeSafe-Danger-Zone-Images": "true",
        },
    )
    return service


def answer_body(questions, presence=0.95):
    return {
        "model": "jev-1.14.0",
        "answers": {
            key: (
                {
                    "type": "box",
                    "box": {"top": 0.2, "bottom": 0.8, "left": 0.1, "right": 0.7},
                    "confidence": 0.7,
                }
                if question["type"] == "box"
                else {"type": "noul", "noul": presence}
            )
            for key, question in questions.items()
        },
        "usage": {"input_tokens": 100, "output_tokens": 10},
    }


def test_frame_preparation_bounds_and_sampling():
    data, width, height = normalize_image(photo())
    assert width == height == 280
    assert Image.open(io.BytesIO(data)).format == "JPEG"
    times = sample_times(2, 8)
    assert len(times) == 8 and times[0] == 0 and times[-1] < 2
    assert times == sorted(times)
    assert sample_times(0.01, 1) == [0]
    with pytest.raises(ValidationError):
        BoxEdges(top=0.5, bottom=0.1, left=0, right=1)


def test_image_wire_cache_and_presence_gate(tmp_path):
    calls = []

    def handle(request):
        assert request.headers["TypeSafe-Danger-Zone-Images"] == "true"
        assert "multipart/form-data" in request.headers["content-type"]
        content = request.content
        assert b'"part": "frame"' in content
        calls.append(request)
        questions = {
            key: {"type": "noul"}
            for key in [
                "road_visible",
                "vehicle_visible",
                "vehicle_contact_visible",
                "damage_visible",
                "obstructed",
            ]
        }
        questions["vehicle_box"] = {"type": "box"}
        return httpx.Response(200, json=answer_body(questions, presence=0.3))

    service = client(tmp_path, handle)
    path = tmp_path / "input.png"
    path.write_bytes(photo())

    async def run():
        report = await service.scan_sources([source()], {"photo-1": path})
        assert report.status == "complete" and report.input_tokens == 100
        frame = report.sources[0].frames[0]
        assert frame.vehicle_box is None and frame.box_confidence is None
        assert frame.source_time is None and frame.image_sha256
        # Cache identity follows content and questions, not database identity.
        cached = await service.scan_sources(
            [source(source_id="new-id")], {"new-id": path}
        )
        assert cached.input_tokens == 0 and cached.sources[0].source_id == "new-id"
        await service.close()

    asyncio.run(run())
    assert len(calls) == 1


def test_video_sample_clocks_and_bounded_frames(tmp_path, monkeypatch):
    times = []

    async def frame(path, timestamp):
        times.append(timestamp)
        return photo()

    monkeypatch.setattr("rewind.intelligence.service.video_frame", frame)

    def handle(request):
        questions = {
            key: {"type": "noul"}
            for key in [
                "road_visible",
                "vehicle_visible",
                "vehicle_contact_visible",
                "damage_visible",
                "obstructed",
            ]
        }
        questions["vehicle_box"] = {"type": "box"}
        return httpx.Response(200, json=answer_body(questions))

    service = client(tmp_path, handle)
    service.max_frames = 3

    async def run():
        report = await service.scan_sources(
            [source("video")], {"photo-1": Path("ignored.mp4")}
        )
        assert [item.source_time for item in report.sources[0].frames] == times
        assert len(times) == 3 and max(times) < 2
        assert report.sources[0].frames[0].vehicle_box is not None
        await service.close()

    asyncio.run(run())


def test_api_failure_does_not_fail_reconstruction(tmp_path):
    calls = []

    def handle(request):
        calls.append(request)
        return httpx.Response(503, json={"error": "provider unavailable"})

    service = client(tmp_path, handle)
    path = tmp_path / "input.png"
    path.write_bytes(photo())

    async def run():
        report = await service.scan_sources([source()], {"photo-1": path})
        assert report.status == "unavailable"
        assert report.diagnostics == ["visual_scan_incomplete"]
        assert report.input_tokens == 0
        await service.close()

    asyncio.run(run())
    assert len(calls) == 2


def test_text_labels_and_claim_checks_only_receive_cited_extraction(tmp_path):
    states = []

    def handle(request):
        body = json.loads(request.content)
        states.append(body["state"])
        return httpx.Response(200, json=answer_body(body["questions"]))

    service = client(tmp_path, handle)
    report = EvidenceIntelligence(
        model="jev-1.14.0",
        version="test",
        status="complete",
        sources=[SourceIntelligence(source_id="a"), SourceIntelligence(source_id="b")],
    )
    analysis = Analysis(
        events=[],
        summary=[
            Claim(text="A van is visible", source_refs=[SourceRef(source_id="a")])
        ],
    )
    records = [
        {"source_id": "a", "events": ["van is visible"]},
        {"source_id": "b", "events": ["unrelated"]},
    ]

    async def run():
        result = await service.assess_analysis(analysis, records, report)
        assert result.input_tokens == 300 and len(result.claims) == 1
        assert result.claims[0].claim_index == 0
        assert result.sources[0].labels["incident_relevant"] == 0.95
        cached = await service.assess_analysis(analysis, records, report)
        assert cached.input_tokens == 0
        await service.close()

    asyncio.run(run())
    claim_state = next(state for state in states if "claim" in state)
    assert claim_state["cited_extractions"] == [{"events": ["van is visible"]}]


def test_ffmpeg_uses_source_seek_and_one_frame(monkeypatch):
    from rewind.intelligence.frames import video_frame

    seen = []

    class Process:
        returncode = 0

        async def communicate(self):
            return photo(), None

    async def launch(*args, **kwargs):
        seen.extend(args)
        return Process()

    monkeypatch.setattr(asyncio, "create_subprocess_exec", launch)
    result = asyncio.run(video_frame(Path("/source/clip.mp4"), 1.25))
    assert result == photo()
    assert seen[seen.index("-ss") + 1] == "1.25"
    assert seen[seen.index("-frames:v") + 1] == "1"
    assert "/source/clip.mp4" in seen


def test_ffmpeg_timeout_kills_child(monkeypatch):
    from rewind.intelligence.frames import video_frame

    class Process:
        returncode = None
        killed = False

        async def communicate(self):
            return b"", None

        def kill(self):
            self.killed = True

        async def wait(self):
            self.returncode = -9

    process = Process()

    async def launch(*args, **kwargs):
        return process

    async def timeout(coroutine, timeout):
        coroutine.close()
        raise TimeoutError

    monkeypatch.setattr(asyncio, "create_subprocess_exec", launch)
    monkeypatch.setattr(asyncio, "wait_for", timeout)
    with pytest.raises(TimeoutError):
        asyncio.run(video_frame(Path("/source/clip.mp4"), 0))
    assert process.killed


@pytest.mark.parametrize("status", [401, 422])
def test_non_retryable_errors_and_audio_skip(tmp_path, status):
    calls = []

    def handle(request):
        calls.append(request)
        return httpx.Response(status, json={"error": "not copied into diagnostics"})

    service = client(tmp_path, handle)
    path = tmp_path / "input.png"
    path.write_bytes(photo())

    async def run():
        report = await service.scan_sources([source()], {"photo-1": path})
        assert report.status == "unavailable" and len(calls) == 1
        audio = await service.scan_sources([source("audio")], {})
        assert audio.status == "complete" and audio.sources[0].frames == []
        assert len(calls) == 1
        await service.close()

    asyncio.run(run())
