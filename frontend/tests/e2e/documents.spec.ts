import { expect, test } from '@playwright/test'
import { authenticate, seedDocument, uniqueTitle } from './api'
import { expectOverlayBlur } from './helpers'

test.describe('Documents', () => {
  test('searches real documents and closes the detail dialog every way', async ({ page, request }) => {
    const token = await authenticate(page, request)
    const title = uniqueTitle('E2E Searchable Policy')
    await seedDocument(request, token, title)

    await page.goto('/documents')
    await page.waitForLoadState('networkidle')
    await page.getByLabel('Search documents').fill(title)
    const row = page.getByTestId('document-table').locator('tbody tr').first()
    await expect(row).toContainText(title)

    await row.getByRole('button', { name: 'Open' }).click()
    const dialog = page.getByTestId('document-detail')
    await expect(dialog.getByRole('heading', { name: title })).toBeVisible()
    await expect(dialog).toContainText('Summary')
    await expectOverlayBlur(page)
    await dialog.getByRole('button', { name: 'Close' }).click()
    await expect(dialog).toHaveCount(0)

    await row.getByRole('button', { name: 'Open' }).click()
    await expect(dialog).toBeVisible()
    await dialog.getByRole('button', { name: 'Done' }).click()
    await expect(dialog).toHaveCount(0)

    await row.getByRole('button', { name: 'Open' }).click()
    await expect(dialog).toBeVisible()
    await page.keyboard.press('Escape')
    await expect(dialog).toHaveCount(0)
  })

  test('uploads a real document and closes the upload dialog by X and Cancel', async ({ page, request }) => {
    await authenticate(page, request)
    const title = uniqueTitle('E2E Uploaded Policy')

    await page.goto('/documents')
    await page.waitForLoadState('networkidle')
    await page.getByRole('button', { name: 'Upload document' }).click()
    const dialog = page.getByTestId('upload-document')
    await expect(dialog).toBeVisible()
    await expectOverlayBlur(page)
    await dialog.getByRole('button', { name: 'Close' }).click()
    await expect(dialog).toHaveCount(0)

    await page.getByRole('button', { name: 'Upload document' }).click()
    await expect(dialog).toBeVisible()
    await dialog.getByRole('button', { name: 'Cancel' }).click()
    await expect(dialog).toHaveCount(0)

    await page.getByRole('button', { name: 'Upload document' }).click()
    await expect(dialog).toBeVisible()
    await dialog.getByLabel('Title').fill(title)
    await dialog.locator('#document-category').click()
    await page.getByRole('option', { name: 'Academic Policy' }).click()
    await expect(dialog.locator('#document-category')).toContainText('Academic Policy')
    await dialog.locator('#document-file').setInputFiles({
      name: 'e2e_policy.csv',
      mimeType: 'text/csv',
      buffer: Buffer.from(`Policy,Owner\n${title},Academic Affairs\n`),
    })
    await dialog.getByRole('button', { name: 'Add document' }).click()
    await expect(dialog).toHaveCount(0)
    await page.getByLabel('Search documents').fill(title)
    await expect(page.getByTestId('document-table')).toContainText(title)
    await expect(page.getByText('Document uploaded.', { exact: false })).toBeVisible()
  })
})
