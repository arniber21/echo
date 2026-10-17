import type { FrameAssessment, MediaFile, SourceRef } from '../types/generated'

const signalLabels: Record<string, string> = {
  road_visible: 'Road visible',
  vehicle_visible: 'Vehicle visible',
  vehicle_contact_visible: 'Vehicle contact visible',
  damage_visible: 'Damage visible',
  obstructed: 'View obstructed',
}

export function signalLabel(key: string): string {
  return signalLabels[key] ?? key.replaceAll('_', ' ')
}

/** Avoid displaying rounded probabilities as absolute certainty. */
export function probabilityLabel(probability: number): string {
  if (!Number.isFinite(probability)) return 'Unavailable'
  if (probability < 0.01) return '<1%'
  if (probability > 0.99) return '>99%'
  return `${Math.round(probability * 100)}%`
}

/** Frame timestamps belong to the source clock; a photo never has a seek time. */
export function frameReference(source: MediaFile, frame: FrameAssessment): SourceRef {
  return {
    source_id: source.source_id,
    source_start: source.source_type === 'photo' ? null : frame.source_time,
    source_end: null,
  }
}
