import type { FullConfig } from "@playwright/test";
import { request } from "@playwright/test";

import { HR_SCREENING, PROJECT_NAME, PROJECT_OWNER } from "./fixtures/descriptions";
import { writeSeedState } from "./fixtures/state";

interface HealthResponse {
  status: string;
  schema_version: string;
  mock_model: boolean;
  model: { ok: boolean; provider: string; model: string; latency_ms: number; detail: string | null };
}

async function waitForHealth(url: string, timeoutMs: number): Promise<HealthResponse> {
  const context = await request.newContext();
  const deadline = Date.now() + timeoutMs;
  let lastError = "no response";
  try {
    while (Date.now() < deadline) {
      try {
        const response = await context.get(url, { timeout: 10_000 });
        if (response.ok()) return (await response.json()) as HealthResponse;
        lastError = `${response.status()} ${response.statusText()}`;
      } catch (error) {
        lastError = error instanceof Error ? error.message : String(error);
      }
      await new Promise((resolve) => setTimeout(resolve, 1000));
    }
  } finally {
    await context.dispose();
  }
  throw new Error(`Timed out waiting for ${url}: ${lastError}`);
}

export default async function globalSetup(config: FullConfig): Promise<void> {
  const baseURL = config.projects[0]?.use.baseURL ?? process.env.E2E_BASE_URL ?? "http://localhost:3000";
  const backendURL = process.env.E2E_BACKEND_URL ?? "http://127.0.0.1:8000";
  const live = process.env.E2E_LIVE === "1";

  const backend = await waitForHealth(`${backendURL}/healthz`, 120_000);
  const viaFrontend = await waitForHealth(`${baseURL}/api/backend/healthz`, 180_000);
  // `next dev` compiles routes on first request and then performs a full reload of any page
  // that loaded mid-compile; warm every route before the first test so no test sees that.
  for (const route of ["/", "/intake/new", "/intake/existing"]) {
    await fetch(`${baseURL}${route}`).then((response) => response.arrayBuffer());
  }

  if (live) {
    if (viaFrontend.mock_model) {
      throw new Error("E2E_LIVE=1 but the backend reports mock_model=true. Start it with MOCK_MODEL=0.");
    }
    // The backend already issues a one-token prompt; the health document carries its result.
    const refreshed = await waitForHealth(`${backendURL}/healthz?refresh=true`, 60_000);
    if (refreshed.model.ok !== true) {
      throw new Error(`Live model check failed: ${JSON.stringify(refreshed.model)}`);
    }
  } else if (!backend.mock_model) {
    console.warn("[e2e] MOCK_MODEL is off; the mock suite expects deterministic answers. Set E2E_LIVE=1 for a live run.");
  }

  // A record for the review / visual / accessibility specs. The review page renders any
  // record, interviewed or not, so a plain POST is enough.
  const api = await request.newContext({ baseURL });
  try {
    const response = await api.post("/api/backend/intakes", {
      data: { mode: "new", description: HR_SCREENING, name: PROJECT_NAME, owner: PROJECT_OWNER },
    });
    if (!response.ok()) {
      throw new Error(`Seeding intake failed: ${response.status()} ${await response.text()}`);
    }
    const record = (await response.json()) as { meta: { intake_id: string } };
    const seededIntakeId = record.meta.intake_id;
    process.env.E2E_SEED_INTAKE_ID = seededIntakeId;
    writeSeedState({ seededIntakeId, live, createdAt: new Date().toISOString() });
  } finally {
    await api.dispose();
  }
}
