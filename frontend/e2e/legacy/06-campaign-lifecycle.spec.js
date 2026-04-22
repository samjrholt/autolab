// @ts-check
import { test, expect } from "@playwright/test";
import { waitForConnection, openNewCampaign, switchTab } from "./helpers.js";

test.describe("Campaign lifecycle — run, monitor, export", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/");
    await waitForConnection(page);
  });

  test("start a campaign, see records appear, view record detail", async ({ page }) => {
    // Start a campaign via manual mode
    await openNewCampaign(page);
    const panel = page.locator(".slide-panel");
    await panel.getByRole("button", { name: "Manual" }).click();
    await panel.getByPlaceholder("Campaign name").fill("lifecycle-test");
    await panel.getByPlaceholder(/objective key/i).fill("output");
    await panel.getByRole("button", { name: /start campaign/i }).click();

    // Wait for campaign to start executing
    await page.waitForTimeout(2_000);

    // Switch to Campaign tab
    await switchTab(page, "Campaign");
    await expect(page.getByText("lifecycle-test")).toBeVisible({ timeout: 10_000 });

    // Records should start appearing (the demo_quadratic runs fast)
    await page.waitForTimeout(3_000);

    // Switch to Provenance tab to see records
    await switchTab(page, "Provenance");
    // Should see at least one record row with the operation name
    await expect(page.getByText("demo_quadratic").first()).toBeVisible({ timeout: 15_000 });
  });

  test("Campaign tab shows export buttons (RO-Crate + PROV)", async ({ page }) => {
    // Start a quick campaign first
    await openNewCampaign(page);
    const panel = page.locator(".slide-panel");
    await panel.getByRole("button", { name: "Manual" }).click();
    await panel.getByPlaceholder("Campaign name").fill("export-test");
    await panel.getByPlaceholder(/objective key/i).fill("output");
    await panel.getByRole("button", { name: /start campaign/i }).click();

    await page.waitForTimeout(1_000);
    await switchTab(page, "Campaign");
    await expect(page.getByText("export-test")).toBeVisible({ timeout: 10_000 });

    // Export buttons should be visible in the campaign header area
    await expect(page.getByText("RO-Crate")).toBeVisible({ timeout: 5_000 });
    await expect(page.getByText("PROV")).toBeVisible();
  });
});
