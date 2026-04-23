// @ts-check
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

/**
 * Best-effort cleanup for old E2E ledger directories.
 *
 * The active run gets a unique AUTOLAB_ROOT from playwright.config.js, so a
 * locked stale SQLite file should not fail the suite or touch a developer's
 * normal .autolab-runs/default lab.
 */
export default async function globalSetup() {
  const runsDir = path.resolve(__dirname, "..", "..", ".autolab-runs");
  if (!fs.existsSync(runsDir)) return;
  const activeRoot = process.env.AUTOLAB_E2E_ROOT
    ? path.resolve(__dirname, "..", "..", process.env.AUTOLAB_E2E_ROOT)
    : null;

  for (const entry of fs.readdirSync(runsDir, { withFileTypes: true })) {
    if (!entry.isDirectory() || !entry.name.startsWith("e2e-test")) continue;
    const target = path.join(runsDir, entry.name);
    if (activeRoot && path.resolve(target) === activeRoot) continue;
    try {
      fs.rmSync(target, { recursive: true, force: true });
    } catch (error) {
      console.warn(`Skipping locked E2E run directory ${target}: ${error}`);
    }
  }
}
