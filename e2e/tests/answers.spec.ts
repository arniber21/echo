import { expect, test } from '@playwright/test'
import { fileURLToPath } from 'node:url'
import type { Case } from '../../frontend/app/types/generated'

test('question answers persist, stay pending until update, and retain exact historical attribution', async ({ page }) => {
  await page.goto('/?case=demo')
  await expect(page.getByRole('button', { name: 'New case', exact: true })).toBeEnabled()
  await page.getByRole('button', { name: 'New case', exact: true }).click()
  await page.getByLabel('Choose evidence files').setInputFiles(fileURLToPath(new URL('../../demo/media/demo-video.mp4', import.meta.url)))
  await page.getByRole('button', { name: 'Create case with 1 file', exact: true }).click()
  await page.getByLabel('Analysis mode').selectOption('mock')
  await page.getByRole('button', { name: 'Analyze evidence', exact: true }).click()
  await expect(page.getByRole('button', { name: 'Re-analyze', exact: true })).toBeEnabled()
  const caseId = new URL(page.url()).searchParams.get('case')
  if (!caseId) throw new Error('Case URL is required')
  async function readCase(): Promise<Case> {
    const response = await page.request.get(`/api/cases/${caseId}`)
    expect(response.ok()).toBeTruthy()
    return response.json()
  }
  const initial = await readCase()
  const question = initial.analysis?.missing_evidence[0]
  if (!question) throw new Error('Mock reconstruction must include a question')
  await page.getByRole('tab', { name: /Missing evidence/ }).click()
  await page.getByRole('button', { name: 'Answer question', exact: true }).first().click()
  const form = page.getByRole('form', { name: `Answer: ${question.title}`, exact: true })
  await form.getByLabel(`Response to ${question.title}`, { exact: true }).fill('I was driving the blue car. The camera clock was five minutes slow.')
  await form.getByLabel('Respondent (optional)', { exact: true }).fill('Driver A')
  let rejected = false
  await page.route(`**/api/cases/${caseId}/answers`, async route => {
    if (route.request().method() === 'POST' && !rejected) {
      rejected = true
      await route.fulfill({ status: 409, json: { detail: 'The case changed. Review the current question and retry.' } })
    } else await route.continue()
  })
  await form.getByRole('button', { name: 'Save answer', exact: true }).click()
  await expect(page.getByText('The case changed. Review the current question and retry.', { exact: true })).toBeVisible()
  await expect(form.getByLabel(`Response to ${question.title}`, { exact: true })).toHaveValue('I was driving the blue car. The camera clock was five minutes slow.')
  await form.getByRole('button', { name: 'Save answer', exact: true }).click()
  await expect(page.getByText('Case responses changed · reconstruction needs update.', { exact: true })).toBeVisible()
  const pending = await readCase()
  expect(pending.answers).toHaveLength(1)
  expect(pending.analysis).toEqual(initial.analysis)
  expect(pending.memory).toEqual(initial.memory)
  expect(pending.evidence_revision).toBe(initial.evidence_revision + 1)
  expect(pending.answers[0]?.respondent).toBe('Driver A')
  await page.reload()
  const inventory = page.getByRole('region', { name: 'Case responses', exact: true })
  await expect(inventory).toContainText('The camera clock was five minutes slow.')
  await inventory.getByRole('button', { name: 'Edit answer', exact: true }).click()
  await inventory.getByLabel(`Response to ${question.title}`, { exact: true }).fill('Correction: the camera clock was two minutes slow.')
  await inventory.getByRole('button', { name: 'Save answer', exact: true }).click()
  await expect(inventory).toContainText('Correction: the camera clock was two minutes slow.')
  await page.getByRole('button', { name: 'Update reconstruction', exact: true }).click()
  await expect(page.getByRole('button', { name: 'Re-analyze', exact: true })).toBeEnabled()
  const accepted = await readCase()
  expect(accepted.analyzed_answers[0]?.text).toBe('Correction: the camera clock was two minutes slow.')
  const citations = page.locator('.insights-panel .answer-reference')
  await expect(citations).not.toHaveCount(0)
  await citations.first().locator('summary').click()
  await expect(citations.first()).toContainText('User reported · Driver A')
  await expect(citations.first()).toContainText('Correction: the camera clock was two minutes slow.')
  // Editing again must not rewrite attribution used by the accepted reconstruction.
  await inventory.getByRole('button', { name: 'Edit answer', exact: true }).click()
  await inventory.getByLabel(`Response to ${question.title}`, { exact: true }).fill('The clock is now confirmed to be three minutes slow.')
  await inventory.getByRole('button', { name: 'Save answer', exact: true }).click()
  await expect(inventory).toContainText('three minutes slow')
  await expect(citations.first()).toContainText('two minutes slow')
  await expect(citations.first()).not.toContainText('three minutes slow')
  await page.getByRole('button', { name: 'Update reconstruction', exact: true }).click()
  await expect(page.getByRole('button', { name: 'Re-analyze', exact: true })).toBeEnabled()
  await page.getByLabel('Reconstruction version', { exact: true }).selectOption(String(accepted.analyzed_revision))
  await expect(inventory).toContainText('two minutes slow')
  await expect(inventory).not.toContainText('three minutes slow')
  await expect(inventory.getByRole('button', { name: 'Edit answer', exact: true })).toHaveCount(0)
  await page.getByRole('button', { name: 'Return to current', exact: true }).click()
  await expect(inventory).toContainText('three minutes slow')
  await page.getByRole('link', { name: /View report/ }).click()
  await expect(page.getByRole('region', { name: 'Case responses', exact: true })).toContainText('Driver A')
  await expect(page.locator('.report-document .answer-reference').first()).toContainText('User reported · Driver A')
})

