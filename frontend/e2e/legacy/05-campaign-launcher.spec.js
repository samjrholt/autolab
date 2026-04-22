// @ts-check
import { test, expect } from "@playwright/test";
import { waitForConnection, openNewCampaign, switchTab } from "./helpers.js";

test.describe("Campaign launcher", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/");
    await waitForConnection(page);
  });

  test("opens the New Campaign slide-over", async ({ page }) => {
    await openNewCampaign(page);
    await expect(page.getByText("New campaign")).toBeVisible();
    await expect(page.getByText(/configure your campaign/i)).toBeVisible();
  });

  test("Manual mode — shows planner picker with descriptions", async ({ page }) => {
    await openNewCampaign(page);

    // Should show Manual tab
    const manualTab = page.locator(".slide-panel").getByRole("button", { name: "Manual" });
    await manualTab.click();

    // Should show planner options
    await expect(page.getByText("Heuristic")).toBeVisible();
    await expect(page.getByText(/bayesian optimisation/i)).toBeVisible();
    await expect(page.getByText("Optuna")).toBeVisible();
    await expect(page.getByText(/claude.*llm/i)).toBeVisible();
  });

  test("Manual mode — fill campaign form with objective and acceptance criteria", async ({ page }) => {
    await openNewCampaign(page);

    const panel = page.locator(".slide-panel");
    const manualTab = panel.getByRole("button", { name: "Manual" });
    await manualTab.click();

    // Fill campaign name
    await panel.getByPlaceholder("Campaign name").fill("test-heuristic");

    // Fill objective
    await panel.getByPlaceholder(/objective key/i).fill("score");
    await panel.locator("select", { has: page.locator('option:has-text("Maximize")') }).first().selectOption("minimize");

    // Select Heuristic planner (should be default)
    const heuristicRadio = panel.locator('input[value="heuristic"]');
    await expect(heuristicRadio).toBeChecked();

    // Set budget
    const budgetInput = panel.locator('input[type="number"]').first();
    await budgetInput.fill("5");

    // Add an acceptance criterion
    await panel.getByText("+ Add rule").click();
    await panel.getByPlaceholder("output_key").fill("score");
    await panel.getByPlaceholder("threshold").fill("0.95");
  });

  test("Manual mode — start a campaign and see it in Campaign tab", async ({ page }) => {
    await openNewCampaign(page);

    const panel = page.locator(".slide-panel");
    const manualTab = panel.getByRole("button", { name: "Manual" });
    await manualTab.click();

    await panel.getByPlaceholder("Campaign name").fill("e2e-test-campaign");
    await panel.getByPlaceholder(/objective key/i).fill("output");

    await panel.getByRole("button", { name: /start campaign/i }).click();

    // Panel should close and we should be able to see the campaign
    await page.waitForTimeout(1_000);

    await switchTab(page, "Campaign");
    await expect(page.getByText("e2e-test-campaign")).toBeVisible({ timeout: 10_000 });
  });

  test("Claude mode — shows the design textarea and design button", async ({ page }) => {
    await openNewCampaign(page);

    const panel = page.locator(".slide-panel");
    await panel.getByRole("button", { name: "With Claude" }).click();

    // Should show the prompt textarea
    await expect(panel.getByPlaceholder(/describe what you want/i)).toBeVisible();

    // Should show Design button
    await expect(panel.getByRole("button", { name: "Design" })).toBeVisible();
  });

  test("Planner selection shows config form for BO", async ({ page }) => {
    await openNewCampaign(page);

    const panel = page.locator(".slide-panel");
    await panel.getByRole("button", { name: "Manual" }).click();

    // Select BO planner
    await panel.locator('input[value="bo"]').click();

    // Should show BO config panel
    await expect(panel.getByText("BO config")).toBeVisible({ timeout: 3_000 });
    await expect(panel.getByPlaceholder(/operation to optimise/i)).toBeVisible();
  });

  test("Planner selection shows config form for Optuna", async ({ page }) => {
    await openNewCampaign(page);

    const panel = page.locator(".slide-panel");
    await panel.getByRole("button", { name: "Manual" }).click();

    // Select Optuna planner
    await panel.locator('input[value="optuna"]').click();

    // Should show Optuna config panel
    await expect(panel.getByText("Optuna config")).toBeVisible({ timeout: 3_000 });
    await expect(panel.getByPlaceholder("n_trials")).toBeVisible();
  });
});
