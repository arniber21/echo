import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from rewind.analysis import AnalysisSettings, analyze
from rewind.analysis import pipeline
from rewind.analysis.cache import JsonCache
from rewind.analysis.provider import GeminiProvider, InvalidModelOutput
from rewind.analysis.types import ExtractedEvent, Extraction
from rewind.analysis.validation import validate_extraction, validate_synthesis
from rewind.models import Analysis, Case, Event


@pytest.fixture
def case():
    return Case.model_validate_json((Path(__file__).parents[2] / "shared/sample_case.json").read_text())


class FakeProvider:
    calls = []

    def __init__(self, settings):
        pass

    async def close(self):
        pass

    async def generate(self, prompt, schema, *, path=None, mime_type=None, validate=None):
        self.calls.append((schema.__name__, mime_type))
        if schema is Extraction:
            is_photo = mime_type.startswith("image/")
            result = Extraction(events=[ExtractedEvent(
                title="Visible marker", description="A test marker",
                source_start=None if is_photo else 1,
                source_end=None if is_photo else 2,
                evidence_type="testimony" if mime_type.startswith("audio/") else "observation", confidence=0.7,
            )], limitations=[])
        else:
            records = json.loads(prompt.split("Input:\n")[1])
            result = Analysis(events=[Event(
                **event, case_min=0.5 if record["source_type"] == "video" else 0,
                case_best=1, case_max=1.5 if record["source_type"] == "video" else None,
                alignment_basis="Test only", alignment_confidence=0.2, verification_status="unverified",
            ) for record in records for event in record["events"]], summary=[])
        if validate:
            validate(result)
        return result


def test_cache_remaps_ids_and_uses_content_and_role(case, tmp_path, monkeypatch):
    FakeProvider.calls = []
    monkeypatch.setattr(pipeline, "GeminiProvider", FakeProvider)
    paths = {}
    for source in case.media_files:
        path = tmp_path / source.filename
        path.write_bytes(b"same test bytes")
        paths[source.source_id] = path
    settings = AnalysisSettings(api_key="test", mode="live", cache_dir=tmp_path / "cache")
    progress = AsyncMock()
    first = asyncio.run(analyze(case, paths, progress, settings=settings))
    # Equal photo contents share extraction, but audio and video roles never do.
    assert FakeProvider.calls == [("Extraction", "video/mp4"), ("Extraction", "audio/mp4"), ("Extraction", "image/jpeg"), ("Analysis", None)]
    assert first.mode == "live"
    renamed = case.model_copy(deep=True)
    renamed_paths = {}
    for source in renamed.media_files:
        old_id = source.source_id
        source.source_id = "new-" + old_id
        renamed_paths[source.source_id] = paths[old_id]
    second = asyncio.run(analyze(renamed, renamed_paths, progress, settings=settings))
    assert second.mode == "cached"
    assert len(FakeProvider.calls) == 4
    assert {event.source_id for event in second.events} == set(renamed_paths)
    assert all(event.source_start == 1 for event in second.events if event.source_type.value != "photo")
    # Changing the model invalidates both extraction and synthesis.
    asyncio.run(analyze(case, paths, progress, settings=AnalysisSettings(api_key="test", model="different", cache_dir=tmp_path / "cache")))
    assert len(FakeProvider.calls) == 8


def test_mock_discloses_uninspected_arbitrary_uploads(case):
    result = asyncio.run(analyze(case, {}, AsyncMock(), settings=AnalysisSettings(mode="mock")))
    assert result.mode == "mock"
    assert "SIMULATED" in result.notice
    assert all(event.confidence == 0 and "not been inspected" in event.description for event in result.events)
    assert result.contradictions == []


def test_corrupt_cache_is_a_miss(tmp_path):
    (tmp_path / "bad.json").write_text("{truncated")
    assert JsonCache(tmp_path).read("bad", Extraction) is None


def test_extraction_rejects_wrong_clocks_and_photo_times(case):
    invalid = Extraction(events=[ExtractedEvent(title="x", description="x", source_start=100, source_end=101, evidence_type="observation", confidence=.5)], limitations=[])
    with pytest.raises(ValueError, match="duration"):
        validate_extraction(invalid, case.media_files[0])
    with pytest.raises(ValueError, match="seek times"):
        validate_extraction(invalid, case.media_files[2])


