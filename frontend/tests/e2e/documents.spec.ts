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
    const openTitle = row.getByRole('button').first()

    await openTitle.click()
    const dialog = page.getByTestId('document-detail')
    await expect(dialog.getByRole('heading', { name: title })).toBeVisible()
    await expect(dialog).toContainText('Summary')
    await expectOverlayBlur(page)
    await dialog.getByRole('button', { name: 'Close' }).click()
    await expect(dialog).toHaveCount(0)

    await openTitle.click()
    await expect(dialog).toBeVisible()
    await dialog.getByRole('button', { name: 'Done' }).click()
    await expect(dialog).toHaveCount(0)

    await openTitle.click()
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

  test('renames, versions, archives, restores, downloads and deletes a document', async ({ page, request }) => {
    const token = await authenticate(page, request)
    const title = uniqueTitle('E2E Action Document')
    const renamedTitle = `${title} Renamed`
    await seedDocument(request, token, title)

    await page.goto('/documents')
    await page.waitForLoadState('networkidle')
    await page.getByLabel('Search documents').fill(title)
    let row = page.getByTestId('document-table').locator('tbody tr').first()
    await expect(row).toContainText(title)

    await row.getByRole('button', { name: `Actions for ${title}` }).click()
    await page.getByRole('menuitem', { name: 'Rename' }).click()
    await page.locator('#rename-document-title').fill(renamedTitle)
    await page.getByRole('button', { name: 'Save name' }).click()
    await expect(page.getByText('Document renamed.')).toBeVisible()
    await page.getByLabel('Search documents').fill(renamedTitle)
    row = page.getByTestId('document-table').locator('tbody tr').first()
    await expect(row).toContainText(renamedTitle)

    const downloadPromise = page.waitForEvent('download')
    await row.getByRole('button', { name: `Actions for ${renamedTitle}` }).click()
    await page.getByRole('menuitem', { name: 'Download' }).click()
    const download = await downloadPromise
    expect(download.suggestedFilename()).toContain('e2e_')

    await row.getByRole('button', { name: `Actions for ${renamedTitle}` }).click()
    await page.getByRole('menuitem', { name: 'New version' }).click()
    await page.locator('#document-version-file').setInputFiles({
      name: 'e2e_policy_v2.csv',
      mimeType: 'text/csv',
      buffer: Buffer.from('Policy,Owner\nUpdated version,Academic Affairs\n'),
    })
    await page.getByRole('button', { name: 'Upload version' }).click()
    await expect(page.getByText('Version 2 uploaded.')).toBeVisible()

    await row.getByRole('button', { name: `Actions for ${renamedTitle}` }).click()
    await page.getByRole('menuitem', { name: 'Archive' }).click()
    await expect(page.getByText('Document archived.')).toBeVisible()
    await page.getByRole('button', { name: /Archived \(/ }).click()
    await expect(page.getByTestId('document-table')).toContainText(renamedTitle)

    row = page.getByTestId('document-table').locator('tbody tr').first()
    await row.getByRole('button', { name: `Actions for ${renamedTitle}` }).click()
    await page.getByRole('menuitem', { name: 'Restore' }).click()
    await expect(page.getByText('Document restored.')).toBeVisible()
    await page.getByRole('button', { name: 'Back to active documents' }).click()
    await expect(page.getByTestId('document-table')).toContainText(renamedTitle)

    row = page.getByTestId('document-table').locator('tbody tr').first()
    await row.getByRole('button', { name: `Actions for ${renamedTitle}` }).click()
    await page.getByRole('menuitem', { name: 'Delete' }).click()
    await expect(page.getByText('Delete this document?')).toBeVisible()
    await page.getByRole('button', { name: 'Delete document' }).click()
    await expect(page.getByText('Document deleted.')).toBeVisible()
    await expect(page.getByTestId('document-table')).toHaveCount(0)
  })

  test('creates a folder and moves a document into it', async ({ page, request }) => {
    const token = await authenticate(page, request)
    const title = uniqueTitle('E2E Foldered Document')
    const folderName = uniqueTitle('E2E Folder')
    await seedDocument(request, token, title)

    await page.goto('/documents')
    await page.waitForLoadState('networkidle')
    await page.getByRole('button', { name: 'New folder' }).click()
    await page.locator('#folder-name').fill(folderName)
    await page.getByRole('button', { name: 'Save folder' }).click()
    await expect(page.getByText('Folder created.')).toBeVisible()

    await page.getByLabel('Search documents').fill(title)
    const row = page.getByTestId('document-table').locator('tbody tr').first()
    await row.getByRole('button', { name: `Actions for ${title}` }).click()
    await page.getByRole('menuitem', { name: 'Move to folder' }).click()
    await page.locator('#move-folder').click()
    await page.getByRole('option', { name: folderName }).click()
    await page.getByRole('button', { name: 'Move document' }).click()
    await expect(page.getByText('Document moved.')).toBeVisible()

    await page.getByLabel('Search documents').fill('')
    await page.getByRole('button', { name: new RegExp(folderName) }).first().click()
    await expect(page.getByTestId('document-table')).toContainText(title)
  })

  test('imports a Google Sheets link through the upload dialog', async ({ page, request }) => {
    await authenticate(page, request)
    await page.goto('/documents')
    await page.waitForLoadState('networkidle')
    await page.getByRole('button', { name: 'Upload document' }).click()
    const dialog = page.getByTestId('upload-document')
    await dialog.getByRole('tab', { name: 'Google Drive link' }).click()

    let payload: Record<string, string> | undefined
    await page.route('**/api/v1/documents/import/google', async route => {
      payload = route.request().postDataJSON() as Record<string, string>
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          id: 'google-doc-1',
          title: payload.title,
          department_id: 'dep-1',
          academic_year: payload.academic_year,
          current_version: 1,
          is_archived: false,
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
          versions: [],
          latest_version: null,
        }),
      })
    })

    await dialog.getByLabel('Title').fill('Imported Google Sheet')
    await dialog.getByLabel('Google Docs, Sheets, Slides or Drive link').fill('https://docs.google.com/spreadsheets/d/abc123/edit#gid=0')
    await dialog.getByRole('button', { name: 'Import from Google' }).click()

    await expect(dialog).toHaveCount(0)
    expect(payload?.url).toContain('docs.google.com/spreadsheets/d/abc123')
    await expect(page.getByText('Document uploaded.', { exact: false })).toBeVisible()
  })
})
