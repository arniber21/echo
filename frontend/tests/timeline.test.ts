import { describe, expect, test } from 'bun:test'
import type { Event } from '../app/types/generated'
import {
  caseExtent,
  eventSourceReference,
  formatTime,
  placementLabel,
  rangeStyle,
} from '../app/utils/timeline'

const event: Event = {
  event_id: 'testimony-1',
  title: 'Impact recalled',
  description: 'A driver describes the impact.',
  source_id: 'voice',
  source_type: 'audio',
  source_start: 17,
  source_end: 20,
  case_min: 6,
  case_best: 8,
  case_max: 12,
  alignment_basis: 'Content match to the observed impact.',
  alignment_confidence: 0.5,
  confidence: 0.7,
  verification_status: 'unverified',
  evidence_type: 'testimony',
  supports: [],
}

describe('distinct source and case clocks', () => {
  test('seeks the audio statement at 17 seconds, while placing it at case second 8', () => {
    expect(eventSourceReference(event)).toEqual({
      source_id: 'voice',
      source_start: 17,
      source_end: 20,
    })
    expect(rangeStyle(event, 20)).toEqual({ left: '30%', width: '30%' })
  })
  test('preserves open-ended post-incident photos without inventing source timestamps', () => {
    const photo: Event = {
      ...event,
      source_type: 'photo',
      source_start: null,
      source_end: null,
      case_min: 8,
      case_max: null,
    }
    expect(eventSourceReference(photo).source_start).toBeNull()
    expect(placementLabel(photo)).toBe('Post-incident · time unknown')
    expect(rangeStyle(photo, 20)).toEqual({ left: '40%', width: '60%' })
  })
  test('extent includes distant testimony rather than hiding wide ranges', () => {
    expect(caseExtent([{ ...event, case_max: 120 }], [])).toBe(120)
  })
  test('clips pre-video uncertainty while keeping the label explicit', () => {
    const before = { ...event, case_min: null }
    expect(rangeStyle(before, 20).left).toBe('0%')
    expect(placementLabel(before)).toContain('Open start')
  })
  test('time labels distinguish unknown times and negative times', () => {
    expect(formatTime(null)).toBe('Time unknown')
    expect(formatTime(-1.5)).toBe('−00:01.5')
    expect(formatTime(83)).toBe('01:23.0')
  })
})
