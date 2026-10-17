import type { Analysis, AnalysisRevision, Case, MediaFile } from '../types/generated'

export interface ReconstructionView {
  analysis: Analysis | null
  revision: number | null
  sourceIds: string[]
  media: MediaFile[]
  historical: boolean
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
  return snapshot
    ? {
        analysis: snapshot.analysis,
        revision: snapshot.revision,
        sourceIds: snapshot.media_source_ids,
        media: snapshot.media_files.length
          ? snapshot.media_files
          : incident.media_files.filter((source) =>
              snapshot.media_source_ids.includes(source.source_id),
            ),
        historical: true,
      }
    : {
        analysis: incident.analysis,
        revision: incident.analyzed_revision,
        sourceIds: incident.analyzed_source_ids,
        media: incident.media_files,
        historical: false,
      }
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
