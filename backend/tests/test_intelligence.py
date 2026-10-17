"""Classifier seam tests: wire protocol, cache, source clocks and fail-open behavior."""

import asyncio
import io
import json
from email import policy
from email.parser import BytesParser
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


def multipart_body(request):
    message = BytesParser(policy=policy.default).parsebytes(
        ("Content-Type: " + request.headers["content-type"] + "\r\n\r\n").encode()
        + request.content
    )
    return json.loads(
        next(
            part.get_payload(decode=True)
            for part in message.iter_parts()
            if part.get_param("name", header="content-disposition") == "request"
        )
    )


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
        return httpx.Response(
            200, json=answer_body(multipart_body(request)["questions"])
        )

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
    assert claim_state["cited_extractions"][0]["events"] == ["van is visible"]
    assert claim_state["cited_extractions"][0]["citation"] == {
        "source_start": None,
        "source_end": None,
    }


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


def test_claim_support_cannot_use_relevant_event_outside_cited_source_range(tmp_path):
    states = []

    def handle(request):
        body = json.loads(request.content)
        state = body["state"]
        states.append(state)
        result = answer_body(body["questions"])
        if "claim" in state:
            # This test double makes support depend on which evidence the caller
            # actually sends, rather than always returning a favorable answer.
            has_contact = any(
                event["title"] == "Contact"
                for entry in state["cited_extractions"]
                for event in entry["events"]
            )
            result["answers"]["supported"]["noul"] = float(has_contact)
            result["answers"]["overclaim"]["noul"] = float(not has_contact)
        return httpx.Response(200, json=result)

    service = client(tmp_path, handle)
    report = EvidenceIntelligence(
        model="jev-1.14.0",
        version="test",
        status="complete",
        sources=[SourceIntelligence(source_id="a")],
    )
    analysis = Analysis(
        events=[],
        summary=[
            Claim(
                text="Vehicles contact at source second 1",
                source_refs=[SourceRef(source_id="a", source_start=0, source_end=2)],
            )
        ],
    )
    records = [
        {
            "source_id": "a",
            "source_type": "video",
            "events": [
                {
                    "title": "Driving",
                    "source_start": 0,
                    "source_end": 2,
                    "evidence_type": "observation",
                },
                {
                    "title": "Contact",
                    "source_start": 8,
                    "source_end": 9,
                    "case_best": 1,
                    "evidence_type": "observation",
                },
                {
                    "title": "Unknown time",
                    "source_start": None,
                    "source_end": None,
                    "evidence_type": "inference",
                },
            ],
        }
    ]

    async def run():
        result = await service.assess_analysis(analysis, records, report)
        assert result.claims[0].supported_probability == 0
        assert result.claims[0].overclaim_probability == 1
        await service.close()

    asyncio.run(run())
    scoped = next(state for state in states if "claim" in state)["cited_extractions"][0]
    assert scoped["citation"] == {"source_start": 0, "source_end": 2}
    assert scoped["citation_scope"] == "source_interval"
    assert scoped["excluded_outside_citation"] == 1
    assert scoped["excluded_unknown_source_time"] == 1
    assert [event["title"] for event in scoped["events"]] == ["Driving"]


def test_photo_citations_preserve_unknown_time_and_inference_kind():
    from rewind.intelligence.service import _cited_extractions

    claim = Claim(
        text="Damage appears visible", source_refs=[SourceRef(source_id="photo")]
    )
    records = [
        {
            "source_id": "photo",
            "source_type": "photo",
            "events": [
                {
                    "title": "Possible damage",
                    "source_start": None,
                    "source_end": None,
                    "case_best": 7,
                    "alignment_confidence": 0.2,
                    "evidence_type": "inference",
                }
            ],
        }
    ]
    entry = _cited_extractions(claim, records)[0]
    assert entry["citation_scope"] == "untimed_photo"
    assert entry["citation"] == {"source_start": None, "source_end": None}
    assert entry["events"][0]["source_start"] is None
    assert entry["events"][0]["evidence_type"] == "inference"
    assert entry["events"][0]["alignment_confidence"] == 0.2


