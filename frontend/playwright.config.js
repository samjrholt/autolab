// @ts-check
import { defineConfig, devices } from "@playwright/test";

const e2eRoot = `./.autolab-runs/e2e-test-${process.pid}-${Date.now()}`;
process.env.AUTOLAB_E2E_ROOT = e2eRoot;

/**
 * Playwright configuration for autolab Console E2E tests.
 *
 * Architecture:
 *   1. `webServer[0]` boots the FastAPI backend on :8010 (demo_quadratic bootstrap).
 *   2. `webServer[1]` boots the Vite dev server on :5174, which proxies API
 *      calls to the backend via vite.config.js.
 *   3. Tests navigate to http://localhost:5174 and exercise real user flows.
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
    baseURL: "http://localhost:5174",
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
          ? "pixi run python -m uvicorn autolab.server.app:app --host 127.0.0.1 --port 8010"
          : "pixi run python -m uvicorn autolab.server.app:app --host 127.0.0.1 --port 8010",
      port: 8010,
      cwd: "..",
      env: {
        AUTOLAB_ROOT: e2eRoot,
        AUTOLAB_BOOTSTRAP: "demo_quadratic",
        AUTOLAB_CLAUDE_OFFLINE: "1",
      },
      reuseExistingServer: false,
      timeout: 30_000,
    },
    {
      // 2. Start the Vite dev server (proxies API to backend)
      command: "npm run dev",
      port: 5174,
      env: {
        VITE_PORT: "5174",
        AUTOLAB_API_TARGET: "http://localhost:8010",
      },
      reuseExistingServer: false,
      timeout: 15_000,
    },
  ],
});
