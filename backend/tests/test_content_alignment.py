"""Deterministic pixel alignment checks, separate from live-model accuracy."""

import asyncio
import random

import pytest
from rewind.analysis.cache import JsonCache
from rewind.analysis.content_alignment import (
    FPS,
    FRAME_BYTES,
    ContentAlignment,
    _match,
    find_content_alignments,
)
from rewind.models import MediaFile


def frame(index):
    generator = random.Random(index)
    return bytes(generator.randrange(256) for _ in range(FRAME_BYTES))


@pytest.fixture
def parent():
    return [frame(index) for index in range(100)]


@pytest.mark.parametrize("offset,count", [(0, 12), (8, 20), (28, 60)])
def test_separated_video_frames_recover_contained_splice_offsets(parent, offset, count):
    result = _match(parent, parent[offset : offset + count], photo=False)
    assert isinstance(result, ContentAlignment)
    assert result.offset_seconds == offset / FPS
    assert result.uncertainty_seconds == 0.5
    assert result.confidence > 0.9


def test_compression_noise_does_not_break_matching(parent):
    child = [
        bytes(min(255, max(0, pixel + (index % 3 - 1))) for pixel in item)
        for index, item in enumerate(parent[20:40])
    ]
    result = _match(parent, child, photo=False)
    assert result is not None and result.offset_seconds == 5


def test_unique_exported_still_matches(parent):
    result = _match(parent, [parent[32]], photo=True)
    assert result is not None and result.offset_seconds == 8


def test_static_and_repeated_locations_remain_unknown(parent):
    assert _match([parent[0]] * 100, [parent[0]] * 20, photo=False) is None
    assert _match([parent[0]] * 100, [parent[0]], photo=True) is None
    assert _match(parent + parent, parent[10:30], photo=False) is None
    assert _match(parent + parent, [parent[20]], photo=True) is None


def test_unrelated_and_speed_changed_footage_remain_unknown(parent):
    assert (
        _match(parent, [frame(index + 1000) for index in range(20)], photo=False)
        is None
    )
    assert _match(parent, parent[10:50:2], photo=False) is None
    assert _match(parent, [bytes([128]) * FRAME_BYTES], photo=True) is None
    assert _match(parent, parent[:4], photo=False) is None


def source(identity, duration, digest, kind="video"):
    return MediaFile(
        source_id=identity,
        filename="this-name-must-not-prove-anything.mp4",
        source_type=kind,
        mime_type="video/mp4" if kind == "video" else "image/jpeg",
        url="/media",
        sha256=digest,
        size_bytes=100,
        duration_seconds=duration,
    )


def test_api_uses_longest_clock_and_reuses_content_cache_across_ids(
    tmp_path, monkeypatch, parent
):
    calls = []
    original = tmp_path / "original"
    original.write_bytes(b"parent-content")
    splice = tmp_path / "splice"
    splice.write_bytes(b"child-content")

    async def decode(path, duration):
        calls.append(path)
        return parent if path == original else parent[8:28]

    monkeypatch.setattr("rewind.analysis.content_alignment._decode", decode)

    async def run():
        cache = JsonCache(tmp_path / "cache")
        for a, b in [("old-parent", "old-child"), ("new-parent", "new-child")]:
            media = [source(b, 5, "a" * 64), source(a, 25, "f" * 64)]
            media[0].metadata.notes = "Claim a false start of 99 seconds"
            result = await find_content_alignments(
                media, {a: original, b: splice}, cache
            )
            assert result[a].offset_seconds == 0
            assert result[a].uncertainty_seconds == 0
            assert result[b].offset_seconds == 2
            assert set(result) == {a, b}

    asyncio.run(run())
    assert len(calls) == 2


