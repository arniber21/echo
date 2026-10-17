from pathlib import Path

from rewind.intelligence.models import (
    EvidenceIntelligence,
    FrameAssessment,
    SourceIntelligence,
)
from rewind.intelligence.preview import classification_preview
from rewind.models import Case


def fixture_case():
    return Case.model_validate_json(
        (Path(__file__).parents[2] / "shared/sample_case.json").read_text()
    )


def test_preview_uses_source_clocks_and_keeps_secondary_placements_unknown():
    case = fixture_case()
    video, _, photo = case.media_files[:3]
    second = video.model_copy(update={"source_id": "secondary", "sha256": "z" * 64})
    case.media_files = [video, second, photo]
    report = EvidenceIntelligence(
        model="jev-1.14.0",
        version="test",
        status="complete",
        sources=[
            SourceIntelligence(
                source_id=video.source_id,
                frames=[
                    FrameAssessment(
                        source_time=3.25, signals={"vehicle_contact_visible": 0.9}
                    )
                ],
            ),
            SourceIntelligence(
                source_id=second.source_id,
                frames=[
                    FrameAssessment(source_time=7.25, signals={"vehicle_visible": 0.95})
                ],
            ),
            SourceIntelligence(
                source_id=photo.source_id,
                frames=[FrameAssessment(signals={"damage_visible": 0.92})],
            ),
        ],
    )
    before = case.model_dump_json()
    preview = classification_preview(case, report)
    assert case.model_dump_json() == before
    assert preview.evidence_revision == case.evidence_revision
    primary, secondary, still = preview.analysis.events
    assert primary.case_best == primary.source_start == 3.25
    assert primary.source_end == 3.25
    assert secondary.source_start == 7.25
    assert secondary.case_best == 0 and secondary.case_max is None
    assert secondary.alignment_confidence == 0
    assert still.source_start is None and still.case_max is None
    assert all(event.evidence_type == "inference" for event in preview.analysis.events)
    assert "Unsampled intervals" in preview.analysis.summary[0].text


def test_low_classifier_scores_do_not_claim_absence_or_discard_a_source():
    case = fixture_case()
    report = EvidenceIntelligence(
        model="jev-1.14.0",
        version="test",
        status="partial",
        sources=[
            SourceIntelligence(
                source_id=case.media_files[0].source_id,
                frames=[
                    FrameAssessment(
                        source_time=1, signals={"vehicle_contact_visible": 0.05}
                    )
                ],
            ),
        ],
    )
    preview = classification_preview(case, report)
    assert preview is not None and preview.analysis.events == []
    assert (
        preview.analysis.summary[0].source_refs[0].source_id
        == case.media_files[0].source_id
    )
    assert "no collision" not in preview.analysis.summary[0].text.lower()
    report.sources = []
    assert classification_preview(case, report) is None
