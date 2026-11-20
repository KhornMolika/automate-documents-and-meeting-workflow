import { expect, test } from '@playwright/test'
import { authenticate, createMeeting, seedDocument, seedTranscriptMeeting, uniqueTitle } from './api'

const live = process.env.E2E_LIVE === '1'
const demoDir = process.env.DEMO_DIR || '/Users/alexkgm/Desktop/demo'

test.describe('Live services', () => {
  test.skip(!live, 'Set E2E_LIVE=1 to run tests that call the speech service and Gemini.')

  test('transcribes a real Khmer recording', async ({ page, request }) => {
    test.setTimeout(240_000)
    const token = await authenticate(page, request)
    const title = uniqueTitle('E2E Khmer Recording')
    const meeting = await createMeeting(
      request,
      token,
      title,
      new Date(Date.now() + 60_000),
      new Date(Date.now() + 30 * 60_000),
    )

    await page.goto(`/meetings/${meeting.id}/review`)
    await page.waitForLoadState('networkidle')
    await page.getByRole('button', { name: 'Add content' }).first().click()
    const dialog = page.getByTestId('meeting-content')
    await dialog.getByRole('tab', { name: 'Recording' }).click()
    await dialog.locator('#recording-file').setInputFiles(`${demoDir}/recordings/khmer-meeting.mp3`)
    await dialog.locator('#recording-language').click()
    await page.getByRole('option', { name: 'Khmer' }).click()
    await dialog.getByRole('button', { name: 'Transcribe recording' }).click()

    await expect(dialog).toHaveCount(0)
    await expect(page.getByText(/សួស្[តដ]ី/).first()).toBeVisible({ timeout: 180_000 })
    await expect(page.getByText(/តារា/).first()).toBeVisible()
    await expect(page.getByText('0 segments')).toHaveCount(0)
  })

  test('transcribes an English recording locally', async ({ page, request }) => {
    test.setTimeout(180_000)
    const token = await authenticate(page, request)
    const title = uniqueTitle('E2E English Recording')
    const meeting = await createMeeting(
      request,
      token,
      title,
      new Date(Date.now() + 60_000),
      new Date(Date.now() + 30 * 60_000),
    )

    await page.goto(`/meetings/${meeting.id}/review`)
    await page.waitForLoadState('networkidle')
    await page.getByRole('button', { name: 'Add content' }).first().click()
    const dialog = page.getByTestId('meeting-content')
    await dialog.getByRole('tab', { name: 'Recording' }).click()
    await dialog.locator('#recording-file').setInputFiles(`${demoDir}/recordings/english-meeting.mp3`)
    await dialog.locator('#recording-language').click()
    await page.getByRole('option', { name: 'English' }).click()
    await dialog.getByRole('button', { name: 'Transcribe recording' }).click()

    await expect(dialog).toHaveCount(0)
    await expect(page.getByText('Central and Eastern Europe', { exact: false }).first()).toBeVisible({ timeout: 150_000 })
  })

  test('generates a document summary with Gemini', async ({ page, request }) => {
    test.setTimeout(240_000)
    const token = await authenticate(page, request)
    const title = uniqueTitle('E2E Gemini Document')
    await seedDocument(
      request,
      token,
      title,
      `ចំណងជើង,អ្នកទទួល\n${title},នាយកដ្ឋានវិទ្យាសាស្ត្រ\n`,
    )

    await page.goto('/documents')
    await page.waitForLoadState('networkidle')
    await page.getByLabel('Search documents').fill(title)
    const row = page.getByTestId('document-table').locator('tbody tr').first()
    await row.getByRole('button').first().click()
    const dialog = page.getByTestId('document-detail')
    await expect(dialog.getByRole('button', { name: 'ខ្មែរ' })).toHaveAttribute('aria-pressed', 'true')
    await dialog.getByRole('button', { name: /Generate summary/ }).click()

    await expect(dialog.getByTestId('document-summary')).toBeVisible({ timeout: 200_000 })
    await expect(dialog.getByTestId('document-summary')).toHaveText(/[\u1780-\u17FF]/)
  })

  test('generates an AI minutes draft with Gemini', async ({ page, request }) => {
    test.setTimeout(300_000)
    const token = await authenticate(page, request)
    const title = uniqueTitle('E2E Gemini Draft')
    const meeting = await seedTranscriptMeeting(request, token, title)

    await page.goto(`/meetings/${meeting.id}/review`)
    await page.waitForLoadState('networkidle')
    await expect(page.getByRole('button', { name: 'ខ្មែរ' })).toHaveAttribute('aria-pressed', 'true')
    await page.getByRole('button', { name: 'Generate draft from transcript' }).click()

    await expect(page.locator('#mom-summary')).not.toHaveValue('', { timeout: 240_000 })
    await expect(page.locator('#mom-summary')).toHaveValue(/[\u1780-\u17FF]/)
    await expect(page.getByRole('textbox', { name: /^Action item/ }).first()).toBeVisible()
    await expect(page.getByText('Ollama is not reachable')).toHaveCount(0)
  })
})
