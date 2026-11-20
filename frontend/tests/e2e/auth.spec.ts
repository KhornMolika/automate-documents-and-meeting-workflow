import { expect, test } from '@playwright/test'
import { loginTokens } from './api'

test.describe('Authentication', () => {
  test('redirects unauthenticated visitors, signs in and signs out', async ({ page }) => {
    await page.context().clearCookies()
    await page.goto('/')
    await page.waitForLoadState('networkidle')
    await expect(page).toHaveURL(/\/login(\?|$)/)
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

  test('keeps the requested page and toggles password visibility', async ({ page }) => {
    await page.context().clearCookies()
    await page.goto('/tasks')
    await expect(page).toHaveURL(/\/login\?redirect=(%2F|\/)tasks/)

    await page.locator('#email').fill('admin@aub.edu.kh')
    await page.locator('#password').fill('Admin@AUB2026')
    await page.getByRole('button', { name: 'Show password' }).click()
    await expect(page.locator('#password')).toHaveAttribute('type', 'text')
    await page.getByRole('button', { name: 'Sign in' }).click()

    await expect(page).toHaveURL(/\/tasks$/)
    await expect(page.getByRole('heading', { level: 1, name: 'Tasks' })).toBeVisible()
  })

  test('explains an expired session', async ({ page }) => {
    await page.context().clearCookies()
    await page.goto('/login?reason=session-expired')
    await expect(page.getByText('Your session expired. Sign in again to continue where you left off.')).toBeVisible()
  })

  test('refreshes an expired access token with the refresh cookie', async ({ page, request }) => {
    const tokens = await loginTokens(request)
    await page.context().addCookies([
      { name: 'aub_access_token', value: '', url: 'http://127.0.0.1:3000' },
      { name: 'aub_refresh_token', value: tokens.refresh_token, url: 'http://127.0.0.1:3000' },
    ])
    await page.context().clearCookies({ name: 'aub_access_token' })

    await page.goto('/tasks')
    await expect(page).toHaveURL(/\/tasks$/)
    await expect(page.getByRole('heading', { level: 1, name: 'Tasks' })).toBeVisible()
  })
})
