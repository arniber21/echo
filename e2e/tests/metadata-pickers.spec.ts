import { expect, test } from '@playwright/test'
import { fileURLToPath } from 'node:url'
import type { Case } from '../../frontend/app/types/generated'

const fixture = fileURLToPath(new URL('../../demo/media/demo-video.mp4', import.meta.url))

test('location search and native date/time persist through intake, editing and reload', async ({
  page,
}) => {
  const searches: string[] = []
  await page.route('**/api/locations/search?**', (route) => {
    searches.push(new URL(route.request().url()).searchParams.get('q') ?? '')
    return route.fulfill({
      json: [
        {
          label: 'Market St, San Francisco, California',
          latitude: 37.774929,
          longitude: -122.419416,
        },
      ],
    })
  })
  // No public map or geocoding requests are made by automated tests.
  await page.route('https://www.openstreetmap.org/**', (route) =>
    route.fulfill({
      contentType: 'text/html',
      body: '<p>Mock map with selected pin</p>',
    }),
  )
  await page.goto('/?case=demo')
  await page.getByRole('button', { name: 'New case', exact: true }).click()
  await page.getByLabel('Choose evidence files').setInputFiles(fixture)
  let dialog = page.getByRole('dialog')
  await dialog.locator('summary').click()
  await dialog
    .getByLabel('Location for demo-video.mp4', { exact: true })
    .fill('Market St, San Francisco')
  expect(searches).toHaveLength(0)
  await dialog
    .getByRole('button', {
      name: 'Search location for demo-video.mp4',
      exact: true,
    })
    .click()
  await dialog.getByRole('button', { name: /Market St, San Francisco, California/ }).click()
  await expect(dialog.getByTitle('Selected recording location')).toHaveAttribute(
    'src',
    /marker=37.774929%2C-122.419416/,
  )
  await dialog.getByLabel('Recording date for demo-video.mp4', { exact: true }).fill('2026-10-17')
  await dialog.getByLabel('Recording time for demo-video.mp4', { exact: true }).fill('14:30:45')
  await dialog.getByRole('button', { name: 'Create case with 1 file', exact: true }).click()
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('Untitled incident')
  const caseId = new URL(page.url()).searchParams.get('case')!
  let incident: Case = await (await page.request.get(`/api/cases/${caseId}`)).json()
  expect(incident.media_files[0]!.metadata.recorded_at).toBe('2026-10-17T14:30:45')
  expect(incident.media_files[0]!.captured_at).toBeNull()
  expect(incident.media_files[0]!.metadata.location).toContain('(37.774929, -122.419416)')
  await page
    .getByRole('region', { name: 'Source details', exact: true })
    .getByRole('button', { name: 'Edit details', exact: true })
    .click()
  dialog = page.getByRole('dialog')
  await expect(dialog.getByTitle('Selected recording location')).toBeVisible()
  await expect(dialog.getByLabel('Recording date', { exact: true })).toHaveValue('2026-10-17')
  await dialog.getByLabel('Recording time', { exact: true }).fill('15:10:00')
  await dialog.getByRole('button', { name: 'Save source details', exact: true }).click()
  await page.reload()
  await expect(page.getByRole('region', { name: 'Source details', exact: true })).toContainText(
    '2026-10-17 15:10:00 (local time)',
  )
  incident = await (await page.request.get(`/api/cases/${caseId}`)).json()
  expect(incident.media_files[0]!.metadata.recorded_at).toBe('2026-10-17T15:10:00')
  expect(searches).toEqual(['Market St, San Francisco'])
})

test('failed searches preserve manual location and legacy time descriptions', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 900 })
  await page.route('**/api/locations/search?**', (route) =>
    route.fulfill({ status: 503, json: { detail: 'Unavailable' } }),
  )
  await page.goto('/?case=demo')
  await page.getByRole('button', { name: 'New case', exact: true }).click()
  await page.getByLabel('Choose evidence files').setInputFiles(fixture)
  let dialog = page.getByRole('dialog')
  await dialog.locator('summary').click()
  await dialog
    .getByLabel('Location for demo-video.mp4', { exact: true })
    .fill('Main & Third, approximate')
  await dialog.getByLabel('Location for demo-video.mp4', { exact: true }).press('Enter')
  await expect(dialog.getByRole('alert')).toContainText('Map search is unavailable')
  await expect(dialog.getByLabel('Location for demo-video.mp4', { exact: true })).toHaveValue(
    'Main & Third, approximate',
  )
  await dialog.getByRole('button', { name: 'Use a time description', exact: true }).click()
  await dialog
    .getByLabel('Recording time for demo-video.mp4', { exact: true })
    .fill('Around 2:30 pm PDT, date uncertain')
  await dialog.getByRole('button', { name: 'Create case with 1 file', exact: true }).click()
  await page
    .getByRole('region', { name: 'Source details', exact: true })
    .getByRole('button', { name: 'Edit details', exact: true })
    .click()
  dialog = page.getByRole('dialog')
  await expect(dialog.getByLabel('Recording time (reported)', { exact: true })).toHaveValue(
    'Around 2:30 pm PDT, date uncertain',
  )
  await dialog.getByLabel('Source label', { exact: true }).fill('Preserve original time context')
  await dialog.getByRole('button', { name: 'Save source details', exact: true }).click()
  await page.reload()
  await expect(page.getByRole('region', { name: 'Source details', exact: true })).toContainText(
    'Around 2:30 pm PDT, date uncertain',
  )
  await expect
    .poll(() => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth))
    .toBeTruthy()
})
