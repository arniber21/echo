import { expect, test } from '@playwright/test'
import type { Case, EvidenceIntelligence, MediaFile } from '../../frontend/app/types/generated'

function intelligence(source: MediaFile, sourceTime: number, probability: number): EvidenceIntelligence {
  return {
    model: 'jev-1.14.0',
    version: 'browser-test-fixture',
    status: 'complete',
    sources: [{
      source_id: source.source_id,
      labels: { vehicle_visible: probability },
      frames: [{
        source_time: sourceTime,
        signals: { vehicle_visible: probability },
        vehicle_box: null,
        box_confidence: null,
        image_sha256: 'browser-test-frame',
        prepared_width: 1120,
        prepared_height: 630,
      }],
    }],
    claims: [{ claim_index: 0, supported_probability: 0.91, overclaim_probability: 0.12 }],
    input_tokens: 100,
    elapsed_seconds: 0.5,
    diagnostics: [],
  }
}

test('saved evidence signals seek source time and historical versions keep their own checks', async ({ page }) => {
  const response = await page.request.get('/api/cases/demo')
  expect(response.ok()).toBeTruthy()
  const incident: Case = await response.json()
  const source = incident.media_files.find(item => item.source_type === 'video')
  if (!source || !incident.analysis?.summary.length) throw new Error('Fixture requires video and summary')

  // Intercept only this browser's case response; no model call or database mutation.
  incident.evidence_revision = 2
  incident.analyzed_revision = 2
  incident.intelligence = intelligence(source, 3.25, 0.92)
  incident.analysis_history = [{
    revision: 1,
    created_at: incident.created_at,
    media_source_ids: [source.source_id],
    media_count: 1,
    media_files: [source],
    analysis: incident.analysis,
    intelligence: intelligence(source, 7.25, 0.18),
  }]
  await page.route('**/api/cases/demo', route => route.fulfill({ json: incident }))
  await page.goto('/?case=demo')

  const signals = page.getByRole('region', { name: 'Evidence signals', exact: true })
  await expect(signals).toBeVisible()
  await expect(signals).toContainText('not verified findings')
  await signals.locator('summary').filter({ hasText: 'Source checks' }).click()
  await expect(signals.getByText('92%', { exact: true }).first()).toBeVisible()
  await signals.locator('summary').filter({ hasText: 'Sampled images' }).click()
  await signals.getByRole('button', { name: `Open ${source.filename} at source time 00:03.3`, exact: true }).click()
  await expect.poll(() => page.locator('video').evaluate((element: HTMLVideoElement) => element.currentTime)).toBeCloseTo(3.25, 1)

  await signals.locator('summary').filter({ hasText: 'Checks against extracted evidence' }).click()
  await expect(signals.getByText(incident.analysis.summary[0]!.text, { exact: true })).toBeVisible()
  await expect(signals.getByText('Supported by extraction', { exact: true })).toBeVisible()
  await expect(signals.getByText('91%', { exact: true })).toBeVisible()
  await expect(signals.getByText('Goes beyond extraction', { exact: true })).toBeVisible()

  await page.getByLabel('Reconstruction version', { exact: true }).selectOption('1')
  await expect(signals.getByText('18%', { exact: true }).first()).toBeVisible()
  await expect(signals.getByText('92%', { exact: true })).toHaveCount(0)
  await signals.getByRole('button', { name: `Open ${source.filename} at source time 00:07.3`, exact: true }).click()
  await expect.poll(() => page.locator('video').evaluate((element: HTMLVideoElement) => element.currentTime)).toBeCloseTo(7.25, 1)
  await page.getByRole('button', { name: 'Return to current', exact: true }).click()
  await expect(signals.getByText('92%', { exact: true }).first()).toBeVisible()
  await expect(signals.getByText('18%', { exact: true })).toHaveCount(0)
})
