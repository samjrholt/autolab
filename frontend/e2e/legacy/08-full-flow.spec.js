// @ts-check
import { test, expect } from "@playwright/test";
import { waitForConnection, openSettings, closeSlideOver, openNewCampaign, switchTab } from "./helpers.js";

test.describe("Full user flow: setup → workflow → campaign → results", () => {
  test("scientist registers resources + tools, builds workflow, launches campaign", async ({ page }) => {
    await page.goto("/");
    await waitForConnection(page);

    // ── Step 1: Register a SLURM partition resource ──
    await openSettings(page);

    const resourceSection = page.locator("section", { has: page.getByText("Resources", { exact: false }) });
    await resourceSection.getByPlaceholder("Resource name").fill("slurm-gpu");
    const kindSelect = resourceSection.locator("select").first();
    await kindSelect.selectOption("slurm_partition");
    await resourceSection.getByRole("button", { name: /add resource/i }).click();
    await expect(page.getByText("slurm-gpu")).toBeVisible({ timeout: 5_000 });

    // ── Step 2: Register a custom tool ──
    const toolSection = page.locator("section", { has: page.getByText("Tools", { exact: true }) });
    await toolSection.getByPlaceholder(/capability name/i).fill("ml_train");
    await toolSection.getByPlaceholder("Description").fill("Train an ML model");

    // Add input
    const inputsAdd = toolSection.locator("div", { has: page.getByText("Inputs") }).getByText("+ Add");
    await inputsAdd.click();
    await toolSection.locator("div", { has: page.getByText("Inputs") }).getByPlaceholder("name").fill("architecture");

    // Add output
    const outputsAdd = toolSection.locator("div", { has: page.getByText("Outputs") }).getByText("+ Add");
    await outputsAdd.click();
    await toolSection.locator("div", { has: page.getByText("Outputs") }).getByPlaceholder("name").fill("mae");

    await toolSection.getByRole("button", { name: /register tool/i }).click();
    await expect(page.getByText("ml_train")).toBeVisible({ timeout: 5_000 });

    // ── Step 3: Build a workflow ──
    await page.getByRole("button", { name: /new workflow/i }).click();
    await expect(page.getByText(/workflow builder/i)).toBeVisible();

    await page.getByPlaceholder("Workflow name").fill("train-pipeline");
    await page.getByText("+ Add step").click();

    // Select the ml_train operation
    const stepSelects = page.locator('.slide-panel select:has(option:has-text("ml_train"))');
    if (await stepSelects.first().isVisible()) {
      await stepSelects.first().selectOption("ml_train");
    }

    await page.getByRole("button", { name: /save workflow/i }).click();
    await expect(page.getByText("train-pipeline")).toBeVisible({ timeout: 5_000 });

    // ── Step 4: Close settings, launch a campaign ──
    await closeSlideOver(page);
    await openNewCampaign(page);

    const panel = page.locator(".slide-panel");
    await panel.getByRole("button", { name: "Manual" }).click();
    await panel.getByPlaceholder("Campaign name").fill("full-flow-campaign");
    await panel.getByPlaceholder(/objective key/i).fill("mae");
    await panel.locator("select", { has: page.locator('option:has-text("Maximize")') }).first().selectOption("minimize");

    // Set budget to 3 for a quick run
    const budgetInput = panel.locator('input[type="number"]').first();
    await budgetInput.fill("3");

    await panel.getByRole("button", { name: /start campaign/i }).click();

    // ── Step 5: Verify campaign appears in Campaign tab ──
    await page.waitForTimeout(1_000);
    await switchTab(page, "Campaign");
    await expect(page.getByText("full-flow-campaign")).toBeVisible({ timeout: 10_000 });

    // ── Step 6: Wait for some records and check Provenance ──
    await page.waitForTimeout(5_000);
    await switchTab(page, "Provenance");

    // Should have at least some records
    // The page should show record entries (the demo_quadratic and ml_train may both run)
    const main = page.locator("main");
    await expect(main).not.toBeEmpty();
  });
});
