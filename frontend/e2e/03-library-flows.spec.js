// @ts-check
import { test, expect } from "@playwright/test";
import { waitForConnection, navigateTo } from "./helpers.js";

test.describe("Library flows — rows navigate, CTAs open designer", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/");
    await waitForConnection(page);
  });

  test("clicking + New workflow routes to the workflow designer (not Settings)", async ({ page }) => {
    await navigateTo(page, "Workflows");
    await page.getByRole("button", { name: /New workflow/i }).first().click();
    // DesignerPage renders the title "New workflow" and a Claude drafting textarea
    await expect(page.getByRole("heading", { name: "New workflow", exact: true })).toBeVisible();
    await expect(page.locator("textarea")).toBeVisible();
  });

  test("clicking + Register resource routes to the resource designer", async ({ page }) => {
    await navigateTo(page, "Resources");
    await page.getByRole("button", { name: /Register resource/i }).first().click();
    await expect(page.getByRole("heading", { name: "Register resource", exact: true })).toBeVisible();
  });

  test("clicking + Add capability routes to the capability designer", async ({ page }) => {
    await navigateTo(page, "Capabilities");
    await page.getByRole("button", { name: /Add capability/i }).first().click();
    await expect(page.getByRole("heading", { name: "Add capability", exact: true })).toBeVisible();
  });

  test("clicking a resource row opens its detail page", async ({ page }) => {
    await navigateTo(page, "Resources");
    const firstRow = page.locator("tbody tr").first();
    const hasRow = await firstRow.isVisible().catch(() => false);
    if (!hasRow) {
      test.skip(true, "no resources registered in this test environment");
      return;
    }
    const name = await firstRow.locator("td").first().innerText();
    await firstRow.click();
    await expect(page.getByRole("heading", { name, exact: true })).toBeVisible();
    // "Runtime" panel on the detail page
    await expect(page.getByText("Runtime", { exact: true })).toBeVisible();
  });
});