test('provisional multi-view relationships open each original without inventing a seek', async ({ page }) => {
  const response = await page.request.get('/api/cases/demo')
  const incident: Case = await response.json()
  const first = incident.media_files.find(source => source.source_type === 'video')
  if (!first) throw new Error('Fixture video is required')
  const second = { ...first, source_id: 'other-camera', filename: 'other-camera.mp4', metadata: { ...first.metadata, label: 'Other camera' } }
  incident.media_files.push(second)
  incident.analyzed_media_files.push(second)
  incident.analyzed_source_ids.push(second.source_id)
  incident.intelligence = {
    model: 'jev-1.14.0', version: 'browser-fixture', status: 'complete', sources: [], claims: [],
    video_relationships: [{
      source_a: first.source_id, source_b: second.source_id,
      relationship: 'same_incident_different_view', confidence: 0.86,
      same_incident_probability: 0.91, different_view_probability: 0.86,
      basis: 'Similar vehicles and sequence, seen from different sides. Clock alignment is unknown.', matches: [],
    }], input_tokens: 0, elapsed_seconds: 0, diagnostics: [],
  }
  await page.route('**/api/cases/demo', route => route.fulfill({ json: incident }))
  await page.goto('/?case=demo')
  const relationships = page.getByRole('region', { name: 'Video relationships', exact: true })
  await expect(relationships).toContainText('Likely same incident · different viewpoint')
  await expect(relationships).toContainText('Unverified model assessment')
  await expect(relationships).toContainText('Clock alignment is unknown')
  await relationships.getByRole('button', { name: `Open ${second.filename}`, exact: true }).click()
  await expect(page.getByRole('region', { name: 'Source details', exact: true })).toContainText('Other camera')
  await relationships.getByRole('button', { name: `Open ${first.filename}`, exact: true }).click()
  await expect(page.getByRole('region', { name: 'Evidence viewer', exact: true }).locator('.player-caption')).toContainText(first.filename)
  await expect.poll(() => page.locator('video').evaluate((video: HTMLVideoElement) => video.currentTime)).toBe(0)
})
