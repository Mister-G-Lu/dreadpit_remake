import {
  BATCH_INTERVAL_MS,
  BATCH_SIZE,
  BOTS_ENABLED,
  BOT_COOLDOWN_DAYS,
  isSealing,
  lastFireAt,
  MAX_ROSTER,
  currentRound,
  gate,
  id,
  living,
  nowIso,
} from "./db.js";
import { judgeMatch } from "./gemini.js";

let ticking = false;

export function pairFighters(fighters, roundNumber) {
  const list = fighters.slice(0, MAX_ROSTER);
  const bye = [];
  const pool = list.slice();
  if (roundNumber % 2 === 1 && pool.length >= 3) {
    bye.push(pool.shift());
  }
  if (pool.length % 2 === 1) bye.push(pool.pop());
  const pairs = [];
  for (let i = 0; i < pool.length; i += 2) {
    pairs.push([pool[i], pool[i + 1]]);
  }
  return { pairs, bye };
}

export function startRound(db) {
  const roster = living(db);
  if (roster.length < 2) return null;
  const last = currentRound(db);
  if (last?.status === "running" || last?.status === "stalled") return last;
  // Fire timing itself lives in tick(): a round opens at (or after) the daily
  // FIRE_UTC_HOUR once the previous round has closed.

  const number = (last?.number || 0) + 1;
  const { pairs, bye } = pairFighters(roster, number);
  if (!pairs.length) return null;

  const roundId = id();
  const started = nowIso();
  db.prepare(
    `INSERT INTO rounds (id, number, started_at, status, batch_index, next_batch_at, notes)
     VALUES (?, ?, ?, 'running', 0, ?, ?)`
  ).run(
    roundId,
    number,
    started,
    started,
    bye.length ? `bye:${bye.map((b) => b.name).join(",")}` : null
  );

  pairs.forEach((pair, i) => {
    db.prepare(
      `INSERT INTO matches (id, round_id, seq, left_id, right_id, status, attempts)
       VALUES (?, ?, ?, ?, ?, 'pending', 0)`
    ).run(id(), roundId, i + 1, pair[0].id, pair[1].id);
  });

  console.log(
    `[kiln] round ${number} opened — ${pairs.length} matches, first ${BATCH_SIZE} fire now`
  );
  return db.prepare("SELECT * FROM rounds WHERE id = ?").get(roundId);
}

function fillFromGate(db) {
  const livingCount = db
    .prepare("SELECT COUNT(*) AS n FROM fighters WHERE status = 'living'")
    .get().n;
  const slots = MAX_ROSTER - livingCount;
  if (slots <= 0) return;
  const waiting = gate(db).slice(0, slots);
  for (const f of waiting) {
    db.prepare("UPDATE fighters SET status = 'living' WHERE id = ?").run(f.id);
  }
  if (waiting.length) {
    console.log(`[kiln] ${waiting.length} vessel(s) stepped from the mouth onto the stack`);
  }
  if (BOTS_ENABLED) fillFromBotPool(db);
}

// The founding dead rotate: when the gate cannot fill the stack, the pool
// deploys its longest-resting vessels. A revived bot returns as a fresh
// fighter carrying its legend (base_wins). If even resting bots run short,
// the pit takes the oldest rest anyway — the stack never starves.
function fillFromBotPool(db) {
  let slots = MAX_ROSTER - db
    .prepare("SELECT COUNT(*) AS n FROM fighters WHERE status = 'living'")
    .get().n;
  if (slots <= 0) return;

  const now = Date.now();
  const ready = () =>
    db
      .prepare(
        `SELECT * FROM bot_pool
         WHERE status = 'available' AND (available_at IS NULL OR available_at <= ?)
         ORDER BY last_deployed_at ASC, first_seen ASC
         LIMIT ?`
      )
      .all(nowIso(), slots);

  let picks = ready();
  if (picks.length < slots) {
    // Not enough rested vessels — draft the longest-resting regardless of cooldown.
    const short = slots - picks.length;
    const pickedIds = picks.map((p) => p.id);
    const extras = db
      .prepare(
        `SELECT * FROM bot_pool WHERE status IN ('available','resting')
         ORDER BY available_at ASC, last_deployed_at ASC LIMIT ?`
      )
      .all(short + pickedIds.length)
      .filter((p) => !pickedIds.includes(p.id))
      .slice(0, short);
    picks = picks.concat(extras);
  }
  if (!picks.length) return;

  // node:sqlite (Node 22) has no .transaction() helper — drive one manually.
  db.exec("BEGIN");
  try {
    for (const bot of picks) {
      const fid = id();
      db.prepare(
        `INSERT INTO fighters (id, user_id, name, prompt, filename, wins, status, created_at, is_bot)
         VALUES (?, 'system', ?, ?, ?, ?, 'living', ?, 1)`
      ).run(
        fid,
        bot.name,
        "A founding vessel of the pit, returned from the ash.",
        bot.filename,
        bot.base_wins,
        nowIso()
      );
      db.prepare(
        `UPDATE bot_pool
         SET status = 'deployed', deployments = deployments + 1, fighter_id = ?,
             last_deployed_at = ?, available_at = NULL
         WHERE id = ?`
      ).run(fid, nowIso(), bot.id);
    }
    db.exec("COMMIT");
  } catch (err) {
    db.exec("ROLLBACK");
    console.warn("[kiln] bot deployment failed —", err.message);
    return;
  }
  console.log(`[kiln] ${picks.length} founding vessel(s) climbed back onto the stack`);
}

