import { expect, test } from '@playwright/test'
import { existsSync, readFileSync } from 'node:fs'
import { basename, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import type { Case, SourceMetadata } from '../../frontend/app/types/generated'

const directory = fileURLToPath(new URL('../../data/test-clips/', import.meta.url))
const manifestPath = resolve(directory, 'manifest.json')

interface Clip {
  filename: string
  duration: number
  hash: string
  metadata: SourceMetadata
}

function record(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function text(value: Record<string, unknown>, key: string): string {
  const result = value[key]
  if (typeof result !== 'string') throw new Error(`Invalid test dataset field: ${key}`)
  return result
}

function loadClips(): Clip[] {
  if (!existsSync(manifestPath)) return []
  const value: unknown = JSON.parse(readFileSync(manifestPath, 'utf8'))
  if (!record(value) || !Array.isArray(value.clips)) throw new Error('Invalid clip dataset manifest')
  return value.clips.map((entry: unknown) => {
    if (!record(entry) || !record(entry.source_metadata)) throw new Error('Invalid clip metadata')
    const filename = text(entry, 'filename')
    if (basename(filename) !== filename || !filename.endsWith('.mp4')) throw new Error('Invalid clip filename')
    if (typeof entry.duration_seconds !== 'number' || !Number.isFinite(entry.duration_seconds)) throw new Error('Invalid clip duration')
    const metadata = entry.source_metadata
    return {
      filename,
      duration: entry.duration_seconds,
      hash: text(entry, 'sha256'),
      metadata: {
        label: text(metadata, 'label'),
        recorded_by: text(metadata, 'recorded_by'),
        location: text(metadata, 'location'),
        recorded_at: text(metadata, 'recorded_at'),
        notes: text(metadata, 'notes'),
      },
    }
  })
}

const clips = loadClips()

test('real incident dataset contains at least twelve usable clips', { tag: '@real-clips' }, () => {
  test.skip(clips.length === 0 && !process.env.REWIND_REQUIRE_REAL_CLIPS, 'Prepare the local clip dataset first')
  expect(clips.length).toBeGreaterThanOrEqual(12)
  expect(new Set(clips.map(clip => clip.hash)).size).toBe(clips.length)
  for (const clip of clips) expect(existsSync(resolve(directory, clip.filename))).toBeTruthy()
})

for (const clip of clips) {
  test(`upload, annotate, analyze, and play ${clip.filename}`, { tag: '@real-clips' }, async ({ page }) => {
    const errors: string[] = []
    page.on('pageerror', error => errors.push(error.message))
    await page.goto('/?case=demo')
    await page.getByRole('button', { name: 'New case', exact: true }).click()
    await page.getByLabel('Choose evidence files').setInputFiles(resolve(directory, clip.filename))
    const dialog = page.getByRole('dialog')
    await dialog.locator('summary').filter({ hasText: clip.filename }).click()
    await page.getByLabel(`Label for ${clip.filename}`, { exact: true }).fill(clip.metadata.label)
    await page.getByLabel(`Recorded by for ${clip.filename}`, { exact: true }).fill(clip.metadata.recorded_by)
    await page.getByLabel(`Location for ${clip.filename}`, { exact: true }).fill(clip.metadata.location)
    await page.getByLabel(`Recording time for ${clip.filename}`, { exact: true }).fill(clip.metadata.recorded_at)
    await page.getByLabel(`Notes for ${clip.filename}`, { exact: true }).fill(clip.metadata.notes)
    await page.getByRole('button', { name: 'Create case with 1 file', exact: true }).click()
    await expect(page.getByRole('button', { name: 'Analyze evidence', exact: true })).toBeEnabled()
    const caseId = new URL(page.url()).searchParams.get('case')
    if (!caseId) throw new Error('Upload did not create a case URL')
    const incident: Case = await (await page.request.get(`/api/cases/${caseId}`)).json()
    expect(incident.media_files).toHaveLength(1)
    const source = incident.media_files[0]!
    expect(source.sha256).toBe(clip.hash)
    expect(source.duration_seconds).toBeCloseTo(clip.duration, 1)
    expect(source.metadata).toEqual(clip.metadata)
    const video = page.locator('video')
    await expect.poll(() => video.evaluate((element: HTMLVideoElement) => element.readyState >= 2)).toBeTruthy()
    await video.evaluate(async (element: HTMLVideoElement) => { element.muted = true; await element.play() })
    await expect.poll(() => video.evaluate((element: HTMLVideoElement) => element.currentTime)).toBeGreaterThan(0.05)
    await video.evaluate((element: HTMLVideoElement) => element.pause())
    await page.getByLabel('Analysis mode').selectOption('mock')
    await page.getByRole('button', { name: 'Analyze evidence', exact: true }).click()
    await expect(page.getByRole('button', { name: 'Re-analyze', exact: true })).toBeEnabled()
    await expect(page.locator('.timeline-row')).toHaveCount(1)
    await expect(page.getByRole('region', { name: 'Working account', exact: true })).toBeVisible()
    await page.getByRole('region', { name: 'Unified timeline', exact: true }).getByRole('button').click()
    await expect.poll(() => video.evaluate((element: HTMLVideoElement) => element.currentTime)).toBeCloseTo(0, 1)
    await page.reload()
    await expect(page.locator('.timeline-row')).toHaveCount(1)
    await expect(page.getByRole('heading', { name: clip.metadata.label, exact: true })).toBeVisible()
    expect(errors).toEqual([])
  })
}
