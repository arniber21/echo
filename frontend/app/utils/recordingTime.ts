export interface RecordingTimeParts {
  date: string
  time: string
}

function validDate(value: string): boolean {
  const [year, month, day] = value.split('-').map(Number)
  if (!year || !month || !day || month > 12 || year > 9999) return false
  const leap = year % 4 === 0 && (year % 100 !== 0 || year % 400 === 0)
  const days = [31, leap ? 29 : 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
  return day <= (days[month - 1] ?? 0)
}

/** Deliberately exclude offsets, prose and browser-dependent Date parsing. */
export function parseRecordingTime(value: string): RecordingTimeParts | null {
  if (!value) return { date: '', time: '' }
  const match = /^(\d{4}-\d{2}-\d{2})(?:T((?:[01]\d|2[0-3]):[0-5]\d(?::[0-5]\d)?))?$/.exec(value)
  if (!match?.[1] || !validDate(match[1])) return null
  return { date: match[1], time: match[2] ?? '' }
}

export function serializeRecordingTime(parts: RecordingTimeParts): string {
  return parts.date ? `${parts.date}${parts.time ? `T${parts.time}` : ''}` : ''
}