def test_claim_prompt_version_does_not_invalidate_visual_cache(tmp_path, monkeypatch):
    from rewind.intelligence import service as module

    calls = []

    def handle(request):
        body = json.loads(request.content)
        calls.append(body)
        return httpx.Response(200, json=answer_body(body["questions"]))

    service = client(tmp_path, handle)
    questions = {"signal": {"type": "noul", "instructions": "Present?"}}

    async def run():
        await service._evaluate("visual", {"value": 1}, questions)
        await service._evaluate("claim-support", {"value": 1}, questions)
        monkeypatch.setattr(module, "CLAIM_QUESTION_VERSION", "next-question-version")
        _, visual_usage = await service._evaluate("visual", {"value": 1}, questions)
        _, claim_usage = await service._evaluate(
            "claim-support", {"value": 1}, questions
        )
        assert visual_usage == 0 and claim_usage == 100
        await service.close()

    asyncio.run(run())
    assert len(calls) == 3


def test_four_frame_batches_account_once_and_keep_legacy_frame_cache(tmp_path):
    from rewind.intelligence.service import VISUAL_QUESTIONS, _noul_questions

    calls = []

    def handle(request):
        assert request.headers["TypeSafe-Danger-Zone-Images"] == "true"
        body = multipart_body(request)
        calls.append(body)
        assert len(body["state"]["frames"]) == 4
        assert len(body["assets"]) == 4 and len(body["questions"]) == 24
        for index in range(4):
            asset = body["state"]["frames"][index]["frame"]
            # Exactly one plain-text reference to each asset, in shared state.
            assert json.dumps(body["state"]).count(asset) == 1
            for name, question in body["questions"].items():
                if name.startswith(f"f{index}_"):
                    assert f"`frames[{index}].frame`" in question["instructions"]
                    assert "rewind-batch-asset" not in question["instructions"]
        return httpx.Response(200, json=answer_body(body["questions"]))

    service = client(tmp_path, handle)
    questions = _noul_questions(VISUAL_QUESTIONS)
    questions["vehicle_box"] = {
        "type": "box",
        "instructions": "The visible vehicle nearest the image center in `frame`.",
    }
    images = [f"frame-{index}".encode() for index in range(4)]

    async def run():
        results, usage = await service._visual_batch(images, questions)
        assert usage == 100 and all(result is not None for result in results)
        # Existing single-frame caller sees unchanged cache identity.
        for image in images:
            _, cached_usage = await service._evaluate(
                "visual", {"frame": "rewind-frame-asset"}, questions, image
            )
            assert cached_usage == 0
        _, repeated_usage = await service._visual_batch(images, questions)
        assert repeated_usage == 0
        await service.close()

    asyncio.run(run())
    assert len(calls) == 1


@pytest.mark.parametrize("invalid_answer", [None, {"type": "noul", "noul": 1.2}])
def test_batch_sends_only_cache_misses_and_retries_only_incomplete_frame(
    tmp_path, invalid_answer
):
    questions = {"visible": {"type": "noul", "instructions": "Is `frame` visible?"}}
    calls = []

    def handle(request):
        body = multipart_body(request)
        calls.append(body)
        if len(calls) == 1:
            assert len(body["state"]["frames"]) == 2
            result = answer_body(body["questions"])
            # First frame completes; second frame's missing answer must not
            # discard that first result or cause its image to be submitted again.
            if invalid_answer is None:
                del result["answers"]["f1_visible"]
            else:
                result["answers"]["f1_visible"] = invalid_answer
        else:
            assert body["state"] == {"frame": "rewind-frame-asset"}
            assert b"missing-frame" in request.content
            assert b"completed-frame" not in request.content
            result = answer_body(body["questions"])
        return httpx.Response(200, json=result)

    service = client(tmp_path, handle)

    async def run():
        # Seed a cache record in the exact pre-batching format.
        from rewind.intelligence.service import Evaluation

        cached = Evaluation.model_validate(answer_body(questions))
        await service._save(
            service._cache_path(
                "visual", {"frame": "rewind-frame-asset"}, questions, b"cached-frame"
            ),
            cached,
        )
        results, usage = await service._visual_batch(
            [b"cached-frame", b"completed-frame", b"missing-frame"], questions
        )
        assert all(result is not None for result in results)
        assert usage == 200  # two requests, never multiplied by frame count
        assert len(calls) == 2
        _, usage = await service._visual_batch(
            [b"cached-frame", b"completed-frame", b"missing-frame"], questions
        )
        assert usage == 0 and len(calls) == 2
        await service.close()

    asyncio.run(run())


