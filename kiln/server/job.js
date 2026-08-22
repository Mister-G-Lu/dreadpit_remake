// One-shot round driver for cron / systemd timers / managed schedulers.
//
// DreadPit-style scheduling: the trigger is a real job that runs "at least
// once" near the fire mark. The round itself is idempotent — the rounds /
// matches state machine in scheduler.js guarantees at most one round per UTC
// day, keeps a stalled round resuming, and never re-judges a closed match.
//
// Run manually once:
//   cd kiln && node server/job.js
//
// (npm run round is the same thing.)
//
// In a full app deployment set KILN_POLL=0 so the in-process 15s poller is
// disabled and this one-shot job is the only trigger — see kiln/README.md.
import { existsSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { openDb } from "./db.js";
import { tick } from "./scheduler.js";

function loadEnv() {
  const envPath = join(dirname(fileURLToPath(import.meta.url)), "..", ".env");
  if (!existsSync(envPath)) return;
  for (const line of readFileSync(envPath, "utf8").split("\n")) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#")) continue;
    const i = trimmed.indexOf("=");
    if (i < 0) continue;
    const k = trimmed.slice(0, i).trim();
    const v = trimmed.slice(i + 1).trim();
    if (k && process.env[k] === undefined) process.env[k] = v;
  }
}

loadEnv();

const db = openDb();

try {
  const round = await tick(db);
  const row = db
    .prepare("SELECT number, status FROM rounds ORDER BY number DESC LIMIT 1")
    .get();
  console.log(
    `[kiln] job done${row ? ` — round ${row.number} (${row.status})` : ""}`
  );
} catch (err) {
  console.error("[kiln] job failed", err);
  process.exitCode = 1;
} finally {
  db.close();
}
