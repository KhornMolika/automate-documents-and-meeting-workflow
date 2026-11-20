import { expect, test } from '@playwright/test'
import { authenticate, seedDraftMeeting, seedLiveMeeting, uniqueTitle } from './api'
import { expectOverlayBlur } from './helpers'

test.describe('Live meeting', () => {
  test('shows the stored transcript and accepts a realtime segment', async ({ page, request }) => {
    const token = await authenticate(page, request)
    const title = uniqueTitle('E2E Live Console')
    await seedLiveMeeting(request, token, title)

    await page.routeWebSocket('ws://localhost:8000/ws/live-transcript/**', (socket) => {
      setTimeout(() => {
        socket.send(JSON.stringify({
          type: 'transcript_segment',
          speaker_label: 'E2E Live Speaker',
          start_timestamp: 20,
          end_timestamp: 25,
          original_text: 'សូមស្តាប់ការប្រជុំនេះ។',
          translated_text: 'Please follow this meeting.',
        }))
      }, 250)
    })

    await page.goto(`/meetings/${(await findMeeting(request, token, title)).id}/live`)
    await page.waitForLoadState('networkidle')

    await expect(page.getByRole('heading', { level: 1, name: title })).toBeVisible()
    await expect(page.getByText('Original transcript')).toBeVisible()
    await expect(page.getByText('English translation')).toBeVisible()
    await expect(page.getByRole('button', { name: 'End & generate MoM' })).toBeVisible()
    await expect(page.getByTestId('original-segment')).toHaveCount(2)
    await expect(page.getByTestId('translation-segment')).toHaveCount(2)
    await expect(page.getByText('E2E Live Speaker')).toHaveCount(2)
    await expect(page.getByText('Please follow this meeting.')).toBeVisible()
  })

  test('reports a connected audio ingress and its chunk level', async ({ page, request }) => {
    const token = await authenticate(page, request)
    const title = uniqueTitle('E2E Capture Status')
    const meeting = await seedLiveMeeting(request, token, title)

    await page.goto(`/meetings/${meeting.id}/live`)
    await page.waitForLoadState('networkidle')
    await expect(page.getByText('Waiting for capture')).toBeVisible()

    await page.evaluate(
      ({ id, samples }) => {
        const socket = new WebSocket(`ws://127.0.0.1:8000/ws/audio/${id}`)
        socket.binaryType = 'arraybuffer'
        ;(window as any).__audioSocket = socket
        socket.onopen = () => socket.send(new Uint8Array(samples).buffer)
      },
      { id: meeting.id, samples: 16000 * 3 * 2 },
    )

    await expect(page.getByText('Receiving audio', { exact: false })).toBeVisible()
    await page.evaluate(() => (window as any).__audioSocket?.close())
  })
})

test.describe('Minutes review', () => {
  test('corrects a misheard transcript before generating minutes', async ({ page, request }) => {
    const token = await authenticate(page, request)
    const title = uniqueTitle('E2E Transcript Correction')
    const meeting = await seedLiveMeeting(request, token, title)

    await page.goto(`/meetings/${meeting.id}/review`)
    await page.waitForLoadState('networkidle')
    await page.getByRole('button', { name: 'Edit' }).first().click()
    await page.getByTestId('transcript-original').fill('សូមពិនិត្យរបាយការណ៍នេះ។')
    await page.getByTestId('transcript-translation').fill('Please review this report.')
    await page.getByRole('button', { name: 'Save correction' }).click()

    await expect(page.getByText('Transcript corrected.')).toBeVisible()
    await expect(page.getByText('សូមពិនិត្យរបាយការណ៍នេះ។')).toBeVisible()

    await page.reload()
    await page.waitForLoadState('networkidle')
    await expect(page.getByText('សូមពិនិត្យរបាយការណ៍នេះ។')).toBeVisible()
    await expect(page.getByText('Please review this report.')).toBeVisible()
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

    await page.getByRole('button', { name: 'Approve & publish' }).click()
    const dialog = page.getByTestId('approve-minutes')
    await expect(dialog).toBeVisible()
    await expectOverlayBlur(page)
    await dialog.getByRole('button', { name: 'Close' }).click()
    await expect(dialog).toHaveCount(0)

    await page.getByRole('button', { name: 'Approve & publish' }).click()
    await expect(dialog).toBeVisible()
    await dialog.getByRole('button', { name: 'Cancel' }).click()
    await expect(dialog).toHaveCount(0)

    await page.getByRole('button', { name: 'Approve & publish' }).click()
    await expect(dialog).toBeVisible()
    await dialog.getByRole('button', { name: 'Confirm & publish' }).click()
    await expect(page.getByText('Minutes verified')).toBeVisible()
    await expect(page.getByRole('button', { name: 'DOCX' })).toBeVisible()
    await expect(page.getByRole('button', { name: 'CSV' })).toBeVisible()
    await expect(page.getByRole('button', { name: 'Approve & publish' })).toHaveCount(0)
  })

  test('shows a provider error instead of inventing a draft', async ({ page, request }) => {
    const token = await authenticate(page, request)
    const title = uniqueTitle('E2E No AI Draft')
    const meeting = await seedLiveMeeting(request, token, title)

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
    await page.getByRole('button', { name: 'Generate draft' }).click()
    await expect(page.getByText('Ollama is not reachable')).toBeVisible()
  })
})

async function findMeeting(request: any, token: string, title: string) {
  const response = await request.get('http://127.0.0.1:8000/api/v1/meetings?limit=200', {
    headers: { Authorization: `Bearer ${token}` },
  })
  expect(response.ok()).toBeTruthy()
  const meetings = await response.json()
  const meeting = meetings.find((item: any) => item.title === title)
  expect(meeting, `Meeting ${title} should exist`).toBeTruthy()
  return meeting as { id: string }
}
