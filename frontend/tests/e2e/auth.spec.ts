import { expect, test } from '@playwright/test'

test.describe('Authentication', () => {
  test('redirects unauthenticated visitors, signs in and signs out', async ({ page }) => {
    await page.context().clearCookies()
    await page.goto('/')
    await page.waitForLoadState('networkidle')
    await expect(page).toHaveURL(/\/login$/)
    await expect(page.getByRole('heading', { level: 1, name: 'Sign in' })).toBeVisible()

    await page.locator('#password').fill('Admin@AUB2026')
    await page.getByRole('button', { name: 'Sign in' }).click()

    await expect(page).toHaveURL(/\/$/)
    await expect(page.getByRole('heading', { level: 1, name: 'Overview' })).toBeVisible()
    await page.getByRole('button', { name: 'Sign out' }).click()
    await expect(page).toHaveURL(/\/login$/)
  })

  test('rejects a wrong password', async ({ page }) => {
    await page.goto('/login')
    await page.waitForLoadState('networkidle')
    await page.locator('#password').fill('not-the-password')
    await page.getByRole('button', { name: 'Sign in' }).click()
    await expect(page.getByText('Incorrect email or password')).toBeVisible()
    await expect(page).toHaveURL(/\/login$/)
  })
})
