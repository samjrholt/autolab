// @ts-check
import { test, expect } from "@playwright/test";
import { waitForConnection, navigateTo } from "./helpers.js";

test.describe("Smoke — app boots and every top-level page renders", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/");
    await waitForConnection(page);
  });

  test("sidebar renders the Anthropic-style nav", async ({ page }) => {
    const sidebar = page.locator("aside");
    await expect(sidebar).toContainText("Campaigns");
    await expect(sidebar).toContainText("Library");
    await expect(sidebar).toContainText("Workflows");
    await expect(sidebar).toContainText("Resources");
    await expect(sidebar).toContainText("Capabilities");
    await expect(sidebar).toContainText("Ledger");
    await expect(sidebar).toContainText("Settings");
  });

  test("Campaigns page is the default and shows either a table or empty state", async ({ page }) => {
    await expect(page.getByRole("heading", { name: "Campaigns", exact: true })).toBeVisible();
    // Either the table header "Goal" is visible or the empty-state CTA is
    const hasCampaigns = await page.getByRole("columnheader", { name: "Goal" }).isVisible().catch(() => false);
    if (!hasCampaigns) {
      await expect(page.getByRole("button", { name: /Start your first campaign/i })).toBeVisible();
    }
  });

  test("can navigate to every library page", async ({ page }) => {
    for (const label of ["Workflows", "Resources", "Capabilities"]) {
      await navigateTo(page, label);
      await expect(page.getByRole("heading", { name: label, exact: true })).toBeVisible({ timeout: 5_000 });
    }
  });

  test("Ledger page renders records or an empty state", async ({ page }) => {
    await navigateTo(page, "Ledger");
    // either table columns visible, or empty-state heading
    const hasLedger = await page.getByRole("columnheader", { name: /Time/ }).isVisible().catch(() => false);
    if (!hasLedger) {
      await expect(page.getByText(/ledger is empty/i)).toBeVisible();
    }
  });

  test("Settings page shows section sub-nav", async ({ page }) => {
    await navigateTo(page, "Settings");
    await expect(page.getByRole("heading", { name: "Settings", exact: true })).toBeVisible();
    await expect(page.getByText("API keys", { exact: true }).first()).toBeVisible();
    await expect(page.getByText("Setup Assistant", { exact: true }).first()).toBeVisible();
  });

  test("TopBar shows the connection pill", async ({ page }) => {
    // "live" or "disconnected" text is always present in the top bar
    const pill = page.getByText(/^(live|disconnected)$/);
    await expect(pill.first()).toBeVisible();
  });
});
