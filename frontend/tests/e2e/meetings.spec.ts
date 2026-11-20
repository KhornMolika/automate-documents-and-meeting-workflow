import { expect, test } from '@playwright/test'
import { authenticate, createMeeting, seedCompletedMeeting, seedDraftMeeting, uniqueTitle } from './api'
import { expectOverlayBlur } from './helpers'

test.describe('Meetings', () => {
  test('filters real meetings and opens the linked minutes', async ({ page, request }) => {
    const token = await authenticate(page, request)
    const prefix = uniqueTitle('E2E Filter')
    const draftTitle = `${prefix} Draft`
    const publishedTitle = `${prefix} Published`
    await seedDraftMeeting(request, token, draftTitle)
    await seedCompletedMeeting(request, token, publishedTitle)

    await page.goto('/meetings')
    await page.waitForLoadState('networkidle')
    await page.getByLabel('Search meetings').fill(prefix)
    const rows = page.getByTestId('meeting-row')
    await expect(rows.filter({ hasText: draftTitle })).toHaveCount(1)
    await expect(rows.filter({ hasText: publishedTitle })).toHaveCount(1)

    await page.getByRole('tab', { name: /^Draft/ }).click()
    await expect(rows.filter({ hasText: draftTitle })).toHaveCount(1)
    await expect(rows.filter({ hasText: publishedTitle })).toHaveCount(0)

    await page.getByRole('tab', { name: /^Published/ }).click()
    await expect(rows.filter({ hasText: publishedTitle })).toHaveCount(1)
    await expect(rows.filter({ hasText: draftTitle })).toHaveCount(0)

    const publishedRow = rows.filter({ hasText: publishedTitle })
    await publishedRow.getByRole('link', { name: 'View minutes' }).click()
    await expect(page).toHaveURL(/\/meetings\/.+\/review$/)
    await expect(page.getByText('Minutes published').first()).toBeVisible()
  })

  test('paginates meetings and supports rename and delete', async ({ page, request }) => {
    const token = await authenticate(page, request)
    const prefix = uniqueTitle('E2E Paged')
    const now = Date.now()

    for (let index = 0; index < 12; index += 1) {
      await createMeeting(
        request,
        token,
        `${prefix} ${String(index + 1).padStart(2, '0')}`,
        new Date(now + index * 60_000),
        new Date(now + index * 60_000 + 30 * 60_000),
      )
    }

    await page.goto('/meetings')
    await page.waitForLoadState('networkidle')
    await page.getByLabel('Search meetings').fill(prefix)
    await expect(page.getByText(/Showing 1.10 of 12/)).toBeVisible()

    await page.getByRole('button', { name: 'Next' }).click()
    await expect(page.getByText(/Showing 11.12 of 12/)).toBeVisible()
    await expect(page.getByText(/E2E Paged .* 12/)).toBeVisible()

    await page.getByLabel('Rows per page').click()
    await page.getByRole('option', { name: '20 rows' }).click()
    await expect(page.getByText(/Showing 1.12 of 12/)).toBeVisible()

    await page.getByLabel('Search meetings').fill(`${prefix} 01`)
    const row = page.getByTestId('meeting-row').first()
    const originalTitle = `${prefix} 01`
    const renamedTitle = `${prefix} Renamed`
    await expect(row).toContainText(originalTitle)

    await page.getByRole('button', { name: `Actions for ${originalTitle}` }).click()
    await page.getByRole('menuitem', { name: 'Rename' }).click()
    await page.locator('#rename-meeting-title').fill(renamedTitle)
    await page.getByRole('button', { name: 'Save name' }).click()
    await expect(page.getByText('Meeting renamed.')).toBeVisible()
    await page.getByLabel('Search meetings').fill(renamedTitle)
    await expect(page.getByTestId('meeting-row').first()).toContainText(renamedTitle)

    await page.getByRole('button', { name: `Actions for ${renamedTitle}` }).click()
    await page.getByRole('menuitem', { name: 'Delete' }).click()
    await expect(page.getByText('Delete this meeting?')).toBeVisible()
    await page.getByRole('button', { name: 'Delete meeting' }).click()
    await expect(page.getByText('Meeting deleted.')).toBeVisible()
    await expect(page.getByTestId('meeting-row')).toHaveCount(0)
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
    await expect(page.getByText('Meeting created.')).toBeVisible()
    await expect(page).toHaveURL(/\/meetings\/.+\/review$/)
    await expect(page.getByRole('heading', { name: title })).toBeVisible()
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
    await expect(page).toHaveURL(/\/meetings\/.+\/review$/)
    await expect(page.getByRole('heading', { name: 'Computer Science and Engineering meeting' })).toBeVisible()
  })
})
