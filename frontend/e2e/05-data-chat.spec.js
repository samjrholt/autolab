// @ts-check
import { test, expect } from "@playwright/test";
import { waitForConnection } from "./helpers.js";

const API_BASE = "http://127.0.0.1:8010";

async function seedCampaign(request) {
  const create = await request.post(`${API_BASE}/campaigns`, {
    data: {
      name: "playwright-ledger-fixture",
      objective: { key: "score", direction: "maximise" },
      budget: 3,
      planner: "optuna",
      planner_config: {
        operation: "demo_quadratic",
        search_space: {
          x: { type: "float", low: 0.0, high: 1.0 },
        },
      },
    },
  });
  expect(create.ok()).toBeTruthy();
  const body = await create.json();
  const campaignId = body.campaign_id;
  expect(campaignId).toBeTruthy();

  const deadline = Date.now() + 15_000;
  while (Date.now() < deadline) {
    const status = await request.get(`${API_BASE}/campaigns/${campaignId}`);
    expect(status.ok()).toBeTruthy();
    const payload = await status.json();
    if (["completed", "failed", "cancelled"].includes(payload.status)) {
      return campaignId;
    }
    await new Promise((resolve) => setTimeout(resolve, 300));
  }

  throw new Error(`campaign ${campaignId} did not finish in time`);
}

test.describe("Data Chat — live ledger query flow", () => {
  test("navigates to Data Chat, posts /analysis/query, and renders a visualization", async ({ page, request }) => {
    await seedCampaign(request);

    await page.goto("/");
    await waitForConnection(page);

    await page.locator("aside").first().getByRole("button", { name: "Data Chat", exact: true }).click();

    await expect(page.getByRole("heading", { name: "Data Chat", exact: true })).toBeVisible();
    await expect(page.getByLabel("Ask for a ledger visualization")).toBeVisible();

    const analysisResponsePromise = page.waitForResponse(
      (response) =>
        response.url().includes("/analysis/query") && response.request().method() === "POST",
    );

    await page.getByLabel("Ask for a ledger visualization").fill("Show best-so-far convergence for each campaign");
    await page.getByRole("button", { name: "Ask", exact: true }).click();

    const analysisResponse = await analysisResponsePromise;
    expect(analysisResponse.status()).toBe(200);

    const payload = await analysisResponse.json();
    expect(payload.chart).toBeTruthy();
    expect(payload.chart.title).toBeTruthy();

    await expect(page.getByText(payload.chart.title, { exact: true })).toBeVisible();
    await expect(page.getByText("Generated visualization", { exact: true })).toBeVisible();
  });
});
