import fs from "node:fs";
import path from "node:path";

/** What global setup leaves behind for the specs. */
export interface SeedState {
  /** An HR-screening intake created through the REST API (not interviewed). */
  seededIntakeId: string;
  live: boolean;
  createdAt: string;
}

export const STATE_DIRECTORY = path.resolve(__dirname, "../.state");
export const STATE_FILE = path.join(STATE_DIRECTORY, "seed.json");

export function writeSeedState(state: SeedState): void {
  fs.mkdirSync(STATE_DIRECTORY, { recursive: true });
  fs.writeFileSync(STATE_FILE, `${JSON.stringify(state, null, 2)}\n`, "utf8");
}

export function readSeedState(): SeedState {
  const fromEnv = process.env.E2E_SEED_INTAKE_ID;
  if (fs.existsSync(STATE_FILE)) {
    const parsed = JSON.parse(fs.readFileSync(STATE_FILE, "utf8")) as SeedState;
    return fromEnv ? { ...parsed, seededIntakeId: fromEnv } : parsed;
  }
  if (fromEnv) {
    return { seededIntakeId: fromEnv, live: process.env.E2E_LIVE === "1", createdAt: "" };
  }
  throw new Error(`No seed state at ${STATE_FILE}; did global setup run?`);
}
