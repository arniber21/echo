import type {
  Analysis,
  AnalysisRevision,
  Case,
  CaseAnswer,
  EvidenceIntelligence,
  MediaFile,
} from '../types/generated'

export interface ReconstructionView {
  analysis: Analysis | null
  intelligence: EvidenceIntelligence | null
  revision: number | null
  sourceIds: string[]
  media: MediaFile[]
  answers: CaseAnswer[]
  citationAnswers: CaseAnswer[]
  historical: boolean
  quickScan: boolean
}

export interface ReconstructionDelta {
  previousRevision: number
  addedSources: number
  events: number
  missingEvidence: number
  contradictions: number
}

export function pendingSourceIds(incident: Case): string[] {
  const analyzedIds = new Set(incident.analyzed_source_ids)
  return incident.media_files
    .filter((source) => !analyzedIds.has(source.source_id))
    .map((source) => source.source_id)
}

export function reconstructionView(
  incident: Case,
  selectedRevision: number | null,
): ReconstructionView {
  const snapshot =
    selectedRevision === null
      ? undefined
      : incident.analysis_history.find((item) => item.revision === selectedRevision)
  const preview = currentPreview(incident)
  return snapshot
    ? {
        analysis: snapshot.analysis,
        intelligence: snapshot.intelligence ?? null,
        revision: snapshot.revision,
        sourceIds: snapshot.media_source_ids,
        media: snapshot.media_files.length
          ? snapshot.media_files
          : incident.media_files.filter((source) =>
              snapshot.media_source_ids.includes(source.source_id),
            ),
        answers: snapshot.answers,
        citationAnswers: snapshot.answers,
        historical: true,
        quickScan: false,
      }
    : {
        analysis: incident.analysis ?? preview?.analysis ?? null,
        intelligence: incident.analysis
          ? (incident.intelligence ?? null)
          : (preview?.intelligence ?? incident.intelligence ?? null),
        revision: incident.analyzed_revision,
        sourceIds: incident.analysis
          ? incident.analyzed_source_ids
          : preview
            ? incident.media_files.map((source) => source.source_id)
            : incident.analyzed_source_ids,
        media: incident.media_files,
        answers: incident.answers,
        citationAnswers: incident.analyzed_answers,
        historical: false,
        quickScan: !incident.analysis && Boolean(preview),
      }
}

/** Preview results only describe the evidence revision they were computed against. */
export function currentPreview(incident: Case) {
  return incident.preview?.evidence_revision === incident.evidence_revision
    ? incident.preview
    : null
}

/** Count changes describe the size of each result, not semantic additions or removals. */
export function reconstructionDelta(incident: Case): ReconstructionDelta | null {
  if (!incident.analysis || incident.analyzed_revision === null) return null
  const analyzedRevision = incident.analyzed_revision
  const previous = [...incident.analysis_history]
    .filter((snapshot) => snapshot.revision < analyzedRevision)
    .sort((a, b) => b.revision - a.revision)[0]
  if (!previous) return null
  return {
    previousRevision: previous.revision,
    addedSources: incident.analyzed_source_ids.filter(
      (id) => !previous.media_source_ids.includes(id),
    ).length,
    events: incident.analysis.events.length - previous.analysis.events.length,
    missingEvidence:
      incident.analysis.missing_evidence.length - previous.analysis.missing_evidence.length,
    contradictions:
      incident.analysis.contradictions.length - previous.analysis.contradictions.length,
  }
}

export function historyNewestFirst(history: AnalysisRevision[]): AnalysisRevision[] {
  return [...history].sort((a, b) => b.revision - a.revision)
}

export function formatCountChange(count: number): string {
  return count > 0 ? `+${count}` : count < 0 ? `−${Math.abs(count)}` : 'unchanged'
}
