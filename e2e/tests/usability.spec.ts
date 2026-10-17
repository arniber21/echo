import { expect, test } from '@playwright/test'
import type { Case } from '../../frontend/app/types/generated'

for (const width of [1440, 390]) {
  test(`timeline selection reveals its exact source at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 1000 })
    await page.emulateMedia({ reducedMotion: 'reduce' })
    const incident: Case = await (await page.request.get('/api/cases/demo')).json()
    const event = incident.analysis?.events.find(item => item.source_type === 'video' && item.source_start !== null)
    if (!event || event.source_start === null) throw new Error('Fixture must include a seekable event')
    await page.goto('/?case=demo')
    const eventButton = page.getByRole('region', { name: 'Unified timeline', exact: true }).getByRole('button', { name: event.title, exact: true })
    // Keyboard activation must reveal the selected source too.
    await eventButton.focus()
    await eventButton.press('Enter')
    const viewer = page.getByRole('region', { name: 'Evidence viewer', exact: true })
    await expect(viewer).toBeInViewport()
    await expect.poll(() => page.locator('video').evaluate((video: HTMLVideoElement) => video.currentTime)).toBeCloseTo(event.source_start, 1)
    const position = await page.evaluate(() => window.scrollY)
    await expect.poll(() => page.evaluate(() => window.scrollY)).toBe(position)
  })
}

test('a missing case URL recovers to an existing workspace without claiming there are no cases', async ({ page }) => {
  const { fileURLToPath } = await import('node:url')
  await page.goto('/?case=demo')
  await expect(page.getByRole('button', { name: 'New case', exact: true })).toBeEnabled()
  await page.getByRole('button', { name: 'New case', exact: true }).click()
  await page.getByLabel('Choose evidence files').setInputFiles(fileURLToPath(new URL('../../demo/media/demo-video.mp4', import.meta.url)))
  await page.getByRole('dialog').getByLabel('Case title', { exact: true }).fill('Existing case for recovery')
  await page.getByRole('button', { name: 'Create case with 1 file', exact: true }).click()
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('Existing case for recovery')
  await page.goto('/?case=does-not-exist')
  await expect(page.getByRole('heading', { name: 'Case not found', exact: true })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'No cases yet', exact: true })).toHaveCount(0)
  await page.locator('.load-failure').getByRole('button', { name: 'Open workspace', exact: true }).click()
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('Existing case for recovery')
  await expect(page).not.toHaveURL(/does-not-exist/)
  await page.reload()
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('Existing case for recovery')
})

test('a workspace load failure is distinct from an empty workspace', async ({ page }) => {
  await page.route('**/api/workspace', route => route.fulfill({ status: 503, json: { detail: 'Storage is unavailable.' } }))
  await page.goto('/')
  await expect(page.getByRole('heading', { name: 'Unable to load workspace', exact: true })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'No cases yet', exact: true })).toHaveCount(0)
})

test('provider explanations identify Gemini and optional TypeSafe before analysis', async ({ page }) => {
  await page.goto('/?case=demo')
  const library = page.locator('.library-footnote')
  await expect(library).toContainText('Original files are stored locally.')
  await expect(library).toContainText('Gemini')
  await expect(library).toContainText('Optional TypeSafe checks receive sampled images and extracted text.')
  await expect(library).toContainText('Simulated analysis makes no external requests.')
  await page.getByRole('button', { name: 'New case', exact: true }).click()
  const notice = page.getByRole('dialog').locator('.upload-privacy')
  await expect(notice).toContainText('Gemini')
  await expect(notice).toContainText('Optional TypeSafe checks receive sampled images and extracted text.')
  await expect(notice).toContainText('Simulated analysis makes no external requests.')
})
