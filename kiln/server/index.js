import express from "express";
import { createServer } from "node:http";
import { existsSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { BATCH_INTERVAL_MS, BATCH_SIZE, MAX_ROSTER, openDb, SPARKS_PER_DAY } from "./db.js";
import { createApp } from "./app.js";
import { startScheduler } from "./scheduler.js";

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

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, "..");
const db = openDb();
const app = createApp(db);

const PORT = Number(process.env.PORT || 3000);
const HOST = process.env.HOST || "0.0.0.0";

async function start() {
  if (process.env.NODE_ENV === "production") {
    const dist = join(ROOT, "dist");
    app.use(express.static(dist));
    app.get("/{*splat}", (_req, res) => {
      res.sendFile(join(dist, "index.html"));
    });
  }

  const server = createServer(app);
  if (process.env.NODE_ENV !== "production") {
    const { createServer: createViteServer } = await import("vite");
    const vite = await createViteServer({
      root: ROOT,
      server: {
        middlewareMode: true,
        host: true,
        allowedHosts: true,
        hmr: { server },
      },
      appType: "spa",
    });
    app.use(vite.middlewares);
  }

  startScheduler(db);
  server.listen(PORT, HOST, () => {
    console.log(`[kiln] listening on http://${HOST}:${PORT}`);
    console.log(
      `[kiln] roster ${MAX_ROSTER} · sparks ${SPARKS_PER_DAY}/day · batch ${BATCH_SIZE} every ${BATCH_INTERVAL_MS / 60000}m · gemini ${process.env.GEMINI_API_KEY ? "on" : "lesser-eye"}`
    );
  });
}

start().catch((err) => {
  console.error(err);
  process.exit(1);
});
