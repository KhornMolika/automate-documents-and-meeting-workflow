import { expect, test } from '@playwright/test'
import { authenticate, seedCompletedMeeting, uniqueTitle } from './api'

test.describe('Tasks', () => {
  test('shows verified action items and decisions, and persists a status update', async ({ page, request }) => {
    const token = await authenticate(page, request)
    const title = uniqueTitle('E2E Tasks Meeting')
    await seedCompletedMeeting(request, token, title)

    await page.goto('/tasks')
    await page.waitForLoadState('networkidle')

    await expect(page.getByRole('heading', { level: 1, name: 'Tasks' })).toBeVisible()
    const taskRow = page.getByText('Submit the E2E ethics approval.', { exact: true })
    await expect(taskRow.first()).toBeVisible()
    await expect(page.getByText(title).first()).toBeVisible()

    const select = page.getByLabel('Status for Submit the E2E ethics approval.').last()
    await select.click()
    await page.getByRole('option', { name: 'Completed' }).click()
    await expect(page.getByText('Task updated.')).toBeVisible()

    await page.reload()
    await page.waitForLoadState('networkidle')
    await expect(page.getByLabel('Status for Submit the E2E ethics approval.').last()).toContainText('Completed')

    await page.getByRole('tab', { name: /Decisions/ }).click()
    await expect(page.getByText('Approve the proposal for the next stage.').last()).toBeVisible()
  })
})
