import express from "express";
import { createServer } from "node:http";
import { existsSync, readFileSync } from "node:fs";
import { basename, dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import {
  admittedToday,
  botPoolStats,
  bumpSparks,
  currentRound,
  dead,
  gate,
  imageUrl,
  living,
  MAX_ROSTER,
  nowIso,
  openDb,
  publicFighter,
  REPO_ROOT,
  roundMatches,
  SPARKS_PER_DAY,
  sparksToday,
  UPLOADS,
  userByToken,
  BATCH_SIZE,
  BATCH_INTERVAL_MS,
} from "./db.js";
import {
  clearSessionCookie,
  createSession,
  isSecure,
  login,
  parseCookies,
  register,
  setSessionCookie,
} from "./auth.js";
import { generateSpark } from "./pollinations.js";
import { startScheduler, tick } from "./scheduler.js";

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
const app = express();
app.set("trust proxy", 1);
app.disable("x-powered-by");
app.use(express.json({ limit: "1mb" }));

function me(req) {
  const token = parseCookies(req).kiln_session;
  return userByToken(db, token);
}

function requireUser(req, res, next) {
  const user = me(req);
  if (!user || user.id === "system") {
    return res.status(401).json({ error: "Log in first." });
  }
  req.user = user;
  next();
}

function sendErr(res, err) {
  const status = err.status || 500;
  if (status >= 500) console.error(err);
  res.status(status).json({ error: err.message || "internal" });
}

app.get("/api/health", (_req, res) => {
  res.json({ ok: true, name: "kiln" });
});

app.get("/api/auth/me", (req, res) => {
  const user = me(req);
  if (!user || user.id === "system") return res.json({ user: null });
  res.json({
    user: { id: user.id, username: user.username },
    sparksUsed: sparksToday(db, user.id),
    sparksMax: SPARKS_PER_DAY,
  });
});

app.post("/api/auth/register", (req, res) => {
  try {
    const user = register(db, req.body?.username, req.body?.password);
    const token = createSession(db, user.id);
    setSessionCookie(res, token, isSecure(req));
    res.json({ user });
  } catch (err) {
    sendErr(res, err);
  }
});

app.post("/api/auth/login", (req, res) => {
  try {
    const user = login(db, req.body?.username, req.body?.password);
    const token = createSession(db, user.id);
    setSessionCookie(res, token, isSecure(req));
    res.json({ user });
  } catch (err) {
    sendErr(res, err);
  }
});

app.post("/api/auth/logout", (req, res) => {
  const token = parseCookies(req).kiln_session;
  if (token) db.prepare("DELETE FROM sessions WHERE token = ?").run(token);
  clearSessionCookie(res, isSecure(req));
  res.json({ ok: true });
});

app.get("/api/quota", requireUser, (req, res) => {
  const livingN = db.prepare("SELECT COUNT(*) AS n FROM fighters WHERE status = 'living'").get().n;
  res.json({
    sparksUsed: sparksToday(db, req.user.id),
    sparksMax: SPARKS_PER_DAY,
    admittedToday: admittedToday(db),
    admitMax: MAX_ROSTER,
    living: livingN,
    livingMax: MAX_ROSTER,
    gate: gate(db).length,
  });
});

app.post("/api/forge/spark", requireUser, async (req, res) => {
  try {
    const prompt = String(req.body?.prompt || "").trim().slice(0, 200);
    if (prompt.length < 8) {
      return res.status(400).json({ error: "Describe the fighter in at least 8 characters." });
    }
    const used = sparksToday(db, req.user.id);
    if (used >= SPARKS_PER_DAY) {
      return res.status(429).json({ error: "Ten portraits a day. Try again tomorrow." });
    }
    const seed =
      Number.isFinite(Number(req.body?.seed)) && Number(req.body.seed) >= 0
        ? Number(req.body.seed)
        : Math.floor(Math.random() * 99999);
    const apiKey = String(req.headers["x-pollinations-key"] || "").trim() || null;
    const spark = await generateSpark(prompt, seed, apiKey);
    bumpSparks(db, req.user.id);
    db.prepare(
      `INSERT INTO sparks (id, user_id, prompt, seed, filename, created_at) VALUES (?, ?, ?, ?, ?, ?)`
    ).run(spark.id, req.user.id, prompt, spark.seed, spark.filename, nowIso());
    res.json({
      id: spark.id,
      seed: spark.seed,
      image: `/uploads/${spark.filename}`,
      sparksUsed: sparksToday(db, req.user.id),
      sparksMax: SPARKS_PER_DAY,
    });
  } catch (err) {
    sendErr(res, err);
  }
});

app.post("/api/fighters", requireUser, (req, res) => {
  try {
    const name = String(req.body?.name || "").trim().slice(0, 40);
    const sparkId = String(req.body?.sparkId || "").trim();
    if (name.length < 2) return res.status(400).json({ error: "Name the fighter." });
    // Reserved: the judge's internal labels. A vessel named "Fighter 1" would
    // read like an unsubstituted placeholder in narrations.
    if (/^fighter[\s_-]?\d*$/i.test(name)) {
      return res.status(400).json({ error: "That name is reserved. Choose another." });
    }
    const spark = db
      .prepare("SELECT * FROM sparks WHERE id = ? AND user_id = ?")
      .get(sparkId, req.user.id);
    if (!spark) return res.status(400).json({ error: "Pick a portrait you generated today." });

    const taken = db.prepare("SELECT id FROM fighters WHERE spark_id = ?").get(spark.id);
    if (taken) return res.status(409).json({ error: "That portrait is already a fighter." });

    if (admittedToday(db) >= MAX_ROSTER) {
      return res.status(409).json({
        error: "256 new fighters a day. The roster is closed until tomorrow.",
      });
    }

    const livingN = db
      .prepare("SELECT COUNT(*) AS n FROM fighters WHERE status = 'living'")
      .get().n;
    const status = livingN >= MAX_ROSTER ? "gate" : "living";
    const fid = spark.id.slice(0, 12) + "f";
    db.prepare(
      `INSERT INTO fighters (id, user_id, name, prompt, spark_id, filename, wins, status, created_at)
       VALUES (?, ?, ?, ?, ?, ?, 0, ?, ?)`
    ).run(fid, req.user.id, name, spark.prompt, spark.id, spark.filename, status, nowIso());
    const row = db
      .prepare(
        `SELECT f.*, u.username AS owner FROM fighters f JOIN users u ON u.id = f.user_id WHERE f.id = ?`
      )
      .get(fid);
    res.json({ fighter: publicFighter(row), queued: status === "gate" });
  } catch (err) {
    sendErr(res, err);
  }
});

app.get("/api/state", (req, res) => {
  const round = currentRound(db);
  const matches = round ? roundMatches(db, round.id) : [];
  const user = me(req);
  const livingRows = living(db);
  res.json({
    maxRoster: MAX_ROSTER,
    sparksMax: SPARKS_PER_DAY,
    batchSize: BATCH_SIZE,
    batchIntervalMs: BATCH_INTERVAL_MS,
    gemini: Boolean(process.env.GEMINI_API_KEY),
    living: livingRows.map(publicFighter),
    gate: gate(db).map(publicFighter),
    deadCount: db.prepare("SELECT COUNT(*) AS n FROM fighters WHERE status = 'dead'").get().n,
    admittedToday: admittedToday(db),
    me:
      user && user.id !== "system"
        ? {
            id: user.id,
            username: user.username,
            sparksUsed: sparksToday(db, user.id),
          }
        : null,
    round: round
      ? {
          id: round.id,
          number: round.number,
          status: round.status,
          startedAt: round.started_at,
          completedAt: round.completed_at,
          batchIndex: round.batch_index,
          nextBatchAt: round.next_batch_at,
          notes: round.notes,
          matchesTotal: matches.length,
          matchesDone: matches.filter((m) => m.status === "done").length,
        }
      : null,
    matches: matches.map(publicMatch),
    bots: botPoolStats(db),
  });
});

function publicMatch(m) {
  const batch = Math.ceil(m.seq / BATCH_SIZE);
  return {
    id: m.id,
    seq: m.seq,
    batch,
    status: m.status,
    margin: m.margin,
    narration: m.narration,
    judgedAt: m.judged_at,
    judge: m.judge,
    winnerId: m.winner_id,
    left: {
      id: m.left_id,
      name: m.left_name,
      image: imageUrl(m.left_file),
      wins: m.left_wins,
    },
    right: {
      id: m.right_id,
      name: m.right_name,
      image: imageUrl(m.right_file),
      wins: m.right_wins,
    },
  };
}

app.get("/api/stack", (_req, res) => {
  res.json({ living: living(db).map(publicFighter), gate: gate(db).map(publicFighter) });
});

app.get("/api/ash", (_req, res) => {
  res.json({ dead: dead(db).map(publicFighter) });
});

app.get("/api/fighters/:id", (req, res) => {
  const row = db
    .prepare(
      `SELECT f.*, u.username AS owner, k.name AS killer_name
       FROM fighters f
       JOIN users u ON u.id = f.user_id
       LEFT JOIN fighters k ON k.id = f.killed_by
       WHERE f.id = ?`
    )
    .get(req.params.id);
  if (!row) return res.status(404).json({ error: "No such fighter." });
  const fights = db
    .prepare(
      `SELECT m.*, rd.number AS round_number,
              lf.name AS left_name, lf.filename AS left_file,
              rf.name AS right_name, rf.filename AS right_file
       FROM matches m
       JOIN rounds rd ON rd.id = m.round_id
       JOIN fighters lf ON lf.id = m.left_id
       JOIN fighters rf ON rf.id = m.right_id
       WHERE m.left_id = ? OR m.right_id = ?
       ORDER BY m.judged_at DESC, rd.number DESC, m.seq DESC`
    )
    .all(row.id, row.id);
  res.json({
    fighter: publicFighter(row),
    fights: fights.map((m) => {
      const opponentIsRight = m.left_id === row.id;
      return {
        id: m.id,
        round: m.round_number,
        status: m.status,
        winnerId: m.winner_id,
        foughtAt: m.judged_at,
        opponent: opponentIsRight
          ? { id: m.right_id, name: m.right_name, image: imageUrl(m.right_file) }
          : { id: m.left_id, name: m.left_name, image: imageUrl(m.left_file) },
      };
    }),
  });
});

app.get("/api/matches/:id", (req, res) => {
  const m = db
    .prepare(
      `SELECT m.*,
              l.name AS left_name, l.filename AS left_file, l.wins AS left_wins,
              r.name AS right_name, r.filename AS right_file, r.wins AS right_wins
       FROM matches m
       JOIN fighters l ON l.id = m.left_id
       JOIN fighters r ON r.id = m.right_id
       WHERE m.id = ?`
    )
    .get(req.params.id);
  if (!m) return res.status(404).json({ error: "No such fight." });
  const extra = {
    leftScout: m.left_scout ? JSON.parse(m.left_scout) : null,
    rightScout: m.right_scout ? JSON.parse(m.right_scout) : null,
  };
  res.json({ match: { ...publicMatch(m), ...extra } });
});

app.post("/api/round/tick", requireUser, async (_req, res) => {
  try {
    await tick(db);
    const round = currentRound(db);
    res.json({ ok: true, round: round ? { id: round.id, status: round.status } : null });
  } catch (err) {
    sendErr(res, err);
  }
});

app.use("/uploads", express.static(UPLOADS, { maxAge: "7d", fallthrough: false }));

// Founding-dead portraits live in the repo (catalogued by bot_images_manifest.json),
// not in kiln/data/uploads. Only these three folders are ever served.
const BOT_FOLDERS = new Set(["big_portraits", "bot_losers", "portraits"]);
app.get("/bots/:folder/:file", (req, res) => {
  const { folder, file } = req.params;
  if (!BOT_FOLDERS.has(folder)) return res.status(404).end();
  const safe = basename(file);
  res.sendFile(join(REPO_ROOT, folder, safe), { maxAge: "7d" }, (err) => {
    if (err && !res.headersSent) res.status(404).end();
  });
});

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
