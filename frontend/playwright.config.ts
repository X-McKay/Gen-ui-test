import path from "node:path";

import { defineConfig, devices } from "@playwright/test";

/**
 * Playwright configuration for the intake app.
 *
 * - `E2E_BASE_URL`         frontend origin (default http://localhost:3000)
 * - `E2E_BACKEND_URL`      backend origin used for health checks (default http://127.0.0.1:8000)
 * - `E2E_EXTERNAL_SERVERS` set when the backend and frontend are already running; no webServer is started
 * - `E2E_LIVE=1`           run against the real model (MOCK_MODEL=0); counts relax to the plan's bounds
 * - `E2E_PRODUCTION=1`     serve the frontend with `next start` instead of `next dev`
 */
const externalServers = Boolean(process.env.E2E_EXTERNAL_SERVERS);
const live = process.env.E2E_LIVE === "1";
const production = process.env.E2E_PRODUCTION === "1";
const baseURL = process.env.E2E_BASE_URL ?? "http://localhost:3000";
const backendURL = process.env.E2E_BACKEND_URL ?? "http://127.0.0.1:8000";
const isCI = Boolean(process.env.CI);

export default defineConfig({
  testDir: "./e2e",
  globalSetup: "./e2e/global-setup.ts",
  fullyParallel: true,
  forbidOnly: isCI,
  retries: process.env.CI ? 2 : 0,
  // The backend agent (ag-ui-adk `ADKAgent`) allows 10 concurrent executions; every
  // worker holds one while a step streams, so the local default stays well under that.
  // Override with E2E_WORKERS.
  workers: process.env.CI ? 2 : Number(process.env.E2E_WORKERS ?? 4),
  reporter: [["html", { open: "never" }], ["list"]],
  timeout: live ? 240_000 : 120_000,
  expect: {
    timeout: live ? 30_000 : 15_000,
    toHaveScreenshot: { maxDiffPixelRatio: 0.01, animations: "disabled", caret: "hide" },
  },
  outputDir: "./test-results",
  use: {
    baseURL,
    trace: "on-first-retry",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
    actionTimeout: live ? 30_000 : 15_000,
  },
  projects: [
    { name: "chromium", use: { ...devices["Desktop Chrome"] } },
    { name: "firefox", use: { ...devices["Desktop Firefox"] } },
    { name: "webkit", use: { ...devices["Desktop Safari"] } },
    { name: "mobile-chrome", use: { ...devices["Pixel 7"] } },
  ],
  webServer: externalServers
    ? undefined
    : [
        {
          command: "uv run uvicorn app.main:app --port 8000",
          cwd: path.resolve(__dirname, "../backend"),
          url: `${backendURL}/healthz`,
          env: {
            MOCK_MODEL: live ? "0" : "1",
            // Every worker reaches the backend from one address; the per-address limit is for people.
            AGENT_RATE_LIMIT: "1000/minute",
            DATABASE_URL: "sqlite:////tmp/intake-e2e.db",
          },
          reuseExistingServer: !isCI,
          timeout: 120_000,
          stdout: "ignore",
          stderr: "pipe",
        },
        {
          command: production ? "pnpm exec next start --port 3000" : "pnpm exec next dev --port 3000",
          cwd: __dirname,
          url: `${baseURL}/api/backend/healthz`,
          // The CopilotKit inspector is a dev-only widget; its announcement popup overlays the page.
          env: { BACKEND_URL: backendURL, NEXT_PUBLIC_ENABLE_INSPECTOR: "0" },
          reuseExistingServer: !isCI,
          timeout: 180_000,
          stdout: "ignore",
          stderr: "pipe",
        },
      ],
});
