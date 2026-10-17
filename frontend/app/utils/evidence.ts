import type { Case, SourceMetadata } from '../types/generated'

export function emptySourceMetadata(): SourceMetadata {
  return { label: '', recorded_by: '', location: '', recorded_at: '', notes: '' }
}

export function sourceDetailsChanged(
  incident: Pick<Case, 'analysis' | 'evidence_revision' | 'analyzed_revision'>,
  newSourceCount: number,
): boolean {
  return Boolean(
    incident.analysis &&
    incident.analyzed_revision !== incident.evidence_revision &&
    newSourceCount === 0,
  )
}
