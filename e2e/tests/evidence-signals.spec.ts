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

for (const accepted of [false, true]) {
  test(`quick scan arrives before detailed analysis and survives failure (${accepted ? 'existing reconstruction' : 'first reconstruction'})`, async ({ page }) => {
    const response = await page.request.get('/api/cases/demo')
    const fixture: Case = await response.json()
    const source = fixture.media_files.find(item => item.source_type === 'video')
    const initialAnalysis = fixture.analysis
    const videoEvent = initialAnalysis?.events.find(event => event.source_id === source?.source_id)
    if (!source || !initialAnalysis || !videoEvent) throw new Error('Fixture requires video analysis')
    const quickEvent = {
      ...videoEvent,
      event_id: 'quick-frame',
      title: 'Sampled vehicle visible',
      source_start: 3.25,
      source_end: null,
      case_best: 3.25,
    }
    const preview: NonNullable<Case['preview']> = {
      evidence_revision: 3,
      created_at: fixture.created_at,
      analysis: {
        ...initialAnalysis,
        events: [quickEvent],
        summary: [{ text: 'Preliminary sampled-frame check.', source_refs: [{ source_id: source.source_id, source_start: 3.25, source_end: null }] }],
        missing_evidence: [],
        contradictions: [],
      },
      intelligence: intelligence(source, 3.25, 0.92),
    }
    fixture.evidence_revision = 3
    fixture.preview = null
    if (accepted) {
      fixture.analyzed_revision = 2
      fixture.analysis_history = [{
        revision: 1,
        created_at: fixture.created_at,
        media_source_ids: [source.source_id],
        media_count: 1,
        media_files: [source],
        analysis: { ...initialAnalysis, events: [{ ...videoEvent, title: 'Saved earlier event' }] },
        intelligence: null,
      }]
    } else {
      fixture.analysis = null
      fixture.intelligence = null
      fixture.memory = null
      fixture.analysis_history = []
      fixture.analyzed_revision = null
      fixture.analyzed_source_ids = []
      fixture.analyzed_media_files = []
    }
    let started = false
    let failed = false
    let jobPolls = 0
    let caseRefreshes = 0
    const job = () => ({
      job_id: 'quick-preview-job',
      case_id: fixture.case_id,
      status: failed ? 'failed' : 'running',
      stage: failed ? 'failed' : jobPolls ? 'analyzing_video' : 'classifying_evidence',
      progress: 20,
      error: failed ? 'Detailed provider unavailable in browser test.' : null,
    })
    await page.route('**/api/cases/demo', route => {
      caseRefreshes += 1
      return route.fulfill({ json: { ...fixture, preview: started ? preview : null } })
    })
    await page.route('**/api/cases/demo/analyze', route => {
      started = true
      return route.fulfill({ json: job() })
    })
    await page.route('**/api/jobs/quick-preview-job', route => {
      jobPolls += 1
      return route.fulfill({ json: job() })
    })
    await page.goto('/?case=demo')
    const account = page.getByRole('region', { name: 'Working account', exact: true })
    const accountBefore = accepted ? await account.innerText() : null
    await page.getByRole('button', { name: accepted ? 'Update reconstruction' : 'Analyze evidence', exact: true }).click()
    const scan = page.getByRole('region', { name: 'Quick scan', exact: true })
    await expect(scan).toBeVisible()
    await expect(scan).toContainText('Detailed reconstruction is running.')
    await expect(page.locator('.timeline-row')).toHaveCount(accepted ? initialAnalysis.events.length : 1)
    expect(failed).toBe(false)
    if (accepted) {
      await scan.locator('summary').filter({ hasText: 'Scan results for the newest evidence' }).click()
      await scan.getByRole('button', { name: /Sampled vehicle visible/ }).click()
    } else {
      await page.getByRole('region', { name: 'Unified timeline', exact: true }).getByRole('button', { name: quickEvent.title, exact: true }).click()
    }
    await expect.poll(() => page.locator('video').evaluate((element: HTMLVideoElement) => element.currentTime)).toBeCloseTo(3.25, 1)
    if (accepted) {
      await expect(account).toHaveText(accountBefore!, { useInnerText: true })
      await page.getByLabel('Reconstruction version', { exact: true }).selectOption('1')
      await expect(scan).toHaveCount(0)
      await expect(page.locator('.timeline-row')).toHaveCount(1)
      await expect(page.locator('.timeline-row')).toContainText('Saved earlier event')
      const previousPolls = jobPolls
      await expect.poll(() => jobPolls).toBeGreaterThan(previousPolls + 1)
      await expect(page.getByLabel('Reconstruction version', { exact: true })).toHaveValue('1')
      await expect(scan).toHaveCount(0)
      await page.getByRole('button', { name: 'Return to current', exact: true }).click()
      await expect(scan).toBeVisible()
    }
    const previousRefreshes = caseRefreshes
    failed = true
    await expect(scan).toContainText('Detailed reconstruction unavailable.')
    await expect(page.getByText('Detailed provider unavailable in browser test.', { exact: true })).toBeVisible()
    expect(caseRefreshes).toBeGreaterThan(previousRefreshes)
    await expect(page.locator('.timeline-row')).toHaveCount(accepted ? initialAnalysis.events.length : 1)
    if (accepted) {
      await expect(account).toHaveText(accountBefore!, { useInnerText: true })
      await page.getByLabel('Reconstruction version', { exact: true }).selectOption('1')
      await expect(page.locator('.timeline-row')).toContainText('Saved earlier event')
      await expect(scan).toHaveCount(0)
    } else {
      await expect(account).toHaveCount(0)
      await expect(page.getByRole('heading', { name: 'No analysis yet', exact: true })).toHaveCount(0)
    }
  })
}
