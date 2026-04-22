// @ts-check
import { defineConfig, devices } from "@playwright/test";

/**
 * Playwright configuration for autolab Console E2E tests.
 *
 * Architecture:
 *   1. `webServer[0]` boots the FastAPI backend on :8000 (demo_quadratic bootstrap).
 *   2. `webServer[1]` boots the Vite dev server on :5173, which proxies API
 *      calls to the backend via vite.config.js.
 *   3. Tests navigate to http://localhost:5173 and exercise real user flows.
 *
 * Run: `npm run test:e2e`           (headless)
 *       `npm run test:e2e:ui`       (Playwright UI mode)
 *       `npm run test:e2e:headed`   (visible browser)
 */
export default defineConfig({
  testDir: "./e2e",
  testIgnore: ["**/legacy/**"],
  globalSetup: "./e2e/global-setup.js",
  fullyParallel: false, // tests share one server — run serially for now
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: 1,
  reporter: process.env.CI ? "github" : "list",

  use: {
    baseURL: "http://localhost:5173",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
  },

  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],

  webServer: [
    {
      // 1. Start the FastAPI backend with a demo bootstrap
      command:
        process.platform === "win32"
          ? "pixi run python -m uvicorn autolab.server.app:app --host 127.0.0.1 --port 8000"
          : "pixi run python -m uvicorn autolab.server.app:app --host 127.0.0.1 --port 8000",
      port: 8000,
      cwd: "..",
      env: {
        AUTOLAB_ROOT: "./.autolab-runs/e2e-test",
        AUTOLAB_BOOTSTRAP: "demo_quadratic",
      },
      reuseExistingServer: !process.env.CI,
      timeout: 30_000,
    },
    {
      // 2. Start the Vite dev server (proxies API to backend)
      command: "npm run dev",
      port: 5173,
      reuseExistingServer: !process.env.CI,
      timeout: 15_000,
    },
  ],
});
