from datetime import UTC, datetime

import pytest

from rewind.memory import project_memory
from rewind.models import Analysis, Claim, Finding, SourceRef

NOW = datetime(2026, 10, 17, tzinfo=UTC)


def analysis(text: str) -> Analysis:
    return Analysis(events=[], summary=[Claim(text=text, source_refs=[SourceRef(source_id="video")])])


def test_unchanged_claims_retain_identity_without_duplicate_storage():
    first = project_memory(None, analysis("A car is visible."), 1, NOW)
    second = project_memory(first, analysis("A car is visible."), 2, NOW)
    assert len(second.entries) == 1
    assert first.summary_entry_ids == second.summary_entry_ids
    assert second.entries[0].first_revision == 1
    assert second.entries[0].last_revision == 2
    assert first.entries[0].last_revision == 1  # No mutation of previous account.


def test_replaced_claims_remain_superseded_and_new_claims_have_new_identity():
    first = project_memory(None, analysis("The color is unclear."), 1, NOW)
    second = project_memory(first, analysis("The source shows an amber car."), 2, NOW)
    assert len(second.entries) == 2
    assert second.entries[0].status == "superseded"
    assert second.entries[0].last_revision == 1
    assert second.entries[1].status == "active"
    assert second.entries[1].first_revision == 2
    assert second.summary_entry_ids == [second.entries[1].entry_id]
    assert first.entries[0].status == "active"


def test_ref_order_does_not_change_identity_but_source_time_does():
    refs = [SourceRef(source_id="video", source_start=8), SourceRef(source_id="audio", source_start=6)]
    value = Analysis(events=[], summary=[Claim(text="Accounts disagree.", source_refs=refs)])
    first = project_memory(None, value, 1, NOW)
    value.summary[0].source_refs.reverse()
    second = project_memory(first, value, 2, NOW)
    assert len(second.entries) == 1
    value.summary[0].source_refs[0].source_start = 7
    third = project_memory(second, value, 3, NOW)
    assert len(third.entries) == 2
    assert len([entry for entry in third.entries if entry.status == "active"]) == 1


def test_questions_and_conflicts_are_explicit_and_revision_cannot_rewind():
    value = analysis("Contact is visible.")
    value.missing_evidence = [Finding(id="gap", title="Other view", description="A second view is missing.")]
    first = project_memory(None, value, 2, NOW)
    assert {entry.kind for entry in first.entries} == {"summary", "question"}
    with pytest.raises(ValueError, match="backwards"):
        project_memory(first, value, 1, NOW)
