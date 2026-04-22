// @ts-check
import { test, expect } from "@playwright/test";
import { waitForConnection, openSettings } from "./helpers.js";

test.describe("Tool registration", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/");
    await waitForConnection(page);
    await openSettings(page);
  });

  test("Tools section shows bootstrapped tool", async ({ page }) => {
    // demo_quadratic bootstrap registers a tool called "demo_quadratic"
    await expect(page.getByText("demo_quadratic")).toBeVisible();
  });

  test("Manual mode — register a tool with inputs and outputs", async ({ page }) => {
    const toolsSection = page.locator("section", { has: page.getByText("Tools", { exact: true }) });

    // Should be on Manual tab by default
    const manualTab = toolsSection.getByRole("button", { name: "Manual" });
    if (await manualTab.isVisible()) {
      await manualTab.click();
    }

    // Fill capability name
    await toolsSection.getByPlaceholder(/capability name/i).fill("sintering");

    // Fill description
    await toolsSection.getByPlaceholder("Description").fill("Sinter a pellet at target temperature");

    // Add an input field
    const inputsAdd = toolsSection.locator("div", { has: page.getByText("Inputs") }).getByText("+ Add");
    await inputsAdd.click();
    await toolsSection.locator("div", { has: page.getByText("Inputs") }).getByPlaceholder("name").fill("temperature_k");

    // Add an output field
    const outputsAdd = toolsSection.locator("div", { has: page.getByText("Outputs") }).getByText("+ Add");
    await outputsAdd.click();
    await toolsSection.locator("div", { has: page.getByText("Outputs") }).getByPlaceholder("name").fill("density");

    // Click register
    await toolsSection.getByRole("button", { name: /register tool/i }).click();

    // Wait for tool to appear in the list
    await expect(page.getByText("sintering")).toBeVisible({ timeout: 5_000 });
  });

  test("Claude mode — shows the design prompt", async ({ page }) => {
    const toolsSection = page.locator("section", { has: page.getByText("Tools", { exact: true }) });

    // Switch to Claude mode
    await toolsSection.getByRole("button", { name: "With Claude" }).click();

    // Should show a prompt textarea
    await expect(
      toolsSection.getByPlaceholder(/describe a tool/i)
    ).toBeVisible();

    await expect(
      toolsSection.getByRole("button", { name: /propose tool/i })
    ).toBeVisible();
  });
});
