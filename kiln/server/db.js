import { DatabaseSync } from "node:sqlite";
import { mkdirSync, copyFileSync, existsSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { randomBytes } from "node:crypto";

const __dirname = dirname(fileURLToPath(import.meta.url));
export const ROOT = join(__dirname, "..");
export const REPO_ROOT = join(ROOT, "..");
export const DATA_DIR = join(ROOT, "data");
export const UPLOADS = join(DATA_DIR, "uploads");

export const MAX_ROSTER = Number(process.env.MAX_ROSTER || 256);
export const SPARKS_PER_DAY = Number(process.env.SPARKS_PER_DAY || 10);
export const BATCH_SIZE = Number(process.env.BATCH_SIZE || 10);
export const BATCH_INTERVAL_MS = Number(process.env.BATCH_INTERVAL_MS || 60 * 60 * 1000);
export const BOT_COOLDOWN_DAYS = Number(process.env.BOT_COOLDOWN_DAYS || 1);
export const BOTS_ENABLED = process.env.KILN_BOTS !== "0";

// Portrait filenames starting with this prefix live in the repo (not kiln/data)
// and are served under /bots/<folder>/<file>. See imageUrl() / portraitPath().
export const BOT_FILE_PREFIX = "@bot/";

export function utcDate(d = new Date()) {
  return d.toISOString().slice(0, 10);
}

export function nowIso() {
  return new Date().toISOString();
}

export function id(n = 8) {
  return randomBytes(n).toString("hex");
}

const SCHEMA = `
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
  id TEXT PRIMARY KEY,
  username TEXT UNIQUE NOT NULL,
  pass_hash TEXT NOT NULL,
  pass_salt TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sessions (
  token TEXT PRIMARY KEY,
  user_id TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS generation_ledger (
  user_id TEXT NOT NULL,
  utc_date TEXT NOT NULL,
  count INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (user_id, utc_date)
);

CREATE TABLE IF NOT EXISTS sparks (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL,
  prompt TEXT NOT NULL,
  seed INTEGER NOT NULL,
  filename TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS fighters (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL,
  name TEXT NOT NULL,
  prompt TEXT NOT NULL,
  spark_id TEXT,
  filename TEXT NOT NULL,
  wins INTEGER NOT NULL DEFAULT 0,
  status TEXT NOT NULL,
  created_at TEXT NOT NULL,
  died_at TEXT,
  killed_by TEXT,
  death_match_id TEXT
);

CREATE TABLE IF NOT EXISTS rounds (
  id TEXT PRIMARY KEY,
  number INTEGER NOT NULL,
  started_at TEXT NOT NULL,
  completed_at TEXT,
  status TEXT NOT NULL,
  batch_index INTEGER NOT NULL DEFAULT 0,
  next_batch_at TEXT NOT NULL,
  notes TEXT
);

CREATE TABLE IF NOT EXISTS matches (
  id TEXT PRIMARY KEY,
  round_id TEXT NOT NULL,
  seq INTEGER NOT NULL,
  left_id TEXT NOT NULL,
  right_id TEXT NOT NULL,
  winner_id TEXT,
  margin TEXT,
  narration TEXT,
  left_scout TEXT,
  right_scout TEXT,
  raw_json TEXT,
  status TEXT NOT NULL,
  attempts INTEGER NOT NULL DEFAULT 0,
  judged_at TEXT,
  judge TEXT
);

CREATE TABLE IF NOT EXISTS bot_pool (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  base_wins INTEGER NOT NULL DEFAULT 0,
  filename TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'available',
  deployments INTEGER NOT NULL DEFAULT 0,
  deaths INTEGER NOT NULL DEFAULT 0,
  wins_gained INTEGER NOT NULL DEFAULT 0,
  fighter_id TEXT,
  last_deployed_at TEXT,
  available_at TEXT,
  first_seen TEXT NOT NULL
);
`;

// Additive migrations for databases created before a feature existed.
function migrate(db) {
  const cols = db.prepare("PRAGMA table_info(fighters)").all().map((c) => c.name);
  if (!cols.includes("is_bot")) {
    db.exec("ALTER TABLE fighters ADD COLUMN is_bot INTEGER NOT NULL DEFAULT 0");
  }
}

// The rotating founding-dead: 308 scraped DreadPit portraits catalogued in
// bot_images_manifest.json at the repo root. Bots deploy to fill empty stack
// slots, die like anything else in the pit, and return to the pool to revive.
export function seedBotPool(db) {
  const n = db.prepare("SELECT COUNT(*) AS n FROM bot_pool").get().n;
  if (n > 0) return;
  const manifest = join(REPO_ROOT, "bot_images_manifest.json");
  if (!existsSync(manifest)) {
    console.log("[kiln] bot pool: no bot_images_manifest.json — stack fills from the gate only");
    return;
  }
  let entries;
  try {
    entries = JSON.parse(readFileSync(manifest, "utf8"));
  } catch (err) {
    console.warn("[kiln] bot pool: manifest unreadable —", err.message);
    return;
  }
  const ins = db.prepare(
    `INSERT INTO bot_pool (id, name, base_wins, filename, status, first_seen)
     VALUES (?, ?, ?, ?, 'available', ?)`
  );
  let seeded = 0;
  // node:sqlite (Node 22) has no .transaction() helper — drive one manually.
  db.exec("BEGIN");
  try {
    for (const e of entries) {
      if (!e?.id || !e?.name || !e?.image) continue;
      ins.run(String(e.id), String(e.name).slice(0, 60), Number(e.wins) || 0, BOT_FILE_PREFIX + e.image, nowIso());
      seeded++;
    }
    db.exec("COMMIT");
  } catch (err) {
    db.exec("ROLLBACK");
    console.warn("[kiln] bot pool: seed failed —", err.message);
    return;
  }
  console.log(`[kiln] bot pool seeded: ${seeded} rotating vessels (revive cooldown ${BOT_COOLDOWN_DAYS}d)`);
}

// A fighter portrait is either an upload in kiln/data/uploads or, when the
// filename carries the @bot/ prefix, a repo file served via /bots/.
export function imageUrl(filename) {
  if (filename?.startsWith(BOT_FILE_PREFIX)) return `/bots/${filename.slice(BOT_FILE_PREFIX.length)}`;
  return `/uploads/${filename}`;
}

export function portraitPath(filename) {
  if (filename?.startsWith(BOT_FILE_PREFIX)) return join(REPO_ROOT, filename.slice(BOT_FILE_PREFIX.length));
  return join(UPLOADS, filename);
}

export function botPoolStats(db) {
  const total = db.prepare("SELECT COUNT(*) AS n FROM bot_pool").get().n;
  if (!total) return { enabled: false, total: 0 };
  const by = db.prepare("SELECT status, COUNT(*) AS n FROM bot_pool GROUP BY status").all();
  const s = Object.fromEntries(by.map((r) => [r.status, r.n]));
  return {
    enabled: BOTS_ENABLED,
    total,
    available: s.available || 0,
    deployed: s.deployed || 0,
    resting: s.resting || 0,
  };
}

const SEED = [
  {
    name: "Forge Colossus",
    prompt:
      "Giant walking furnace of black iron. White-hot molten core through chest bars. Anvil hammers. Flat iron mask, orange eye slits. No flesh. Just forge.",
    file: "forge_colossus_portrait_v7.jpg",
  },
  {
    name: "Vatican Gun",
    prompt:
      "Hooded executioner in black leather duster. Six-barrel gatling cannon, holy water drums, gas mask with red lenses, crucifix on the stock.",
    file: "vatican_gun_portrait_v7.jpg",
  },
  {
    name: "The Hook",
    prompt:
      "Gaunt hunter draped in monster pelts. Hooked chain between both hands. Iron hook for a hand. One glowing eye. Trophies, no armor.",
    file: "the_hook_portrait_v3.jpg",
  },
  {
    name: "Wrath Infernal",
    prompt:
      "Demonic winged entity wreathed in black orange flames, fiery wings spread, obsidian skull, burning eyes, claws of molten rock.",
    file: "wrath_infernal_portrait_v7.jpg",
  },
  {
    name: "The Reclaimer",
    prompt:
      "Salvage giant of rusted plate and cable, one furnace eye, dragging a wrecking hook, industrial ruin given a body.",
    file: "the_reclaimer_portrait_v5.jpg",
  },
];

export function openDb() {
  mkdirSync(UPLOADS, { recursive: true });
  const db = new DatabaseSync(join(DATA_DIR, "kiln.sqlite"));
  db.exec(SCHEMA);
  migrate(db);
  seedBotPool(db);

  const sys = db.prepare("SELECT id FROM users WHERE id = ?").get("system");
  if (!sys) {
    db.prepare(
      "INSERT INTO users (id, username, pass_hash, pass_salt, created_at) VALUES (?, ?, ?, ?, ?)"
    ).run("system", "kiln", "x", "x", nowIso());
  }

  const count = db.prepare("SELECT COUNT(*) AS n FROM fighters").get().n;
  if (count === 0) {
    for (const s of SEED) {
      const src = join(REPO_ROOT, "generated_images", s.file);
      if (!existsSync(src)) continue;
      const fid = id();
      const destName = `${fid}.jpg`;
      copyFileSync(src, join(UPLOADS, destName));
      db.prepare(
        `INSERT INTO fighters (id, user_id, name, prompt, filename, wins, status, created_at)
         VALUES (?, 'system', ?, ?, ?, 0, 'living', ?)`
      ).run(fid, s.name, s.prompt, destName, nowIso());
    }
  }

  return db;
}

export function userByToken(db, token) {
  if (!token) return null;
  const row = db
    .prepare(
      `SELECT u.* FROM sessions s JOIN users u ON u.id = s.user_id WHERE s.token = ?`
    )
    .get(token);
  return row || null;
}

export function living(db) {
  return db
    .prepare(
      `SELECT f.*, u.username AS owner
       FROM fighters f JOIN users u ON u.id = f.user_id
       WHERE f.status = 'living'
       ORDER BY f.wins DESC, f.created_at ASC`
    )
    .all();
}

export function gate(db) {
  return db
    .prepare(
      `SELECT f.*, u.username AS owner
       FROM fighters f JOIN users u ON u.id = f.user_id
       WHERE f.status = 'gate'
       ORDER BY f.created_at ASC`
    )
    .all();
}

export function dead(db) {
  return db
    .prepare(
      `SELECT f.*, u.username AS owner, k.name AS killer_name
       FROM fighters f
       JOIN users u ON u.id = f.user_id
       LEFT JOIN fighters k ON k.id = f.killed_by
       WHERE f.status = 'dead'
       ORDER BY f.died_at DESC`
    )
    .all();
}

export function sparksToday(db, userId) {
  const row = db
    .prepare("SELECT count FROM generation_ledger WHERE user_id = ? AND utc_date = ?")
    .get(userId, utcDate());
  return row ? row.count : 0;
}

export function bumpSparks(db, userId) {
  const d = utcDate();
  const row = db
    .prepare("SELECT count FROM generation_ledger WHERE user_id = ? AND utc_date = ?")
    .get(userId, d);
  if (!row) {
    db.prepare(
      "INSERT INTO generation_ledger (user_id, utc_date, count) VALUES (?, ?, 1)"
    ).run(userId, d);
    return 1;
  }
  db.prepare(
    "UPDATE generation_ledger SET count = count + 1 WHERE user_id = ? AND utc_date = ?"
  ).run(userId, d);
  return row.count + 1;
}

export function admittedToday(db) {
  const start = `${utcDate()}T00:00:00.000Z`;
  const row = db
    .prepare(
      `SELECT COUNT(*) AS n FROM fighters
       WHERE user_id != 'system' AND created_at >= ? AND status IN ('living','gate')`
    )
    .get(start);
  return row.n;
}

export function currentRound(db) {
  return (
    db.prepare(`SELECT * FROM rounds ORDER BY number DESC LIMIT 1`).get() || null
  );
}

export function roundMatches(db, roundId) {
  return db
    .prepare(
      `SELECT m.*,
              l.name AS left_name, l.filename AS left_file, l.wins AS left_wins,
              r.name AS right_name, r.filename AS right_file, r.wins AS right_wins
       FROM matches m
       JOIN fighters l ON l.id = m.left_id
       JOIN fighters r ON r.id = m.right_id
       WHERE m.round_id = ?
       ORDER BY m.seq ASC`
    )
    .all(roundId);
}

export function publicFighter(row) {
  if (!row) return null;
  return {
    id: row.id,
    name: row.name,
    prompt: row.status === "dead" ? null : row.prompt,
    sealed: row.status === "dead",
    filename: row.filename,
    image: imageUrl(row.filename),
    wins: row.wins,
    status: row.status,
    isBot: Boolean(row.is_bot),
    owner: row.owner || null,
    createdAt: row.created_at,
    diedAt: row.died_at || null,
    killerId: row.killed_by || null,
    killerName: row.killer_name || null,
  };
}
