// @ts-check
import { test, expect } from "@playwright/test";
import { waitForConnection, openSettings } from "./helpers.js";

test.describe("Workflow builder", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/");
    await waitForConnection(page);
    await openSettings(page);
  });

  test("Workflows section shows '+ New workflow' button", async ({ page }) => {
    await expect(page.getByRole("button", { name: /new workflow/i })).toBeVisible();
  });

  test("Manual mode — open builder and add steps", async ({ page }) => {
    // Click "+ New workflow"
    await page.getByRole("button", { name: /new workflow/i }).click();

    // The workflow builder should appear
    await expect(page.getByText(/workflow builder/i)).toBeVisible({ timeout: 3_000 });

    // Click Manual tab
    const manualTab = page.locator("div", { has: page.getByText("Workflow builder") }).getByRole("button", { name: "Manual" });
    if (await manualTab.isVisible()) {
      await manualTab.click();
    }

    // Fill workflow name
    await page.getByPlaceholder("Workflow name").fill("test-pipeline");

    // Add first step
    await page.getByText("+ Add step").click();
    await expect(page.getByText("s1")).toBeVisible();

    // Select the demo_quadratic operation for step 1
    const stepSelect = page.locator("select", { has: page.locator('option:has-text("demo_quadratic")') }).first();
    await stepSelect.selectOption("demo_quadratic");

    // Add second step
    await page.getByText("+ Add step").click();
    await expect(page.getByText("s2")).toBeVisible();

    // Second step should auto-depend on s1
    // The dependency chip for s1 should be active
    const depChip = page.locator('button:has-text("s1")').last();
    await expect(depChip).toHaveClass(/border-white/);
  });

  test("Manual mode — save a workflow", async ({ page }) => {
    await page.getByRole("button", { name: /new workflow/i }).click();

    const manualTab = page.locator("div", { has: page.getByText("Workflow builder") }).getByRole("button", { name: "Manual" });
    if (await manualTab.isVisible()) {
      await manualTab.click();
    }

    await page.getByPlaceholder("Workflow name").fill("simple-flow");
    await page.getByText("+ Add step").click();

    const stepSelect = page.locator("select", { has: page.locator('option:has-text("demo_quadratic")') }).first();
    await stepSelect.selectOption("demo_quadratic");

    await page.getByRole("button", { name: /save workflow/i }).click();

    // The workflow should appear in the workflows list
    await expect(page.getByText("simple-flow")).toBeVisible({ timeout: 5_000 });
  });

  test("Claude mode — shows the design prompt", async ({ page }) => {
    await page.getByRole("button", { name: /new workflow/i }).click();

    const claudeTab = page.locator("div", { has: page.getByText("Workflow builder") }).getByRole("button", { name: "With Claude" });
    await claudeTab.click();

    await expect(
      page.getByPlaceholder(/describe your workflow/i)
    ).toBeVisible();

    await expect(
      page.getByRole("button", { name: /propose workflow/i })
    ).toBeVisible();
  });
});
