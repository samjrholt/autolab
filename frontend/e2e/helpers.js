// @ts-check
/**
 * Shared helpers for autolab Playwright E2E tests, updated for the
 * Anthropic-style sidebar shell.
 */

/**
 * Wait for the app to boot and connect to the backend.
 */
export async function waitForConnection(page) {
  // sidebar renders synchronously; top-bar's connection pill flips to green on WS open
  await page.waitForSelector("aside", { timeout: 15_000 });
  await page.waitForSelector("text=Campaigns", { timeout: 10_000 });
  // wait for at least one render pass after /status resolves
  await page.waitForLoadState("networkidle", { timeout: 5_000 }).catch(() => {});
}

/**
 * Navigate to a top-level sidebar page by its label.
 * @param {import('@playwright/test').Page} page
 * @param {"Campaigns"|"Workflows"|"Resources"|"Capabilities"|"Ledger"|"Settings"} label
 */
export async function navigateTo(page, label) {
  // First aside is the AppShell sidebar (the Settings page renders a second aside
  // for its sub-nav once loaded).
  const sidebar = page.locator("aside").first();
  await sidebar.getByRole("button", { name: label, exact: true }).click();
  await page.waitForTimeout(120);
}

/**
 * Click the primary "+ New …" CTA in a page header.
 */
export async function clickPrimary(page, text) {
  await page.getByRole("button", { name: text }).first().click();
}

/**
 * Close any open slide-over.
 */
export async function closeSlideOver(page) {
  const closeBtn = page.locator('.slide-panel button:has-text("✕")');
  if (await closeBtn.isVisible().catch(() => false)) {
    await closeBtn.click();
    await page.waitForTimeout(300);
  }
}
