// @ts-check
import { test, expect } from "@playwright/test";
import { waitForConnection, navigateTo } from "./helpers.js";

test.describe("Setup Assistant", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/");
    await waitForConnection(page);
  });

  test("asks for missing setup information before proposing registrations", async ({ page }) => {
    await navigateTo(page, "Assistant");
    await expect(page.getByRole("heading", { name: "Setup Assistant", exact: true })).toBeVisible();

    const setupRequest = page.waitForResponse((response) =>
      response.url().includes("/lab/setup") && response.request().method() === "POST"
    );
    await page.getByPlaceholder(/I have a WSL host/i).fill("I want to set up a lab");
    await page.getByRole("button", { name: "Send" }).click();
    await setupRequest;

    await expect(page.getByText(/I need a few details before registering anything/i)).toBeVisible();
    await expect(page.getByText("What equipment or compute resources should autolab use?", { exact: true })).toBeVisible();
    await expect(page.getByRole("button", { name: "Register setup" })).toHaveCount(0);
  });

  test("proposes and applies resources, capabilities, and workflow from chat", async ({ page }) => {
    await navigateTo(page, "Assistant");

    const setupRequest = page.waitForResponse((response) =>
      response.url().includes("/lab/setup") && response.request().method() === "POST"
    );
    await page
      .getByPlaceholder(/I have a WSL host/i)
      .fill("I have a local computer and a simulation script. Run it with x and collect a score.");
    await page.getByRole("button", { name: "Send" }).click();
    await setupRequest;

    await expect(page.getByText("local-workstation")).toBeVisible();
    await expect(page.getByText("run_simulation")).toBeVisible();
    await expect(page.getByText("simulation-workflow")).toBeVisible();

    const applyRequest = page.waitForResponse((response) =>
      response.url().includes("/lab/setup/apply") && response.request().method() === "POST"
    );
    await page.getByRole("button", { name: "Register setup" }).click();
    await applyRequest;
    await expect(page.getByText("Registered", { exact: true })).toBeVisible();

    await navigateTo(page, "Resources");
    await expect(page.getByText("local-workstation")).toBeVisible();
    await navigateTo(page, "Capabilities");
    await expect(page.getByRole("cell", { name: "run_simulation", exact: true })).toBeVisible();
    await navigateTo(page, "Workflows");
    await expect(page.getByText("simulation-workflow")).toBeVisible();
  });
});
