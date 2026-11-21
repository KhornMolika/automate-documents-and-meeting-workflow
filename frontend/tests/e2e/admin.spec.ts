import { expect, test } from '@playwright/test'
import { authenticate } from './api'

test.describe('Administration', () => {
  test('shows users, roles and departments to an administrator', async ({ page, request }) => {
    await authenticate(page, request)

    await page.goto('/admin')
    await page.waitForLoadState('networkidle')

    await expect(page.getByRole('heading', { level: 1, name: 'Administration' })).toBeVisible()
    await expect(page.getByText('Users', { exact: true })).toBeVisible()
    await expect(page.getByText('Departments', { exact: true })).toBeVisible()
    await expect(page.getByText('admin@aub.edu.kh')).toBeVisible()
    await expect(page.getByRole('button', { name: 'New user' })).toBeVisible()
    await expect(page.getByRole('button', { name: 'New department' })).toBeVisible()
    await expect(page.getByText('Could not load this view')).toHaveCount(0)
  })
})
