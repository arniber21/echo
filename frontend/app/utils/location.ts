export interface Place {
  label: string
  latitude: number
  longitude: number
}

export function locationValue(place: Place): string {
  return `${place.label.slice(0, 200)} (${place.latitude.toFixed(6)}, ${place.longitude.toFixed(6)})`
}

export function locationCoordinates(value: string): { latitude: number; longitude: number } | null {
  const match = /\((-?\d+(?:\.\d+)?),\s*(-?\d+(?:\.\d+)?)\)$/.exec(value)
  if (!match) return null
  const latitude = Number(match[1])
  const longitude = Number(match[2])
  return Math.abs(latitude) <= 90 && Math.abs(longitude) <= 180 ? { latitude, longitude } : null
}

export function mapUrls(point: { latitude: number; longitude: number }) {
  const { latitude, longitude } = point
  const bbox = [
    Math.max(-180, longitude - 0.008),
    Math.max(-90, latitude - 0.005),
    Math.min(180, longitude + 0.008),
    Math.min(90, latitude + 0.005),
  ].join(',')
  return {
    embed: `https://www.openstreetmap.org/export/embed.html?${new URLSearchParams({ bbox, layer: 'mapnik', marker: `${latitude},${longitude}` })}`,
    full: `https://www.openstreetmap.org/?mlat=${latitude}&mlon=${longitude}#map=17/${latitude}/${longitude}`,
  }
}
