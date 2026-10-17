import { describe, expect, test } from 'bun:test'
import type { Analysis, Case, EvidenceIntelligence, MediaFile } from '../app/types/generated'
import { emptySourceMetadata, sourceDetailsChanged } from '../app/utils/evidence'
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
  metadata: emptySourceMetadata(),
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
    analyzed_media_files: [video],
    analysis_history: [],
    memory: null,
    intelligence: null,
    preview: null,
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
      {
        revision: 1,
        created_at: '2026-10-17T00:01:00Z',
        media_source_ids: ['video'],
        media_count: 1,
        media_files: [video],
        analysis,
        intelligence: null,
      },
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
      {
        revision: 1,
        created_at: '2026-10-17T00:01:00Z',
        media_source_ids: ['video'],
        media_count: 1,
        media_files: [video],
        analysis,
        intelligence: null,
      },
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

test('metadata-only changes need an update even when no new source was added', () => {
  const value = incident()
  value.media_files = [video]
  expect(pendingSourceIds(value)).toEqual([])
  expect(sourceDetailsChanged(value, 0)).toBe(true)
})

test('previous snapshots retain the original source annotations', () => {
  const value = incident()
  value.media_files = [
    { ...video, metadata: { ...emptySourceMetadata(), location: 'Updated location' } },
  ]
  value.analysis_history = [
    {
      revision: 1,
      created_at: '2026-10-17T00:01:00Z',
      media_source_ids: ['video'],
      media_count: 1,
      media_files: [video],
      analysis,
      intelligence: null,
    },
  ]
  expect(reconstructionView(value, 1).media[0]?.metadata.location).toBe('')
  expect(reconstructionView(value, null).media[0]?.metadata.location).toBe('Updated location')
})

test('new intake files have independent metadata values', () => {
  const first = emptySourceMetadata()
  const second = emptySourceMetadata()
  first.label = 'Front camera'
  expect(second.label).toBe('')
})

const signals: EvidenceIntelligence = {
  model: 'jev-1.14.0',
  version: 'test',
  status: 'complete',
  sources: [],
  claims: [],
  input_tokens: 10,
  elapsed_seconds: 1,
  diagnostics: [],
}

test('historical evidence signals never fall back to the current reconstruction', () => {
  const value = incident()
  value.intelligence = signals
  value.analysis_history = [
    {
      revision: 1,
      created_at: '2026-10-17T00:01:00Z',
      media_source_ids: ['video'],
      media_count: 1,
      media_files: [video],
      analysis,
      intelligence: null,
    },
  ]
  expect(reconstructionView(value, null).intelligence).toBe(signals)
  expect(reconstructionView(value, 1).intelligence).toBeNull()
  value.analysis_history[0]!.intelligence = { ...signals, version: 'older' }
  expect(reconstructionView(value, 1).intelligence?.version).toBe('older')
})

test('a quick scan fills an empty current view without replacing accepted analysis or history', () => {
  const value = incident()
  const previewAnalysis: Analysis = { ...analysis, notice: 'Quick scan' }
  value.preview = {
    evidence_revision: value.evidence_revision,
    created_at: value.created_at,
    analysis: previewAnalysis,
    intelligence: signals,
  }
  // Existing accepted results remain the primary view.
  expect(reconstructionView(value, null).analysis).toBe(analysis)
  expect(reconstructionView(value, null).quickScan).toBe(false)
  value.analysis_history = [
    {
      revision: 1,
      created_at: value.created_at,
      media_source_ids: ['video'],
      media_count: 1,
      media_files: [video],
      analysis,
      intelligence: null,
    },
  ]
  expect(reconstructionView(value, 1).intelligence).toBeNull()
  expect(reconstructionView(value, 1).quickScan).toBe(false)
  value.analysis = null
  expect(reconstructionView(value, null).analysis).toBe(previewAnalysis)
  expect(reconstructionView(value, null).intelligence).toBe(signals)
  expect(reconstructionView(value, null).quickScan).toBe(true)
  value.evidence_revision += 1
  expect(reconstructionView(value, null).analysis).toBeNull()
  expect(reconstructionView(value, null).quickScan).toBe(false)
})
