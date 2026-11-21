import { expect, test } from '@playwright/test'
import { authenticate, seedCompletedMeeting, seedDocument, uniqueTitle } from './api'

test.describe('Overview', () => {
  test('shows real meetings, documents and action items from the API', async ({ page, request }) => {
    const token = await authenticate(page, request)
    const completedTitle = uniqueTitle('E2E Completed Review')
    const documentTitle = uniqueTitle('E2E Overview Policy')

    await seedCompletedMeeting(request, token, completedTitle)
    await seedDocument(request, token, documentTitle)

    await page.goto('/')
    await page.waitForLoadState('networkidle')

    await expect(page.getByRole('heading', { level: 1, name: 'Overview' })).toBeVisible()
    await expect(page.getByText('Next meeting')).toBeVisible()
    await expect(page.getByText('Recent documents')).toBeVisible()
    await expect(page.getByText(documentTitle)).toBeVisible()
    await expect(page.getByText('Submit the E2E ethics approval.', { exact: true }).first()).toBeVisible()
    await expect(page.getByText('Could not load this view')).toHaveCount(0)
  })

  test('sidebar links expose the authenticated API reference', async ({ page, request }) => {
    await authenticate(page, request)
    await page.goto('/')
    await expect(page.getByRole('link', { name: 'Documents', exact: true })).toBeVisible()
    await page.getByRole('link', { name: 'Documents', exact: true }).click()
    await expect(page).toHaveURL(/\/documents$/)
    await expect(page.getByRole('heading', { level: 1, name: 'Documents' })).toBeVisible()
    await expect(page.getByRole('link', { name: 'API reference' })).toHaveAttribute(
      'href',
      'http://127.0.0.1:8000/docs',
    )
    await expect(page.getByRole('link', { name: 'Tasks', exact: true })).toBeVisible()
  })
})
