// @ts-check
import { test, expect } from "@playwright/test";
import { waitForConnection, openSettings, closeSlideOver } from "./helpers.js";

test.describe("Resource registration", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/");
    await waitForConnection(page);
    await openSettings(page);
  });

  test("Settings drawer shows Resources section with bootstrapped resource", async ({ page }) => {
    await expect(page.getByText("pc-1")).toBeVisible();
  });

  test("Manual mode — register a resource with kind and capabilities", async ({ page }) => {
    // The Resources section should have a Manual | With Claude tab
    const resourcesSection = page.locator("section", { has: page.getByText("Resources", { exact: false }) });

    // Click Manual tab (should be default)
    const manualTab = resourcesSection.getByRole("button", { name: "Manual" });
    if (await manualTab.isVisible()) {
      await manualTab.click();
    }

    // Fill in the resource form
    await resourcesSection.getByPlaceholder("Resource name").fill("tube-furnace-A");

    // Select furnace kind from dropdown
    const kindSelect = resourcesSection.locator("select").first();
    await kindSelect.selectOption("furnace");

    // After selecting furnace, capabilities should auto-populate
    // Check that max_temp_k preset appeared
    await expect(resourcesSection.getByDisplayValue("max_temp_k")).toBeVisible({ timeout: 3_000 });

    // Fill description
    await resourcesSection.getByPlaceholder(/description/i).fill("Main tube furnace");

    // Click Add resource
    await resourcesSection.getByRole("button", { name: /add resource/i }).click();

    // Wait for refresh and verify the resource appears in the list
    await expect(page.getByText("tube-furnace-A")).toBeVisible({ timeout: 5_000 });
    await expect(page.getByText("furnace")).toBeVisible();
  });

  test("Manual mode — bulk add multiple resources", async ({ page }) => {
    const resourcesSection = page.locator("section", { has: page.getByText("Resources", { exact: false }) });

    await resourcesSection.getByPlaceholder("Resource name").fill("gpu-node");
    const kindSelect = resourcesSection.locator("select").first();
    await kindSelect.selectOption("gpu_node");

    // Set count to 3
    const countInput = resourcesSection.locator('input[type="number"]');
    await countInput.fill("3");

    await resourcesSection.getByRole("button", { name: /add 3 resources/i }).click();

    // Should create gpu-node-1, gpu-node-2, gpu-node-3
    await expect(page.getByText("gpu-node-1")).toBeVisible({ timeout: 5_000 });
    await expect(page.getByText("gpu-node-2")).toBeVisible();
    await expect(page.getByText("gpu-node-3")).toBeVisible();
  });

  test("Claude mode — shows the design prompt textarea", async ({ page }) => {
    const resourcesSection = page.locator("section", { has: page.getByText("Resources", { exact: false }) });

    // Switch to Claude mode
    const claudeTab = resourcesSection.getByRole("button", { name: "With Claude" });
    await claudeTab.click();

    // Should show a textarea for describing the resource
    await expect(
      resourcesSection.getByPlaceholder(/describe your resource/i)
    ).toBeVisible();

    // Should show a "Propose resource" button
    await expect(
      resourcesSection.getByRole("button", { name: /propose resource/i })
    ).toBeVisible();
  });
});