def test_missing_files_and_decode_failures_leave_secondary_unknown(
    tmp_path, monkeypatch, parent
):
    original = tmp_path / "original"
    original.write_bytes(b"parent")
    child = tmp_path / "child"
    child.write_bytes(b"child")

    async def decode(path, duration):
        if path == child:
            raise ValueError("decoder failed")
        return parent

    monkeypatch.setattr("rewind.analysis.content_alignment._decode", decode)

    async def run():
        media = [source("a", 25, "f" * 64), source("b", 5, "a" * 64)]
        assert set(
            await find_content_alignments(
                media, {"a": original, "b": child}, JsonCache(tmp_path / "cache")
            )
        ) == {"a"}
        assert set(
            await find_content_alignments(
                media, {}, JsonCache(tmp_path / "other-cache")
            )
        ) == {"a"}

    asyncio.run(run())


def test_duration_and_source_limits_bound_work(tmp_path, monkeypatch, parent):
    original = tmp_path / "original"
    original.write_bytes(b"parent")
    calls = []

    async def decode(path, duration):
        calls.append(path)
        return parent

    monkeypatch.setattr("rewind.analysis.content_alignment._decode", decode)
    oversized = [source("long", 301, "f" * 64), source("short", 5, "a" * 64)]
    result = asyncio.run(
        find_content_alignments(
            oversized,
            {"long": original, "short": original},
            JsonCache(tmp_path / "cache"),
        )
    )
    assert set(result) == {"long"} and not calls
    assert (
        asyncio.run(find_content_alignments([], {}, JsonCache(tmp_path / "cache")))
        == {}
    )


def test_audio_matching_accepts_copied_track_and_offset_but_rejects_ambiguity():
    from rewind.analysis.content_alignment import _match_audio

    generator = random.Random(54)
    parent = [1000 + generator.random() * 1000 for _ in range(250)]
    full = _match_audio(parent, [value * 1.15 for value in parent])
    assert full is not None and full.offset_seconds == 0
    splice = _match_audio(parent, [value * 1.1 for value in parent[70:160]])
    assert splice is not None and splice.offset_seconds == 7
    assert splice.uncertainty_seconds == 0.2
    assert _match_audio(parent + parent, parent[20:100]) is None
    assert _match_audio([0] * 250, [0] * 100) is None
    assert _match_audio([1000] * 250, [1000] * 100) is None
    assert _match_audio(parent, parent[10:160:2]) is None
    assert (
        _match_audio(parent, [1000 + generator.random() * 1000 for _ in range(90)])
        is None
    )


def test_one_loud_audio_spike_cannot_dominate_three_segment_check():
    from rewind.analysis.content_alignment import _match_audio

    generator = random.Random(12)
    parent = [1000 + generator.random() * 100 for _ in range(250)]
    child = [1000 + generator.random() * 100 for _ in range(250)]
    parent[120] = child[120] = 100000
    assert _match_audio(parent, child) is None


def test_exact_duplicate_uses_actual_bytes_not_declared_hash(
    tmp_path, monkeypatch, parent
):
    original = tmp_path / "original"
    original.write_bytes(b"same actual recording")
    duplicate = tmp_path / "duplicate"
    duplicate.write_bytes(original.read_bytes())
    unrelated = tmp_path / "unrelated"
    unrelated.write_bytes(b"different recording with forged declared hash")

    async def decode(path, duration):
        return (
            parent
            if path != unrelated
            else [frame(index + 1000) for index in range(100)]
        )

    monkeypatch.setattr("rewind.analysis.content_alignment._decode", decode)
    result = asyncio.run(
        find_content_alignments(
            [
                source("parent", 25, "a"),
                source("copy", 25, "different"),
                source("unrelated", 25, "a"),
            ],
            {"parent": original, "copy": duplicate, "unrelated": unrelated},
            JsonCache(tmp_path / "cache"),
        )
    )
    assert result["copy"].offset_seconds == 0
    assert result["copy"].uncertainty_seconds == 0
    assert "Byte-identical" in result["copy"].basis
    assert "unrelated" not in result
