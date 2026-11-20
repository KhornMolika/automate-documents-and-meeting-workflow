import { expect, test } from '@playwright/test'
import { authenticate, seedCompletedMeeting, seedLiveMeeting, uniqueTitle } from './api'
import { expectOverlayBlur } from './helpers'

test.describe('Meetings', () => {
  test('filters real meetings and opens the linked minutes', async ({ page, request }) => {
    const token = await authenticate(page, request)
    const liveTitle = uniqueTitle('E2E Live Filter')
    const completedTitle = uniqueTitle('E2E Completed Filter')
    await seedLiveMeeting(request, token, liveTitle)
    await seedCompletedMeeting(request, token, completedTitle)

    await page.goto('/meetings')
    await page.waitForLoadState('networkidle')
    const rows = page.getByTestId('meeting-row')
    await expect(rows.filter({ hasText: liveTitle })).toHaveCount(1)
    await expect(rows.filter({ hasText: completedTitle })).toHaveCount(1)

    await page.getByRole('tab', { name: /^Live/ }).click()
    await expect(rows.filter({ hasText: liveTitle })).toHaveCount(1)
    await expect(rows.filter({ hasText: completedTitle })).toHaveCount(0)

    await page.getByRole('tab', { name: /^Completed/ }).click()
    await expect(rows.filter({ hasText: completedTitle })).toHaveCount(1)
    await expect(rows.filter({ hasText: liveTitle })).toHaveCount(0)

    const completedRow = rows.filter({ hasText: completedTitle })
    await completedRow.getByRole('link', { name: 'View minutes' }).click()
    await expect(page).toHaveURL(/\/meetings\/.+\/review$/)
    await expect(page.getByText('Minutes verified').first()).toBeVisible()
  })

  test('new meeting closes by X, Cancel and Escape, then creates a real meeting', async ({ page, request }) => {
    await authenticate(page, request)
    const title = uniqueTitle('E2E Created Meeting')

    await page.goto('/meetings')
    await page.waitForLoadState('networkidle')
    await page.getByRole('button', { name: 'New meeting' }).click()
    const dialog = page.getByTestId('new-meeting')
    await expect(dialog).toBeVisible()
    await expectOverlayBlur(page)
    await dialog.getByRole('button', { name: 'Close' }).click()
    await expect(dialog).toHaveCount(0)

    await page.getByRole('button', { name: 'New meeting' }).click()
    await expect(dialog).toBeVisible()
    await dialog.getByRole('button', { name: 'Cancel' }).click()
    await expect(dialog).toHaveCount(0)

    await page.getByRole('button', { name: 'New meeting' }).click()
    await expect(dialog).toBeVisible()
    await page.keyboard.press('Escape')
    await expect(dialog).toHaveCount(0)

    await page.getByRole('button', { name: 'New meeting' }).click()
    await expect(dialog).toBeVisible()
    await dialog.getByLabel('Title').fill(title)
    await dialog.getByRole('button', { name: 'Add description or agenda (optional)' }).click()
    await dialog.getByLabel('Agenda').fill('First agenda\nSecond agenda')
    await dialog.getByRole('button', { name: 'Create meeting' }).click()
    await expect(dialog).toHaveCount(0)
    await expect(page.getByTestId('meeting-list')).toContainText(title)
    await expect(page.getByText('Meeting created.')).toBeVisible()
  })

  test('creates a meeting with no typing at all', async ({ page, request }) => {
    await authenticate(page, request)
    await page.goto('/meetings')
    await page.waitForLoadState('networkidle')

    await page.getByRole('button', { name: 'New meeting' }).click()
    const dialog = page.getByTestId('new-meeting')
    await expect(dialog).toBeVisible()
    await expect(dialog.getByLabel('Starts')).toHaveCount(0)
    await expect(dialog.getByLabel('Duration')).toHaveCount(0)
    await expect(dialog.getByLabel('Agenda')).toHaveCount(0)

    await dialog.getByRole('button', { name: 'Create meeting' }).click()
    await expect(dialog).toHaveCount(0)
    await expect(page.getByText('Meeting created.')).toBeVisible()
    await expect(page.getByTestId('meeting-list')).toContainText('Computer Science and Engineering meeting')
  })
})
