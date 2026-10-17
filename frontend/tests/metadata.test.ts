import { describe, expect, test } from 'bun:test'
import { locationCoordinates, locationValue, mapUrls } from '../app/utils/location'
import { parseRecordingTime, serializeRecordingTime } from '../app/utils/recordingTime'

describe('reported recording time', () => {
  test('round trips local date/time and seconds without inventing a timezone', () => {
    for (const value of ['', '2026-10-17', '2026-10-17T14:30', '2026-10-17T14:30:45']) {
      const parsed = parseRecordingTime(value)
      expect(parsed).not.toBeNull()
      if (parsed) expect(serializeRecordingTime(parsed)).toBe(value)
    }
  })
  test('preserves unsupported legacy and offset values instead of silently converting', () => {
    for (const value of [
      'Oct 17, around 2 pm PDT',
      '2026-10-17T14:30:00Z',
      '2026-10-17T14:30-07:00',
      '2026-02-29',
      '2026-13-01',
      '2026-10-17T25:00',
    ])
      expect(parseRecordingTime(value)).toBeNull()
    expect(parseRecordingTime('2024-02-29')).toEqual({ date: '2024-02-29', time: '' })
  })
  test('clearing a date clears its associated time', () => {
    expect(serializeRecordingTime({ date: '', time: '14:30' })).toBe('')
  })
})

test('selected place survives the existing location string contract with a bounded value', () => {
  const place = {
    label: 'Market St, San Francisco, California, United States',
    latitude: 37.774929,
    longitude: -122.419416,
  }
  const value = locationValue(place)
  expect(locationCoordinates(value)).toEqual({
    latitude: place.latitude,
    longitude: place.longitude,
  })
  expect(locationValue({ ...place, label: 'a'.repeat(400) }).length).toBeLessThanOrEqual(240)
  expect(locationCoordinates('Main St & 3rd Ave')).toBeNull()
  expect(locationCoordinates('Bad (91, 1)')).toBeNull()
  expect(mapUrls(place).embed).toContain('openstreetmap.org/export/embed.html?')
  expect(mapUrls(place).full).toContain('mlat=37.774929')
})
