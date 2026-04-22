// @ts-check
import { test, expect } from "@playwright/test";
import { waitForConnection, navigateTo } from "./helpers.js";

test.describe("Setup Assistant — page reachable and renders correctly", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/");
    await waitForConnection(page);
  });

  test("Assistant is reachable from the sidebar", async ({ page }) => {
    await navigateTo(page, "Assistant");
    await expect(page.getByRole("heading", { name: "Setup Assistant", exact: true })).toBeVisible();
  });

  test("Assistant shows the chat surface or the no-key empty state", async ({ page }) => {
    await navigateTo(page, "Assistant");
    // Either the chat textarea is visible, or the "no key" empty state
    const hasChat = await page.locator("textarea").isVisible().catch(() => false);
    if (hasChat) {
      // Initial assistant greeting should be present
      await expect(page.getByText(/Hi — I'm Claude/i)).toBeVisible();
    } else {
      await expect(page.getByText(/API key not detected/i)).toBeVisible();
    }
  });
});
