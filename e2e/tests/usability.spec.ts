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
