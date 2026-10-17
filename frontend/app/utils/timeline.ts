import type { Event, MediaFile, SourceRef } from '../types/generated'

export function formatTime(seconds: number | null | undefined): string {
  if (seconds == null || !Number.isFinite(seconds)) return 'Time unknown'
  const sign = seconds < 0 ? '−' : ''
  const value = Math.round(Math.abs(seconds) * 10) / 10
  return `${sign}${Math.floor(value / 60)
    .toString()
    .padStart(2, '0')}:${(value % 60).toFixed(1).padStart(4, '0')}`
}

export function caseExtent(events: Event[], media: MediaFile[]): number {
  return Math.max(
    20,
    ...events.flatMap((event) => [event.case_best, event.case_max ?? event.case_best]),
    ...media
      .filter((file) => file.source_type === 'video')
      .map((file) => file.duration_seconds ?? 0),
  )
}

export function rangeStyle(event: Event, extent: number): Record<string, string> {
  const start = Math.max(0, event.case_min ?? 0)
  const end = Math.min(extent, event.case_max ?? extent)
  return {
    left: `${(100 * start) / extent}%`,
    width: `${Math.max(0.8, (100 * (end - start)) / extent)}%`,
  }
}

export function placementLabel(event: Event): string {
  if (event.case_max === null && event.source_type === 'photo')
    return 'Post-incident · time unknown'
  return `${event.case_min === null ? 'Open start' : formatTime(event.case_min)} – ${event.case_max === null ? 'Open end' : formatTime(event.case_max)}`
}

export function sourceLabel(ref: SourceRef, media: MediaFile[]): string {
  const file = media.find((item) => item.source_id === ref.source_id)
  return `${file?.filename ?? ref.source_id}${ref.source_start == null ? '' : ` · ${formatTime(ref.source_start)}`}`
}

/** Playback always uses the original file clock, never the estimated case clock. */
export function eventSourceReference(event: Event): SourceRef {
  return {
    source_id: event.source_id,
    source_start: event.source_start,
    source_end: event.source_end,
  }
}

/** Match the backend primary video choice independent of upload order. */
export function primaryVideo(media: MediaFile[]): MediaFile | undefined {
  return media
    .filter((file) => file.source_type === 'video')
    .sort((a, b) =>
      a.sha256 < b.sha256 ? -1 : a.sha256 > b.sha256 ? 1 : a.source_id.localeCompare(b.source_id),
    )[0]
}
