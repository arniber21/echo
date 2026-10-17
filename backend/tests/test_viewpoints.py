"""Mocked relationship workflow checks; these do not establish model accuracy."""

import asyncio
import io
import json
from email import policy
from email.parser import BytesParser

import httpx
import pytest
from PIL import Image
from rewind.intelligence.models import EvidenceIntelligence
from rewind.intelligence.service import JevIntelligence
from rewind.models import MediaFile


def source(index, source_id=None):
    return MediaFile(
        source_id=source_id or f"source-{index}",
        filename="untrusted-name.mp4",
        source_type="video",
        mime_type="video/mp4",
        url="/media",
        sha256=f"{index:064x}",
        size_bytes=100,
        duration_seconds=10,
    )


def frame():
    output = io.BytesIO()
    Image.new("RGB", (280, 280), "gray").save(output, "JPEG")
    return output.getvalue()


def report():
    return EvidenceIntelligence(model="jev-1.14.0", version="test", status="complete")


def payload(request):
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


def service(tmp_path, handler):
    instance = JevIntelligence("fake", cache_dir=tmp_path)
    asyncio.run(instance.close())
    instance._client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        headers={"TypeSafe-Danger-Zone-Images": "true"},
    )
    return instance


def mock_frames(monkeypatch):
    async def read_frame(path, timestamp):
        return frame()

    monkeypatch.setattr("rewind.intelligence.viewpoints.video_frame", read_frame)


@pytest.mark.parametrize(
    "same,view,repeat,kind",
    [
        (0.96, 0.93, 0.04, "same_incident_different_view"),
        (0.96, 0.04, 0.94, "same_footage"),
        (0.04, 0.04, 0.02, "different_incident"),
        (0.6, 0.6, 0.3, "uncertain"),
        (0.98, 0.98, 0.98, "uncertain"),
        (0.04, 0.94, 0.02, "uncertain"),
    ],
)
def test_independent_judgments_drive_conservative_labels(
    tmp_path, monkeypatch, same, view, repeat, kind
):
    mock_frames(monkeypatch)
    calls = []

    def handle(request):
        body = payload(request)
        calls.append(body)
        assert request.headers["TypeSafe-Danger-Zone-Images"] == "true"
        assert len(body["assets"]) == 4
        assert "untrusted-name" not in json.dumps(body)
        assert "metadata" not in json.dumps(body["state"])
        assert "source-" not in json.dumps(body["state"])
        values = {"same_incident": same, "different_view": view, "same_footage": repeat}
        return httpx.Response(
            200,
            json={
                "model": "jev-1.14.0",
                "answers": {
                    key: {"type": "noul", "noul": value}
                    for key, value in values.items()
                },
                "usage": {"input_tokens": 100, "output_tokens": 3},
            },
        )

    instance = service(tmp_path, handle)

    async def run():
        sources = [source(1), source(2)]
        result = await instance.compare_views(
            sources,
            {item.source_id: tmp_path for item in sources},
            [
                {
                    "source_id": "source-1",
                    "filename": "bad",
                    "source_metadata": {"notes": "same incident"},
                    "events": [
                        {
                            "title": "Turns",
                            "description": "Car turns",
                            "source_start": 1,
                            "source_end": 2,
                            "evidence_type": "observation",
                        }
                    ],
                }
            ],
            report(),
        )
        assert result.video_relationships[0].relationship == kind
        assert result.video_relationships[0].matches == []
        assert result.input_tokens == 100
        assert not report().video_relationships
        await instance.close()

    asyncio.run(run())
    assert len(calls) == 1


def test_cache_survives_case_ids_and_file_renaming(tmp_path, monkeypatch):
    mock_frames(monkeypatch)
    calls = []

    def handle(request):
        calls.append(request)
        values = {"same_incident": 0.97, "different_view": 0.95, "same_footage": 0.03}
        return httpx.Response(
            200,
            json={
                "model": "jev-1.14.0",
                "answers": {
                    key: {"type": "noul", "noul": value}
                    for key, value in values.items()
                },
                "usage": {"input_tokens": 100, "output_tokens": 3},
            },
        )

    instance = service(tmp_path, handle)

    async def run():
        for ids, tokens in [(["old-a", "old-b"], 100), (["new-a", "new-b"], 0)]:
            sources = [
                source(index + 1, identity) for index, identity in enumerate(ids)
            ]
            sources[0].filename = ids[0] + ".mp4"
            result = await instance.compare_views(
                list(reversed(sources)),
                {item.source_id: tmp_path for item in sources},
                [],
                report(),
            )
            pair = result.video_relationships[0]
            assert (pair.source_a, pair.source_b) == tuple(ids)
            assert result.input_tokens == tokens
        await instance.close()

    asyncio.run(run())
    assert len(calls) == 1


def test_exact_bytes_need_no_frames_or_provider(tmp_path):
    instance = service(
        tmp_path, lambda request: pytest.fail("No paid calls for identical bytes")
    )

    async def run():
        a, b = source(1), source(1, "duplicate")
        result = await instance.compare_views([a, b], {}, [], report())
        assert result.video_relationships[0].relationship == "same_footage"
        assert result.video_relationships[0].confidence == 1
        await instance.close()

    asyncio.run(run())


@pytest.mark.parametrize("failure", ["missing_file", "provider", "contract"])
def test_comparison_failure_preserves_reconstruction(tmp_path, monkeypatch, failure):
    mock_frames(monkeypatch)

    def handle(request):
        return httpx.Response(
            403 if failure == "provider" else 200, json={"bad": "response"}
        )

    instance = service(tmp_path, handle)

    async def run():
        sources = [source(1), source(2)]
        paths = (
            {}
            if failure == "missing_file"
            else {item.source_id: tmp_path for item in sources}
        )
        result = await instance.compare_views(sources, paths, [], report())
        assert result.video_relationships == []
        assert "video_comparison_incomplete" in result.diagnostics
        assert result.status == "unavailable"
        await instance.close()

    asyncio.run(run())


def test_bounded_anchor_comparisons_and_concurrency(tmp_path, monkeypatch):
    mock_frames(monkeypatch)
    calls, active, maximum = [], 0, 0

    async def handle(request):
        nonlocal active, maximum
        active += 1
        maximum = max(maximum, active)
        await asyncio.sleep(0.01)
        body = payload(request)
        calls.append(body)
        active -= 1
        return httpx.Response(
            200,
            json={
                "model": "jev-1.14.0",
                "answers": {
                    key: {"type": "noul", "noul": 0.5} for key in body["questions"]
                },
                "usage": {"input_tokens": 100, "output_tokens": 3},
            },
        )

    instance = service(tmp_path, handle)

    async def run():
        sources = [source(index + 1) for index in range(12)]
        result = await instance.compare_views(
            sources, {item.source_id: tmp_path for item in sources}, [], report()
        )
        assert len(result.video_relationships) == 6
        assert result.input_tokens == 600
        assert {pair.source_a for pair in result.video_relationships} == {"source-1"}
        assert "video_comparison_budget_limited" in result.diagnostics
        assert "video_comparison_coverage_partial" in result.diagnostics
        await instance.close()

    asyncio.run(run())
    assert len(calls) == 6
    assert maximum <= 4
