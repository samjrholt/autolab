// @ts-check
import { test, expect } from "@playwright/test";
import { waitForConnection, openSettings, openNewCampaign } from "./helpers.js";

test.describe("Dual-mode (Manual | With Claude) UX consistency", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/");
    await waitForConnection(page);
  });

  test("Resources — switching modes preserves section visibility", async ({ page }) => {
    await openSettings(page);
    const section = page.locator("section", { has: page.getByText("Resources", { exact: false }) });

    // Manual tab should be active by default
    const manualTab = section.getByRole("button", { name: "Manual" });
    const claudeTab = section.getByRole("button", { name: "With Claude" });

    await expect(manualTab).toBeVisible();
    await expect(claudeTab).toBeVisible();

    // Manual mode: form inputs visible
    await expect(section.getByPlaceholder("Resource name")).toBeVisible();

    // Switch to Claude mode
    await claudeTab.click();
    await expect(section.getByPlaceholder(/describe your resource/i)).toBeVisible();

    // Switch back to Manual mode
    await manualTab.click();
    await expect(section.getByPlaceholder("Resource name")).toBeVisible();
  });

  test("Tools — switching modes preserves section visibility", async ({ page }) => {
    await openSettings(page);
    const section = page.locator("section", { has: page.getByText("Tools", { exact: true }) });

    const manualTab = section.getByRole("button", { name: "Manual" });
    const claudeTab = section.getByRole("button", { name: "With Claude" });

    await expect(manualTab).toBeVisible();
    await expect(claudeTab).toBeVisible();

    await expect(section.getByPlaceholder(/capability name/i)).toBeVisible();

    await claudeTab.click();
    await expect(section.getByPlaceholder(/describe a tool/i)).toBeVisible();

    await manualTab.click();
    await expect(section.getByPlaceholder(/capability name/i)).toBeVisible();
  });

  test("Campaign — switching modes preserves the slide-over", async ({ page }) => {
    await openNewCampaign(page);
    const panel = page.locator(".slide-panel");

    const manualTab = panel.getByRole("button", { name: "Manual" });
    const claudeTab = panel.getByRole("button", { name: "With Claude" });

    await manualTab.click();
    await expect(panel.getByPlaceholder("Campaign name")).toBeVisible();

    await claudeTab.click();
    await expect(panel.getByPlaceholder(/describe what you want/i)).toBeVisible();

    await manualTab.click();
    await expect(panel.getByPlaceholder("Campaign name")).toBeVisible();
  });

  test("Workflow builder — both modes available", async ({ page }) => {
    await openSettings(page);
    await page.getByRole("button", { name: /new workflow/i }).click();

    const builder = page.locator("div", { has: page.getByText("Workflow builder") });

    const manualTab = builder.getByRole("button", { name: "Manual" });
    const claudeTab = builder.getByRole("button", { name: "With Claude" });

    await expect(manualTab).toBeVisible();
    await expect(claudeTab).toBeVisible();

    // Manual mode has workflow name + steps
    await manualTab.click();
    await expect(page.getByPlaceholder("Workflow name")).toBeVisible();

    // Claude mode has the prompt
    await claudeTab.click();
    await expect(page.getByPlaceholder(/describe your workflow/i)).toBeVisible();
  });
});
