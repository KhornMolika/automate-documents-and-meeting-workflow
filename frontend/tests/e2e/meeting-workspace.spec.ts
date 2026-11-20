import { expect, test } from '@playwright/test'
import {
  authenticate,
  createMeeting,
  seedDraftMeeting,
  seedTranscriptMeeting,
  uniqueTitle,
} from './api'
import { expectOverlayBlur } from './helpers'

test.describe('Meeting workspace', () => {
  test('corrects a misheard transcript before generating minutes', async ({ page, request }) => {
    const token = await authenticate(page, request)
    const title = uniqueTitle('E2E Transcript Correction')
    const meeting = await seedTranscriptMeeting(request, token, title)

    await page.goto(`/meetings/${meeting.id}/review`)
    await page.waitForLoadState('networkidle')
    await page.getByRole('button', { name: 'Edit' }).first().click()
    await page.getByLabel('Speaker', { exact: true }).fill('Dean Lay Thou')
    await page.getByTestId('transcript-original').fill('សូមពិនិត្យរបាយការណ៍នេះ។')
    await page.getByRole('button', { name: 'Save correction' }).click()

    await expect(page.getByText('Transcript corrected.')).toBeVisible()
    await expect(page.getByText('សូមពិនិត្យរបាយការណ៍នេះ។')).toBeVisible()
    await expect(page.getByText('Dean Lay Thou')).toBeVisible()

    await page.reload()
    await page.waitForLoadState('networkidle')
    await expect(page.getByText('សូមពិនិត្យរបាយការណ៍នេះ។')).toBeVisible()
  })

  test('imports a pasted transcript', async ({ page, request }) => {
    const token = await authenticate(page, request)
    const title = uniqueTitle('E2E Transcript Import')
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
    await expect(dialog).toBeVisible()
    await expectOverlayBlur(page)
    await dialog.getByRole('tab', { name: 'Transcript' }).click()
    await dialog.getByLabel('Or paste the transcript').fill('E2E Chair: Please review the imported minutes.')
    await dialog.getByRole('button', { name: 'Import transcript' }).click()
    await expect(dialog).toHaveCount(0)
    await expect(page.getByText('Imported 1 segment.')).toBeVisible()
    await expect(page.getByText('Please review the imported minutes.')).toBeVisible()
  })

  test('edits a draft, saves and publishes it with downloadable exports', async ({ page, request }) => {
    const token = await authenticate(page, request)
    const title = uniqueTitle('E2E Draft Minutes')
    const meeting = await seedDraftMeeting(request, token, title)

    await page.goto(`/meetings/${meeting.id}/review`)
    await page.waitForLoadState('networkidle')

    const summary = page.locator('#mom-summary')
    await expect(summary).toHaveValue(/The board reviewed/)
    const points = page.getByRole('textbox', { name: /^Discussion point/ })
    await expect(points).toHaveCount(2)
    await page.getByRole('button', { name: 'Add discussion point' }).click()
    await expect(points).toHaveCount(3)
    await points.last().fill('E2E added discussion point')
    await page.getByRole('button', { name: 'Remove discussion point 3' }).click()
    await expect(points).toHaveCount(2)

    await page.getByRole('button', { name: 'Save draft' }).click()
    await expect(page.getByText('Draft saved.')).toBeVisible()

    await page.getByRole('button', { name: 'Publish minutes' }).click()
    const dialog = page.getByTestId('approve-minutes')
    await expect(dialog).toBeVisible()
    await expectOverlayBlur(page)
    await dialog.getByRole('button', { name: 'Close' }).click()
    await expect(dialog).toHaveCount(0)

    await page.getByRole('button', { name: 'Publish minutes' }).click()
    await expect(dialog).toBeVisible()
    await dialog.getByRole('button', { name: 'Cancel' }).click()
    await expect(dialog).toHaveCount(0)

    await page.getByRole('button', { name: 'Publish minutes' }).click()
    await expect(dialog).toBeVisible()
    await dialog.getByRole('button', { name: 'Confirm & publish' }).click()
    await expect(page.getByText('Minutes published').first()).toBeVisible()
    await expect(page.getByRole('button', { name: 'DOCX' })).toBeVisible()
    await expect(page.getByRole('button', { name: 'CSV' })).toBeVisible()
    await expect(page.getByRole('button', { name: 'Publish minutes' })).toHaveCount(0)

    const docxDownload = page.waitForEvent('download')
    await page.getByRole('button', { name: 'DOCX' }).click()
    expect((await docxDownload).suggestedFilename()).toMatch(/minutes\.docx$/)

    const csvDownload = page.waitForEvent('download')
    await page.getByRole('button', { name: 'CSV' }).click()
    expect((await csvDownload).suggestedFilename()).toMatch(/action-items\.csv$/)

    await page.goto('/documents')
    await page.waitForLoadState('networkidle')
    await page.getByLabel('Search documents').fill(title)
    const archivedRow = page.getByTestId('document-table').locator('tbody tr').first()
    await expect(archivedRow).toContainText(title)
    await archivedRow.getByRole('button', { name: 'Open' }).click()
    const archivedDialog = page.getByTestId('document-detail')
    await expect(archivedDialog).toContainText('Archived from a meeting')
    await archivedDialog.getByRole('link', { name: 'Open meeting' }).click()
    await expect(page).toHaveURL(new RegExp(`/meetings/${meeting.id}/review$`))
  })

  test('rejects a live meeting URL before creating a job', async ({ page, request }) => {
    const token = await authenticate(page, request)
    const title = uniqueTitle('E2E Live Link Guard')
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
    await dialog.getByRole('tab', { name: 'From link' }).click()
    await dialog.getByLabel('Direct file link').fill('https://meet.google.com/abc-defg-hij')
    await dialog.getByRole('button', { name: 'Read link' }).click()

    await expect(dialog.getByText('This is a live meeting link')).toBeVisible()
    await expect(dialog).toBeVisible()
  })

  test('shows a provider error instead of inventing a draft', async ({ page, request }) => {
    const token = await authenticate(page, request)
    const title = uniqueTitle('E2E No AI Draft')
    const meeting = await seedTranscriptMeeting(request, token, title)

    await page.route(`**/api/v1/meetings/${meeting.id}/synthesize-mom`, route =>
      route.fulfill({
        status: 503,
        contentType: 'application/json',
        body: JSON.stringify({
          detail: 'Ollama is not reachable at http://localhost:11434. Start it with `ollama serve`.',
        }),
      }),
    )

    await page.goto(`/meetings/${meeting.id}/review`)
    await page.waitForLoadState('networkidle')
    await page.getByRole('button', { name: 'Generate draft from transcript' }).click()
    await expect(page.getByText('Ollama is not reachable')).toBeVisible()
  })
})