function restBot(db, fighter, winnerId) {
  const pool = db.prepare("SELECT * FROM bot_pool WHERE fighter_id = ?").get(fighter.id);
  if (!pool) return;
  const availableAt = new Date(
    Date.now() + Math.max(0, BOT_COOLDOWN_DAYS) * 24 * 60 * 60 * 1000
  ).toISOString();
  db.prepare(
    `UPDATE bot_pool
     SET status = 'resting', fighter_id = NULL, deaths = deaths + 1,
         wins_gained = wins_gained + ?, available_at = ?
     WHERE id = ?`
  ).run(Math.max(0, fighter.wins - pool.base_wins), availableAt, pool.id);
  const due = db
    .prepare("UPDATE bot_pool SET status = 'available' WHERE status = 'resting' AND available_at <= ?")
    .run(nowIso());
  if (due.changes > 0) {
    console.log(`[kiln] ${due.changes} founding vessel(s) finished resting and may return`);
  }
}

function applyVerdict(db, match, result) {
  const winnerId = result.winnerId;
  const loserId = winnerId === match.left_id ? match.right_id : match.left_id;
  const judged = nowIso();
  db.prepare(
    `UPDATE matches SET winner_id = ?, margin = ?, narration = ?, left_scout = ?, right_scout = ?,
       raw_json = ?, status = 'done', judged_at = ?, judge = ?
     WHERE id = ?`
  ).run(
    winnerId,
    result.margin,
    result.narration,
    JSON.stringify(result.left || {}),
    JSON.stringify(result.right || {}),
    result.raw ? JSON.stringify(result.raw) : null,
    judged,
    result.judge,
    match.id
  );
  db.prepare("UPDATE fighters SET wins = wins + 1, career_wins = career_wins + 1 WHERE id = ?").run(winnerId);
  db.prepare(
    `UPDATE fighters SET status = 'dead', died_at = ?, killed_by = ?, death_match_id = ? WHERE id = ?`
  ).run(judged, winnerId, match.id, loserId);
  const loser = db.prepare("SELECT * FROM fighters WHERE id = ?").get(loserId);
  if (loser?.is_bot) restBot(db, loser, winnerId);
}