def test_failed_batch_preserves_other_batch_and_source_timestamps(
    tmp_path, monkeypatch
):
    async def frame(path, timestamp):
        output = io.BytesIO()
        Image.new("RGB", (280, 280), (int(timestamp * 50), 0, 0)).save(output, "PNG")
        return output.getvalue()

    monkeypatch.setattr("rewind.intelligence.service.video_frame", frame)
    calls = []

    def handle(request):
        body = multipart_body(request)
        calls.append(body)
        # First batch fails without retry on a contract error; the other batch
        # still returns independently and remains useful to the application.
        if body["assets"]["rewind-batch-asset-0"] and len(calls) == 1:
            return httpx.Response(422, json={"error": "bad batch"})
        return httpx.Response(200, json=answer_body(body["questions"]))

    service = client(tmp_path, handle)

    async def run():
        report = await service.scan_sources(
            [source("video")], {"photo-1": Path("ignored")}
        )
        assert report.status == "partial" and report.input_tokens == 100
        assert len(report.sources[0].frames) == 4
        times = [item.source_time for item in report.sources[0].frames]
        assert times == sample_times(2, 8)[4:]
        assert report.diagnostics == ["visual_scan_incomplete"]
        await service.close()

    asyncio.run(run())
    assert len(calls) == 2


def test_api_concurrency_is_bounded_and_successful_usage_is_not_multiplied(tmp_path):
    active, maximum = 0, 0

    async def handle(request):
        nonlocal active, maximum
        active += 1
        maximum = max(maximum, active)
        await asyncio.sleep(0)
        result = answer_body(multipart_body(request)["questions"])
        active -= 1
        return httpx.Response(200, json=result)

    service = client(tmp_path, handle)
    questions = {"visible": {"type": "noul", "instructions": "Is `frame` visible?"}}

    async def run():
        results = await asyncio.gather(
            *(
                service._visual_batch(
                    [f"batch-{batch}-frame-{index}".encode() for index in range(4)],
                    questions,
                )
                for batch in range(8)
            )
        )
        assert sum(usage for _, usage in results) == 800
        assert all(result is not None for batch, _ in results for result in batch)
        assert maximum == 4
        await service.close()

    asyncio.run(run())


def test_request_deadline_yields_partial_results_without_waiting_for_long_provider(
    tmp_path, monkeypatch
):
    real_timeout = asyncio.timeout
    deadlines = []

    def bounded_timeout(seconds):
        deadlines.append(seconds)
        return real_timeout(0.001)

    monkeypatch.setattr(asyncio, "timeout", bounded_timeout)

    async def handle(request):
        await asyncio.sleep(0.1)
        raise AssertionError("Deadline failed to stop slow provider")

    service = client(tmp_path, handle)
    questions = {"visible": {"type": "noul", "instructions": "Is `frame` visible?"}}

    async def run():
        results, usage = await service._visual_batch(
            [b"frame-a", b"frame-b"], questions
        )
        assert results == [None, None] and usage == 0
        assert deadlines == [20]
        await service.close()

    asyncio.run(run())
