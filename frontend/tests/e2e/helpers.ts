import { expect, type Page } from '@playwright/test'

export async function expectOverlayBlur(page: Page) {
  const overlay = page.getByTestId('dialog-overlay')
  await expect(overlay).toBeVisible()
  const styles = await overlay.evaluate((element) => {
    const style = getComputedStyle(element)
    return { background: style.backgroundColor, blur: style.backdropFilter }
  })
  expect(styles.background).toContain('0.5')
  expect(styles.blur).toContain('blur')
}

export async function expectNoHorizontalOverflow(page: Page) {
  const fits = await page.evaluate(
    () => document.documentElement.scrollWidth <= window.innerWidth + 1,
  )
  expect(fits).toBe(true)
}