export async function processBatch(db) {
  const round = currentRound(db);
  if (!round || (round.status !== "running" && round.status !== "stalled")) {
    return { skipped: true };
  }

  if (new Date(round.next_batch_at).getTime() > Date.now()) {
    return { waiting: true, nextBatchAt: round.next_batch_at };
  }

  const pending = db
    .prepare(
      `SELECT * FROM matches WHERE round_id = ? AND status IN ('pending','error') ORDER BY seq ASC LIMIT ?`
    )
    .all(round.id, BATCH_SIZE);

  if (!pending.length) {
    db.prepare(
      "UPDATE rounds SET status = 'complete', completed_at = ? WHERE id = ?"
    ).run(nowIso(), round.id);
    console.log(`[kiln] round ${round.number} complete — the stack rests until the next sealing`);
    return { complete: true };
  }

  console.log(
    `[kiln] firing batch ${round.batch_index + 1} — matches ${pending[0].seq}–${pending[pending.length - 1].seq}`
  );

  let judged = 0;
  for (const match of pending) {
    const left = db.prepare("SELECT * FROM fighters WHERE id = ?").get(match.left_id);
    const right = db.prepare("SELECT * FROM fighters WHERE id = ?").get(match.right_id);
    db.prepare("UPDATE matches SET status = 'judging', attempts = attempts + 1 WHERE id = ?").run(
      match.id
    );
    try {
      const result = await judgeMatch(left, right);
      applyVerdict(db, match, result);
      judged++;
      console.log(
        `[kiln]  ${left.name} vs ${right.name} → ${result.winnerId === left.id ? left.name : right.name} (${result.judge})`
      );
    } catch (err) {
      db.prepare("UPDATE matches SET status = 'pending' WHERE id = ?").run(match.id);
      if (err.code === "RATE_LIMIT") {
        const retry = new Date(Date.now() + 10 * 60 * 1000).toISOString();
        db.prepare(
          "UPDATE rounds SET status = 'stalled', next_batch_at = ?, notes = ? WHERE id = ?"
        ).run(retry, "stutter: gemini 429", round.id);
        console.warn(`[kiln] rate limited — stutter until ${retry}`);
        return { stutter: true, judged, nextBatchAt: retry };
      }
      console.warn(`[kiln] match ${match.seq} failed:`, err.message);
    }
  }

  const still = db
    .prepare("SELECT COUNT(*) AS n FROM matches WHERE round_id = ? AND status != 'done'")
    .get(round.id).n;

  if (!still) {
    db.prepare(
      "UPDATE rounds SET status = 'complete', completed_at = ?, batch_index = batch_index + 1 WHERE id = ?"
    ).run(nowIso(), round.id);
    console.log(`[kiln] round ${round.number} complete — the stack rests until the next sealing`);
    return { complete: true, judged };
  }

  const next = new Date(Date.now() + BATCH_INTERVAL_MS).toISOString();
  db.prepare(
    "UPDATE rounds SET status = 'running', batch_index = batch_index + 1, next_batch_at = ? WHERE id = ?"
  ).run(next, round.id);
  return { judged, nextBatchAt: next, remaining: still };
}

export async function tick(db) {
  if (ticking) return;
  ticking = true;
  try {
    const last = currentRound(db);

    // A firing is in progress: judge batches, ignore the clock.
    if (last && (last.status === "running" || last.status === "stalled")) {
      await processBatch(db);
      return;
    }

    const livingN = db
      .prepare("SELECT COUNT(*) AS n FROM fighters WHERE status = 'living'")
      .get().n;

    // First firing ever: seal and fire as soon as two vessels stand, so a
    // fresh kiln welcomes you instead of waiting for midnight.
    if (!last) {
      fillFromGate(db);
      if (livingN >= 2) {
        const opened = startRound(db);
        if (opened) await processBatch(db);
      }
      return;
    }

    // The sealing: in the hour before the fire, the gate line steps up and the
    // founding dead fill the missing slots. No bots materialize outside it.
    if (isSealing()) fillFromGate(db);

    // Fire at (or after) the daily FIRE_UTC_HOUR, once per UTC day.
    const fireAt = lastFireAt().getTime();
    const alreadyFiredTonight = new Date(last.started_at).getTime() >= fireAt;
    if (!alreadyFiredTonight && Date.now() >= fireAt && livingN >= 2) {
      const opened = startRound(db);
      if (opened) await processBatch(db);
    }
  } catch (err) {
    console.error("[kiln] tick error", err);
  } finally {
    ticking = false;
  }
}

export function startScheduler(db) {
  // External cron (node server/job.js, a managed scheduler, or a POST to
  // the authenticated /api/round/tick) can own the round. Set KILN_POLL=0 in a
  // cron-driven deployment so only one trigger is live; leave it on (default)
  // for a single self-scheduling process. tick() is idempotent either way.
  const poll = process.env.KILN_POLL !== "0";
  const t = async () => {
    try {
      await tick(db);
    } catch (e) {
      console.error(e);
    }
  };
  if (poll) {
    setTimeout(t, 2000);
    setInterval(t, 15 * 1000);
  }
  console.log(
    `[kiln] internal round poller ${poll ? "on (15s)" : "off — external cron drives the round"}`
  );
}
