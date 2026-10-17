import { describe, expect, test } from 'bun:test'
import type { Analysis, Case, MediaFile } from '../app/types/generated'
import {
  formatCountChange,
  pendingSourceIds,
  reconstructionDelta,
  reconstructionView,
} from '../app/utils/revisions'

const analysis: Analysis = {
  events: [],
  summary: [],
  missing_evidence: [],
  contradictions: [],
  mode: 'mock',
  notice: 'Simulated analysis.',
}
const video: MediaFile = {
  source_id: 'video',
  filename: 'video.mp4',
  source_type: 'video',
  mime_type: 'video/mp4',
  url: '/api/media/video',
  sha256: 'a',
  size_bytes: 100,
  duration_seconds: 20,
  captured_at: null,
}
const photo: MediaFile = {
  ...video,
  source_id: 'photo',
  filename: 'photo.jpg',
  source_type: 'photo',
  mime_type: 'image/jpeg',
  url: '/api/media/photo',
  sha256: 'b',
  duration_seconds: null,
}
function incident(): Case {
  return {
    case_id: 'test',
    title: 'Progressive reconstruction',
    created_at: '2026-10-17T00:00:00Z',
    media_files: [video, photo],
    analysis,
    evidence_revision: 2,
    analyzed_revision: 1,
    analyzed_at: '2026-10-17T00:01:00Z',
    analyzed_source_ids: ['video'],
    analysis_history: [],
    memory: null,
  }
}

describe('progressive reconstruction', () => {
  test('new media stays pending without rewriting the existing reconstruction', () => {
    const value = incident()
    expect(pendingSourceIds(value)).toEqual(['photo'])
    const view = reconstructionView(value, null)
    expect(view.analysis).toBe(analysis)
    expect(view.sourceIds).toEqual(['video'])
    expect(view.media).toHaveLength(2)
    expect(view.historical).toBe(false)
  })
  test('an older snapshot shows only the evidence available at that time', () => {
    const value = incident()
    value.analysis_history = [
      { revision: 1, created_at: '2026-10-17T00:01:00Z', media_source_ids: ['video'], analysis },
    ]
    const view = reconstructionView(value, 1)
    expect(view.media.map((item) => item.source_id)).toEqual(['video'])
    expect(view.historical).toBe(true)
  })
  test('revision deltas compare counts instead of claiming semantic additions', () => {
    const value = incident()
    value.analyzed_revision = 2
    value.analyzed_source_ids = ['video', 'photo']
    value.analysis_history = [
      { revision: 1, created_at: '2026-10-17T00:01:00Z', media_source_ids: ['video'], analysis },
    ]
    expect(reconstructionDelta(value)).toEqual({
      previousRevision: 1,
      addedSources: 1,
      events: 0,
      missingEvidence: 0,
      contradictions: 0,
    })
    expect(pendingSourceIds(value)).toEqual([])
    expect(formatCountChange(-2)).toBe('−2')
    expect(formatCountChange(0)).toBe('unchanged')
    expect(formatCountChange(3)).toBe('+3')
  })
  test('an invalid history selection safely shows the current reconstruction', () => {
    expect(reconstructionView(incident(), 99).historical).toBe(false)
  })
})
