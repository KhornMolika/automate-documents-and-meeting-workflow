import { expect, test } from '@playwright/test'
import { authenticate, seedDocument, seedTranscriptMeeting, uniqueTitle } from './api'
import { expectNoHorizontalOverflow } from './helpers'

test.use({ viewport: { width: 390, height: 844 } })

test.describe('Mobile layout', () => {
  test('navigation sheet opens, closes by X, and navigates', async ({ page, request }) => {
    await authenticate(page, request)
    await page.goto('/')
    await page.waitForLoadState('networkidle')

    await page.getByRole('button', { name: 'Open navigation' }).click()
    const nav = page.getByTestId('mobile-nav')
    await expect(nav).toBeVisible()
    await expect(page.getByTestId('sheet-overlay')).toBeVisible()

    const overlay = await page.getByTestId('sheet-overlay').evaluate((element) => {
      const style = getComputedStyle(element)
      return { background: style.backgroundColor, blur: style.backdropFilter }
    })
    expect(overlay.background).toContain('0.5')
    expect(overlay.blur).toContain('blur')

    await nav.getByRole('button', { name: 'Close' }).click()
    await expect(nav).toHaveCount(0)

    await page.getByRole('button', { name: 'Open navigation' }).click()
    await nav.getByRole('link', { name: 'Documents', exact: true }).click()
    await expect(page).toHaveURL(/\/documents$/)
    await expect(page.getByRole('heading', { level: 1, name: 'Documents' })).toBeVisible()
  })

  test('core screens fit the phone width', async ({ page, request }) => {
    const token = await authenticate(page, request)
    await seedDocument(request, token, uniqueTitle('E2E Mobile Document'))
    for (const path of ['/', '/documents', '/meetings', '/tasks']) {
      await page.goto(path)
      await page.waitForLoadState('networkidle')
      await expectNoHorizontalOverflow(page)
    }
  })

  test('document dialog and meeting workspace fit on a phone', async ({ page, request }) => {
    const token = await authenticate(page, request)
    const documentTitle = uniqueTitle('E2E Mobile Dialog')
    const meetingTitle = uniqueTitle('E2E Mobile Workspace')
    await seedDocument(request, token, documentTitle)
    const meeting = await seedTranscriptMeeting(request, token, meetingTitle)

    await page.goto('/documents')
    await page.waitForLoadState('networkidle')
    await page.getByLabel('Search documents').fill(documentTitle)
    const row = page.getByTestId('document-table').locator('tbody tr').first()
    await row.getByRole('button').first().click()

    const dialog = page.getByTestId('document-detail')
    await expect(dialog).toBeVisible()
    const box = await dialog.boundingBox()
    expect(box).not.toBeNull()
    expect(box!.x).toBeGreaterThanOrEqual(0)
    expect(box!.width).toBeLessThanOrEqual(390)
    expect(box!.height).toBeLessThanOrEqual(844)
    await expectNoHorizontalOverflow(page)
    await page.keyboard.press('Escape')
    await expect(dialog).toHaveCount(0)

    await page.goto(`/meetings/${meeting.id}/review`)
    await page.waitForLoadState('networkidle')
    await expectNoHorizontalOverflow(page)
  })
})
