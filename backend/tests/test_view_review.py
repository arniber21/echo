"""Joint-review workflow invariants, using simulated provider output."""

import asyncio
import io

import pytest
from PIL import Image
from rewind.analysis.cache import JsonCache
from rewind.analysis.view_review import _Review, review_uncertain_views
from rewind.intelligence.models import EvidenceIntelligence, VideoRelationship
from rewind.models import MediaFile


def source(identity, index):
    return MediaFile(
        source_id=identity,
        filename="ignore-me.mp4",
        source_type="video",
        mime_type="video/mp4",
        url="/media",
        sha256=f"{index:064x}",
        duration_seconds=8,
        size_bytes=100,
    )


def pair(a="a", b="b", **updates):
    return VideoRelationship(
        source_a=a,
        source_b=b,
        relationship="uncertain",
        confidence=0,
        same_incident_probability=0.6,
        different_view_probability=0.65,
        basis="Jev prototype",
        **updates,
    )


def records(a="a", b="b"):
    return [
        {
            "source_id": identity,
            "source_metadata": {"notes": "SECRET USER CLAIM"},
            "events": [
                {
                    "event_id": f"event-{identity}-0",
                    "title": "Truck brakes",
                    "description": "White truck brakes by bridge",
                    "source_start": 1,
                    "source_end": 2,
                    "evidence_type": "observation",
                }
            ],
        }
        for identity in (a, b)
    ]


@pytest.fixture
def frames(monkeypatch):
    async def video_frame(path, timestamp):
        output = io.BytesIO()
        Image.new("RGB", (280, 280), "gray").save(output, "JPEG")
        return output.getvalue()

    monkeypatch.setattr("rewind.analysis.view_review.video_frame", video_frame)


class Provider:
    def __init__(self, *, invalid=False, fail=False):
        self.calls = 0
        self.invalid = invalid
        self.fail = fail

    async def generate(self, prompt, schema, *, path, mime_type, validate):
        self.calls += 1
        assert "SECRET USER CLAIM" not in prompt
        assert "ignore-me.mp4" not in prompt
        assert mime_type == "image/jpeg"
        assert Image.open(path).size == (1280, 800)
        if self.fail:
            raise RuntimeError("provider failure")
        value = schema(
            relationship="same_incident_different_view",
            confidence=0.88,
            basis="Distinctive bridge and truck markings agree; clocks remain unaligned.",
            matches=[
                {
                    "event_a": "bad" if self.invalid else "a-0",
                    "event_b": "b-0",
                    "probability": 0.9,
                }
            ],
        )
        validate(value)
        return value


def test_joint_review_preserves_raw_jev_and_remaps_cache_ids(tmp_path, frames):
    provider = Provider()

    async def run():
        for a, b in [("old-a", "old-b"), ("new-a", "new-b")]:
            original = EvidenceIntelligence(
                model="jev",
                version="1",
                status="complete",
                video_relationships=[pair(a, b)],
            )
            sources = [source(a, 1), source(b, 2)]
            result = await review_uncertain_views(
                provider,
                sources,
                {a: tmp_path, b: tmp_path},
                records(a, b),
                original,
                JsonCache(tmp_path),
                "gemini-test",
            )
            relation = result.video_relationships[0]
            assert relation.relationship == "uncertain"
            assert relation.same_incident_probability == 0.6
            assert original.video_relationships[0].detailed_review is None
            assert (
                relation.detailed_review.relationship == "same_incident_different_view"
            )
            assert relation.detailed_review.model == "gemini-test"
            assert relation.detailed_review.matches[0].event_a == f"event-{a}-0"
            assert relation.detailed_review.matches[0].event_b == f"event-{b}-0"

    asyncio.run(run())
    assert provider.calls == 1


@pytest.mark.parametrize(
    "invalid,fail,paths",
    [(True, False, True), (False, True, True), (False, False, False)],
)
def test_invalid_refs_provider_and_preparation_fail_open(
    tmp_path, frames, invalid, fail, paths
):
    original = EvidenceIntelligence(
        model="jev", version="1", status="complete", video_relationships=[pair()]
    )
    result = asyncio.run(
        review_uncertain_views(
            Provider(invalid=invalid, fail=fail),
            [source("a", 1), source("b", 2)],
            {"a": tmp_path, "b": tmp_path} if paths else {},
            records(),
            original,
            JsonCache(tmp_path),
            "test",
        )
    )
    assert result.video_relationships[0].detailed_review is None
    assert "detailed_view_review_incomplete" in result.diagnostics
    assert result.status == "complete"


def test_confident_and_implausible_pairs_do_not_escalate(tmp_path, frames):
    provider = Provider()
    relationships = [
        pair().model_copy(update={"relationship": "same_footage"}),
        pair().model_copy(update={"same_incident_probability": 0.1}),
    ]
    original = EvidenceIntelligence(
        model="jev", version="1", status="complete", video_relationships=relationships
    )
    asyncio.run(
        review_uncertain_views(
            provider, [], {}, [], original, JsonCache(tmp_path), "test"
        )
    )
    assert provider.calls == 0


def test_at_most_two_pairs_are_reviewed(tmp_path, frames):
    provider = Provider(fail=True)
    sources = [
        source(identity, index + 1)
        for index, identity in enumerate(["a", "b", "c", "d"])
    ]
    original = EvidenceIntelligence(
        model="jev",
        version="1",
        status="complete",
        video_relationships=[pair("a", other) for other in ["b", "c", "d"]],
    )
    result = asyncio.run(
        review_uncertain_views(
            provider,
            sources,
            {item.source_id: tmp_path for item in sources},
            [],
            original,
            JsonCache(tmp_path),
            "test",
        )
    )
    assert provider.calls == 2
    assert "detailed_view_review_budget_limited" in result.diagnostics


def test_uncertain_or_repeated_footage_cannot_claim_event_matches():
    from rewind.analysis.view_review import _validate

    review = _Review(
        relationship="uncertain",
        confidence=0.4,
        basis="Insufficient distinctive overlap.",
        matches=[{"event_a": "a-0", "event_b": "b-0", "probability": 0.5}],
    )
    with pytest.raises(ValueError):
        _validate(review, {"a-0": "a"}, {"b-0": "b"})
