// @ts-check
import { test, expect } from "@playwright/test";
import { waitForConnection, navigateTo } from "./helpers.js";

test.describe("Workflow canvas — visual authoring", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/");
    await waitForConnection(page);
  });

  test("+ New workflow lands on the designer with Describe/Build toggle", async ({ page }) => {
    await navigateTo(page, "Workflows");
    await page.getByRole("button", { name: /New workflow/i }).first().click();

    // Designer title and toggle buttons are both present.
    await expect(page.getByRole("heading", { name: "New workflow", exact: true })).toBeVisible();
    await expect(page.getByRole("button", { name: "Describe", exact: true })).toBeVisible();
    await expect(page.getByRole("button", { name: "Build", exact: true })).toBeVisible();
  });

  test("Build mode shows canvas palette + hint", async ({ page }) => {
    await navigateTo(page, "Workflows");
    await page.getByRole("button", { name: /New workflow/i }).first().click();
    await page.getByRole("button", { name: "Build", exact: true }).click();

    // Canvas controls render (react-flow pane + "Save workflow" CTA).
    await expect(page.getByRole("button", { name: /Save workflow/i })).toBeVisible();
    // Empty-canvas hint guides the scientist.
    await expect(page.getByText(/Drag a capability from the palette/i)).toBeVisible();
    // Palette header (inside main, not the sidebar button).
    await expect(page.getByRole("main").getByText("Capabilities", { exact: true })).toBeVisible();
    // "+ New capability" button is in the palette footer for missing caps.
    await expect(page.getByRole("button", { name: /New capability/i })).toBeVisible();
  });

  test("Describe toggle renders the text prompt", async ({ page }) => {
    await navigateTo(page, "Workflows");
    await page.getByRole("button", { name: /New workflow/i }).first().click();
    await page.getByRole("button", { name: "Describe", exact: true }).click();
    await expect(page.getByText(/Describe what you want/i)).toBeVisible();
    await expect(page.locator("textarea").first()).toBeVisible();
  });
});
