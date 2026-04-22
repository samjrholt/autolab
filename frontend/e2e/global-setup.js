// @ts-check
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

/**
 * Clean the E2E test ledger directory before each full run so tests
 * start from a known state (demo_quadratic bootstrap only).
 */
export default async function globalSetup() {
  const ledgerDir = path.resolve(__dirname, "..", "..", ".autolab-runs", "e2e-test");
  if (fs.existsSync(ledgerDir)) {
    fs.rmSync(ledgerDir, { recursive: true, force: true });
  }
}
