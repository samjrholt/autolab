// @ts-check
import { test, expect } from "@playwright/test";
import { waitForConnection } from "./helpers.js";

test.describe("Natural-language campaign designer", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/");
    await waitForConnection(page);
  });

  test("asks generic clarifying questions for an underspecified request", async ({ page }) => {
    await page.getByRole("button", { name: /\+ New campaign|Start your first campaign/i }).first().click();
    await expect(page.getByRole("heading", { name: "New campaign", exact: true })).toBeVisible();

    await page.getByRole("button", { name: "With Claude", exact: true }).click();

    const designRequest = page.waitForResponse((response) =>
      response.url().includes("/campaigns/design") && response.request().method() === "POST"
    );
    await page
      .getByPlaceholder(/Describe the operation or workflow/i)
      .fill("I want to start a campaign around this problem");
    await page.getByRole("button", { name: "Design", exact: true }).click();
    await designRequest;

    await expect(page.getByText("More information needed", { exact: true })).toBeVisible();
    await expect(page.getByLabel("Which operation or workflow should autolab run?", { exact: true })).toBeVisible();
    await expect(page.getByLabel("Which output or metric should the campaign optimise?", { exact: true })).toBeVisible();
    await expect(page.getByRole("button", { name: "Approve & start", exact: true })).toHaveCount(0);
    await expect(page.getByRole("button", { name: "Continue", exact: true })).toBeDisabled();
  });

  test("only asks for the details still missing in a partial request", async ({ page }) => {
    await page.getByRole("button", { name: /\+ New campaign|Start your first campaign/i }).first().click();
    await expect(page.getByRole("heading", { name: "New campaign", exact: true })).toBeVisible();

    await page.getByRole("button", { name: "With Claude", exact: true }).click();

    const designRequest = page.waitForResponse((response) =>
      response.url().includes("/campaigns/design") && response.request().method() === "POST"
    );
    await page
      .getByPlaceholder(/Describe the operation or workflow/i)
      .fill("Maximise score with demo_quadratic");
    await page.getByRole("button", { name: "Design", exact: true }).click();
    await designRequest;

    await expect(page.getByText("More information needed", { exact: true })).toBeVisible();
    await expect(page.getByLabel("Which inputs, search ranges, or fixed conditions should define the campaign?", { exact: true })).toBeVisible();
    await expect(page.getByLabel("Which operation or workflow should autolab run?", { exact: true })).toHaveCount(0);
    await expect(page.getByLabel("Which output or metric should the campaign optimise?", { exact: true })).toHaveCount(0);
    await expect(page.getByRole("button", { name: "Approve & start", exact: true })).toHaveCount(0);
  });

  test("can refine a vague request into a ready campaign draft", async ({ page }) => {
    await page.getByRole("button", { name: /\+ New campaign|Start your first campaign/i }).first().click();
    await expect(page.getByRole("heading", { name: "New campaign", exact: true })).toBeVisible();

    await page.getByRole("button", { name: "With Claude", exact: true }).click();

    const initialDesign = page.waitForResponse((response) =>
      response.url().includes("/campaigns/design") && response.request().method() === "POST"
    );
    await page
      .getByPlaceholder(/Describe the operation or workflow/i)
      .fill("I want to start a campaign around this problem");
    await page.getByRole("button", { name: "Design", exact: true }).click();
    await initialDesign;

    await expect(page.getByText("More information needed", { exact: true })).toBeVisible();
    await expect(page.getByRole("button", { name: "Continue", exact: true })).toBeDisabled();

    const refineRequest = page.waitForResponse((response) =>
      response.url().includes("/campaigns/design") && response.request().method() === "POST"
    );
    await page.getByLabel("Which operation or workflow should autolab run?", { exact: true }).fill("demo_quadratic");
    await page.getByLabel("Which output or metric should the campaign optimise?", { exact: true }).fill("score");
    await page.getByRole("button", { name: "Continue", exact: true }).click();
    await refineRequest;

    await expect(page.getByLabel("Which inputs, search ranges, or fixed conditions should define the campaign?", { exact: true })).toBeVisible();

    const secondRefineRequest = page.waitForResponse((response) =>
      response.url().includes("/campaigns/design") && response.request().method() === "POST"
    );
    await page.getByLabel("Which inputs, search ranges, or fixed conditions should define the campaign?", { exact: true }).fill("vary x between 0 and 1");
    await page.getByRole("button", { name: "Continue", exact: true }).click();
    await secondRefineRequest;

    await expect(page.getByText("Draft preview (edit inline)", { exact: true })).toBeVisible();
    await expect(page.getByRole("button", { name: "Approve & start", exact: true })).toBeVisible();
    await expect(page.getByText("More information needed", { exact: true })).toHaveCount(0);
  });

  test("can create a campaign from a concrete natural-language prompt", async ({ page }) => {
    await page.getByRole("button", { name: /\+ New campaign|Start your first campaign/i }).first().click();
    await expect(page.getByRole("heading", { name: "New campaign", exact: true })).toBeVisible();

    await page.getByRole("button", { name: "With Claude", exact: true }).click();

    const designRequest = page.waitForResponse((response) =>
      response.url().includes("/campaigns/design") && response.request().method() === "POST"
    );
    await page
      .getByPlaceholder(/Describe the operation or workflow/i)
      .fill("Use demo_quadratic to maximise score by varying x in [0, 1].");
    await page.getByRole("button", { name: "Design", exact: true }).click();
    await designRequest;

    await expect(page.getByText("Draft preview (edit inline)", { exact: true })).toBeVisible();

    const submitRequest = page.waitForResponse((response) =>
      response.url().includes("/campaigns") &&
      !response.url().includes("/campaigns/design") &&
      response.request().method() === "POST"
    );
    await page.getByRole("button", { name: "Approve & start", exact: true }).click();
    await submitRequest;

    await expect(page.getByRole("heading", { name: "Campaigns", exact: true })).toBeVisible();
    await expect(page.getByText("[offline fallback] campaign draft for demo_quadratic", { exact: true })).toBeVisible();
  });
});
