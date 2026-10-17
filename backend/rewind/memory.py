"""Persist a content-addressed working account without another model request.

Analysis is the evidence-validated input. This projection runs only when that
analysis is committed, never on uploads or reads. Exact repeated entries retain
their identity; replaced entries remain inspectable as superseded recollections.
"""

import hashlib
import json
from datetime import datetime

from rewind.models import Analysis, CaseMemory, MemoryEntry, SourceRef


def project_memory(
    previous: CaseMemory | None,
    analysis: Analysis,
    revision: int,
    updated_at: datetime,
) -> CaseMemory:
    if previous is not None and revision < previous.revision:
        raise ValueError("Working-account revision cannot move backwards")
    # Copy prior models: callers may still display a previous committed account.
    entries = (
        {
            entry.entry_id: entry.model_copy(update={"status": "superseded"})
            for entry in previous.entries
            if previous is not None
        }
        if previous is not None
        else {}
    )

    def remember(
        kind: str,
        text: str,
        refs: list[SourceRef],
        answer_refs: list[str] | None = None,
    ) -> str:
        normalized_text = " ".join(text.split())
        # Ordering of references is not a change to the claim's identity.
        normalized_refs = sorted(
            {
                ref.model_dump_json(): ref.model_dump(mode="json") for ref in refs
            }.values(),
            key=lambda ref: json.dumps(ref, sort_keys=True),
        )
        identity_data = {
            "kind": kind,
            "text": normalized_text,
            "source_refs": normalized_refs,
        }
        if answer_refs:
            identity_data["answer_refs"] = sorted(set(answer_refs))
        identity = json.dumps(
            identity_data,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
        entry_id = hashlib.sha256(identity.encode()).hexdigest()[:32]
        old = entries.get(entry_id)
        entries[entry_id] = MemoryEntry.model_validate(
            {
                "entry_id": entry_id,
                "kind": kind,
                "text": normalized_text,
                "source_refs": normalized_refs,
                "answer_refs": sorted(set(answer_refs or [])),
                "first_revision": old.first_revision if old else revision,
                "last_revision": revision,
                "status": "active",
            }
        )
        return entry_id

    summary_ids = list(
        dict.fromkeys(
            remember("summary", claim.text, claim.source_refs, claim.answer_refs)
            for claim in analysis.summary
        )
    )
    for event in analysis.events:
        remember(
            event.evidence_type,
            f"{event.title}: {event.description}",
            [
                SourceRef(
                    source_id=event.source_id,
                    source_start=event.source_start,
                    source_end=event.source_end,
                )
            ],
        )
    for kind, findings in (
        ("question", analysis.missing_evidence),
        ("conflict", analysis.contradictions),
    ):
        for finding in findings:
            remember(
                kind,
                f"{finding.title}: {finding.description}",
                finding.source_refs,
                finding.answer_refs,
            )
    return CaseMemory(
        revision=revision,
        updated_at=updated_at,
        entries=list(entries.values()),
        summary_entry_ids=summary_ids,
    )