def test_synthesis_cannot_change_source_seek_times(case):
    video = case.media_files[0]
    extraction = Extraction(events=[ExtractedEvent(title="x", description="x", source_start=1, source_end=2, evidence_type="observation", confidence=.5)], limitations=[])
    event = Event(event_id=f"event-{video.source_id}-0", source_id=video.source_id, source_type="video", title="x", description="x", source_start=7, source_end=8, case_min=6.5, case_best=7, case_max=7.5, alignment_basis="x", alignment_confidence=.9, confidence=.9, evidence_type="observation")
    with pytest.raises(ValueError, match="changed source"):
        validate_synthesis(Analysis(events=[event], summary=[]), [video], {video.source_id: extraction})


def provider_with_responses(responses):
    provider = object.__new__(GeminiProvider)
    provider.settings = AnalysisSettings(api_key="test")
    provider.client = SimpleNamespace(aio=SimpleNamespace(
        models=SimpleNamespace(generate_content=AsyncMock(side_effect=[SimpleNamespace(text=text) for text in responses])),
        files=SimpleNamespace(
            upload=AsyncMock(return_value=SimpleNamespace(name="files/1", state=SimpleNamespace(name="ACTIVE"), uri="file://1", mime_type="video/mp4")),
            delete=AsyncMock(),
        ),
    ))
    return provider


def test_provider_retries_invalid_json_once_and_deletes_upload(tmp_path):
    provider = provider_with_responses(["not json", '{"events":[],"limitations":[]}'])
    result = asyncio.run(provider.generate("inspect", Extraction, path=tmp_path / "video.mp4", mime_type="video/mp4"))
    assert result.events == []
    assert provider.client.aio.models.generate_content.await_count == 2
    provider.client.aio.files.delete.assert_awaited_once_with(name="files/1")


def test_provider_sends_json_schema_without_legacy_schema_conversion():
    provider = provider_with_responses(['{"events":[],"limitations":[]}'])
    asyncio.run(provider.generate("inspect", Extraction))
    config = provider.client.aio.models.generate_content.call_args.kwargs["config"]
    assert config.response_schema is None
    assert config.response_json_schema == Extraction.model_json_schema()
    assert config.response_json_schema["additionalProperties"] is False


def test_provider_domain_invalid_output_retries_and_fails():
    provider = provider_with_responses(['{"events":[],"limitations":[]}'] * 2)

    def reject(result):
        raise ValueError("bad source reference")

    with pytest.raises(InvalidModelOutput):
        asyncio.run(provider.generate("inspect", Extraction, validate=reject))
    assert provider.client.aio.models.generate_content.await_count == 2


def test_retry_feedback_identifies_safe_rule_without_echoing_input():
    provider = provider_with_responses(['{"events":[],"limitations":[]}'] * 2)

    def reject(result):
        raise ValueError("Synthesis changed source evidence or seek timestamps")

    with pytest.raises(InvalidModelOutput):
        asyncio.run(provider.generate("inspect", Extraction, validate=reject))
    second = provider.client.aio.models.generate_content.call_args_list[1]
    assert "Synthesis changed source evidence or seek timestamps" in second.kwargs["contents"][-1].text
    from rewind.analysis.provider import _validation_feedback
    assert "private-upload-data" not in _validation_feedback(ValueError("private-upload-data"))


def test_live_cli_errors_are_concise_and_redact_provider_details(monkeypatch, capsys):
    from rewind.analysis import check_live

    async def failure(root, fresh):
        raise RuntimeError("API key secret-provider-value")

    monkeypatch.setattr(check_live, "check", failure)
    monkeypatch.setattr("sys.argv", ["check_live"])
    with pytest.raises(SystemExit) as error:
        check_live.main()
    output = capsys.readouterr()
    assert error.value.code == 1
    assert "RuntimeError" in output.err
    assert "secret-provider-value" not in output.err
    assert "Traceback" not in output.err
