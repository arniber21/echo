import { expect, test } from 'bun:test'
import type { FrameAssessment, MediaFile } from '../app/types/generated'
import { emptySourceMetadata } from '../app/utils/evidence'
import {
  frameReference,
  probabilityLabel,
  relationshipLabel,
  signalLabel,
} from '../app/utils/intelligence'

const source: MediaFile = {
  source_id: 'video-2',
  filename: 'second-camera.mp4',
  source_type: 'video',
  mime_type: 'video/mp4',
  url: '/api/media/video-2',
  sha256: 'abc',
  size_bytes: 100,
  duration_seconds: 20,
  captured_at: null,
  metadata: emptySourceMetadata(),
}
const frame: FrameAssessment = {
  source_time: 3.25,
  signals: { vehicle_visible: 0.96 },
  vehicle_box: null,
  box_confidence: null,
  image_sha256: 'frame-hash',
  prepared_width: 1120,
  prepared_height: 630,
}

test('sampled frames seek their own source clock and photos do not seek', () => {
  expect(frameReference(source, frame)).toEqual({
    source_id: 'video-2',
    source_start: 3.25,
    source_end: null,
  })
  expect(frameReference({ ...source, source_type: 'photo' }, frame).source_start).toBeNull()
})

test('probability labels preserve uncertainty near zero and one', () => {
  expect(probabilityLabel(0)).toBe('<1%')
  expect(probabilityLabel(0.004)).toBe('<1%')
  expect(probabilityLabel(0.5)).toBe('50%')
  expect(probabilityLabel(0.996)).toBe('>99%')
  expect(probabilityLabel(1)).toBe('>99%')
  expect(probabilityLabel(Number.NaN)).toBe('Unavailable')
  expect(signalLabel('vehicle_contact_visible')).toBe('Vehicle contact visible')
  expect(signalLabel('new_signal')).toBe('new signal')
})

test('video relationship labels keep provisional assessments explicit', () => {
  expect(relationshipLabel('same_incident_different_view')).toBe(
    'Likely same incident · different viewpoint',
  )
  expect(relationshipLabel('uncertain')).toBe('Relationship uncertain')
  expect(relationshipLabel('same_footage')).toBe('Likely same footage')
  expect(relationshipLabel('different_incident')).toBe('Likely different incidents')
})
