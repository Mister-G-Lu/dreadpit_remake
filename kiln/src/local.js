import { demoAsh, demoFighters, demoMatches, demoState } from "./demo.js";

const STORE_KEY = "kiln_local_v1";
const SESSION_KEY = "kiln_local_session";
const SPARKS_MAX = 10;
const MAX_ROSTER = 256;

function fail(message, status = 400) {
  const err = new Error(message);
  err.status = status;
  throw err;
}

function utcDate(d = new Date()) {
  return d.toISOString().slice(0, 10);
}

function nowIso() {
  return new Date().toISOString();
}

function id(n = 8) {
  const bytes = crypto.getRandomValues(new Uint8Array(n));
  return [...bytes].map((b) => b.toString(16).padStart(2, "0")).join("");
}

function emptyStore() {
  return { users: [], sparks: [], fighters: [], rounds: [], matches: [] };
}

function load() {
  try {
    const raw = localStorage.getItem(STORE_KEY);
    if (!raw) return emptyStore();
    const data = JSON.parse(raw);
    return {
      users: Array.isArray(data.users) ? data.users : [],
      sparks: Array.isArray(data.sparks) ? data.sparks : [],
      fighters: Array.isArray(data.fighters) ? data.fighters : [],
      rounds: Array.isArray(data.rounds) ? data.rounds : [],
      matches: Array.isArray(data.matches) ? data.matches : [],
    };
  } catch {
    return emptyStore();
  }
}

function save(store) {
  localStorage.setItem(STORE_KEY, JSON.stringify(store));
}

function sessionId() {
  return localStorage.getItem(SESSION_KEY) || "";
}

function setSession(userId) {
  if (userId) localStorage.setItem(SESSION_KEY, userId);
  else localStorage.removeItem(SESSION_KEY);
}

function currentUser(store = load()) {
  const sid = sessionId();
  if (!sid) return null;
  return store.users.find((u) => u.id === sid) || null;
}

function requireUser(store) {
  const user = currentUser(store);
  if (!user) fail("Please log in first.", 401);
  return user;
}

function hex(buf) {
  return [...new Uint8Array(buf)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

function saltBytes(hexStr) {
  const pairs = hexStr.match(/.{2}/g) || [];
  return Uint8Array.from(pairs.map((p) => parseInt(p, 16)));
}

async function hashPassword(password, saltHex) {
  const enc = new TextEncoder();
  const key = await crypto.subtle.importKey("raw", enc.encode(password), "PBKDF2", false, ["deriveBits"]);
  const bits = await crypto.subtle.deriveBits(
    { name: "PBKDF2", salt: saltBytes(saltHex), iterations: 100000, hash: "SHA-256" },
    key,
    256
  );
  return hex(bits);
}

function randomSalt() {
  return hex(crypto.getRandomValues(new Uint8Array(16)));
}

function sparksToday(store, userId) {
  const day = utcDate();
  return store.sparks.filter((s) => s.userId === userId && s.createdAt.slice(0, 10) === day).length;
}

function admittedToday(store) {
  const start = `${utcDate()}T00:00:00.000Z`;
  return store.fighters.filter((f) => f.createdAt >= start).length;
}

function publicUser(user) {
  return { id: user.id, username: user.username };
}

function slotsUsed(store, userId) {
  return store.fighters.filter(
    (f) => f.userId === userId && (f.status === "living" || f.status === "gate")
  ).length;
}

function publicFighter(row) {
  return {
    id: row.id,
    name: row.name,
    prompt: row.status === "dead" ? null : row.prompt,
    sealed: row.status === "dead",
    image: row.image,
    wins: row.wins,
    careerWins: row.careerWins ?? row.wins,
    status: row.status,
    owner: row.owner,
    createdAt: row.createdAt,
    diedAt: row.diedAt || null,
    killerId: row.killedBy || null,
    killerName: row.killerName || null,
  };
}

function pollenKey() {
  return localStorage.getItem("kiln_pollen_key") || "";
}

function sparkUrl(prompt, seed, apiKey) {
  const params = new URLSearchParams({
    model: "flux",
    width: "768",
    height: "768",
    seed: String(seed),
    nologo: apiKey ? "true" : "false",
    private: "true",
  });
  if (apiKey) params.set("key", apiKey);
  return `https://image.pollinations.ai/prompt/${encodeURIComponent(prompt)}?${params}`;
}

function stampSvg(prompt, seed) {
  const caption = String(prompt)
    .slice(0, 42)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
  const hue = (seed * 37) % 360;
  const hue2 = (seed * 91) % 360;
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 768 768">
  <defs>
    <radialGradient id="g" cx="50%" cy="40%">
      <stop offset="0%" stop-color="hsl(${hue2},55%,28%)"/>
      <stop offset="100%" stop-color="#0a0908"/>
    </radialGradient>
  </defs>
  <rect width="768" height="768" fill="url(#g)"/>
  <circle cx="${280 + (seed % 200)}" cy="${260 + (seed % 220)}" r="${140 + (seed % 120)}" fill="none" stroke="hsl(${hue},70%,48%)" stroke-width="18"/>
  <rect x="48" y="48" width="672" height="672" fill="none" stroke="#d4894a" stroke-width="3" opacity="0.5"/>
  <text x="384" y="640" text-anchor="middle" fill="#d4c4b0" font-family="Georgia, serif" font-size="22" font-style="italic">${caption}</text>
  <text x="384" y="700" text-anchor="middle" fill="#8d8174" font-family="sans-serif" font-size="14" letter-spacing="4">LOCAL · SEED ${seed}</text>
</svg>`;
  return `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`;
}

function loadRemoteImage(url, ms = 90000) {
  return new Promise((resolve, reject) => {
    const img = new Image();
    const t = setTimeout(() => {
      img.src = "";
      reject(new Error("timeout"));
    }, ms);
    img.onload = () => {
      clearTimeout(t);
      resolve();
    };
    img.onerror = () => {
      clearTimeout(t);
      reject(new Error("failed"));
    };
    img.src = url;
  });
}

function requireCrypto() {
  if (!globalThis.crypto?.subtle) {
    fail("This page needs HTTPS to create or log into an account.");
  }
}

async function register(store, username, password) {
  requireCrypto();
  const name = String(username || "").trim().toLowerCase();
  if (!/^[a-z0-9_]{3,20}$/.test(name)) {
    fail("Username must be 3–20 letters, numbers, or underscores.");
  }
  if (name === "kiln" || name === "system") {
    fail("That username is reserved. Please choose another.");
  }
  if (String(password || "").length < 6) {
    fail("Password must be at least 6 characters.");
  }
  if (store.users.some((u) => u.username === name)) {
    fail("That username is already taken.", 409);
  }
  const salt = randomSalt();
  const passHash = await hashPassword(password, salt);
  const user = { id: id(), username: name, passHash, salt, createdAt: nowIso() };
  store.users.push(user);
  setSession(user.id);
  save(store);
  return { user: publicUser(user) };
}

async function login(store, username, password) {
  const name = String(username || "").trim().toLowerCase();
  const row = store.users.find((u) => u.username === name);
  if (!row) fail("Wrong username or password.", 401);
  const next = await hashPassword(password, row.salt);
  if (next !== row.passHash) fail("Wrong username or password.", 401);
  setSession(row.id);
  save(store);
  return { user: publicUser(row) };
}

function heatScore(fighter) {
  const t = `${fighter.name} ${fighter.prompt || ""}`.toLowerCase();
  const keys = [
    "fire",
    "molten",
    "forge",
    "ember",
    "glow",
    "iron",
    "armor",
    "wing",
    "shadow",
    "cannon",
    "hook",
    "skull",
    "furnace",
  ];
  return keys.reduce((n, k) => n + (t.includes(k) ? 1 : 0), 0) + (fighter.wins || 0) * 0.25;
}

function lesserEye(left, right) {
  const lh = heatScore(left);
  const rh = heatScore(right);
  const winnerLeft = lh === rh ? left.id < right.id : lh > rh;
  const winner = winnerLeft ? left : right;
  const loser = winnerLeft ? right : left;
  const margin = Math.abs(lh - rh) > 2 ? "clear" : "narrow";
  return {
    winnerId: winner.id,
    margin,
    judge: "lesser-eye",
    narration: `The lesser eye of this device (no shared Gemini firing) reads heat and mass alone. ${left.name} and ${right.name} are shoved into the mouth together. The kiln rules: ${winner.name} holds shape. ${loser.name} slumps, cracks, and is raked into the ash.`,
  };
}

function pairLocal(fighters, roundNumber) {
  const list = fighters
    .filter((f) => f.status === "living")
    .sort((a, b) => (b.wins || 0) - (a.wins || 0) || (a.createdAt || "").localeCompare(b.createdAt || ""));
  const bye = [];
  const pool = list.slice();
  if (roundNumber % 2 === 1 && pool.length >= 3) bye.push(pool.shift());
  if (pool.length % 2 === 1) bye.push(pool.pop());
  const pairs = [];
  for (let i = 0; i < pool.length; i += 2) pairs.push([pool[i], pool[i + 1]]);
  return { pairs, bye };
}

function lastFireAt(d = new Date()) {
  const fire = Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate(), 0, 0, 0, 0);
  return fire;
}

function fillLocalGate(store) {
  const livingN = store.fighters.filter((f) => f.status === "living").length;
  const slots = MAX_ROSTER - demoState.living.length - livingN;
  if (slots <= 0) return;
  const waiting = store.fighters.filter((f) => f.status === "gate").slice(0, slots);
  for (const f of waiting) f.status = "living";
}

function currentLocalRound(store) {
  return store.rounds.slice().sort((a, b) => (b.number || 0) - (a.number || 0))[0] || null;
}

function publicMatch(store, m) {
  const left = store.fighters.find((f) => f.id === m.leftId);
  const right = store.fighters.find((f) => f.id === m.rightId);
  if (!left || !right) return null;
  return {
    id: m.id,
    seq: m.seq,
    batch: 1,
    status: m.status,
    margin: m.margin,
    narration: m.narration,
    judgedAt: m.judgedAt,
    judge: m.judge,
    winnerId: m.winnerId,
    left: { id: left.id, name: left.name, image: left.image, wins: left.wins },
    right: { id: right.id, name: right.name, image: right.image, wins: right.wins },
  };
}

function fireLocalRound(store) {
  const living = store.fighters.filter((f) => f.status === "living");
  if (living.length < 2) return null;
  const last = currentLocalRound(store);
  const number = (last?.number || 0) + 1;
  const { pairs, bye } = pairLocal(store.fighters, number);
  if (!pairs.length) return null;
  const started = nowIso();
  const round = {
    id: id(),
    number,
    status: "complete",
    startedAt: started,
    completedAt: started,
    batchIndex: 1,
    nextBatchAt: null,
    notes: bye.length ? `bye:${bye.map((b) => b.name).join(",")}` : null,
  };
  const matches = [];
  pairs.forEach((pair, i) => {
    const [left, right] = pair;
    const result = lesserEye(left, right);
    const judged = nowIso();
    const winner = left.id === result.winnerId ? left : right;
    const loser = left.id === result.winnerId ? right : left;
    winner.wins = (winner.wins || 0) + 1;
    winner.careerWins = (winner.careerWins ?? winner.wins - 1) + 1;
    loser.status = "dead";
    loser.diedAt = judged;
    loser.killedBy = winner.id;
    loser.killerName = winner.name;
    matches.push({
      id: id(10),
      roundId: round.id,
      seq: i + 1,
      leftId: left.id,
      rightId: right.id,
      status: "done",
      winnerId: result.winnerId,
      margin: result.margin,
      narration: result.narration,
      judgedAt: judged,
      judge: result.judge,
    });
  });
  round.matchesTotal = matches.length;
  round.matchesDone = matches.length;
  store.rounds.push(round);
  store.matches.push(...matches);
  return round;
}

function tickLocal(store) {
  fillLocalGate(store);
  const livingN = store.fighters.filter((f) => f.status === "living").length;
  const last = currentLocalRound(store);
  if (!last) {
    if (livingN >= 2) fireLocalRound(store);
    return;
  }
  const fireAt = lastFireAt();
  const already = new Date(last.startedAt).getTime() >= fireAt;
  if (!already && Date.now() >= fireAt && livingN >= 2) fireLocalRound(store);
}

function mePayload(store) {
  const user = currentUser(store);
  if (!user) return { user: null, sparksUsed: 0, sparksMax: SPARKS_MAX };
  return {
    user: publicUser(user),
    sparksUsed: sparksToday(store, user.id),
    sparksMax: SPARKS_MAX,
  };
}

function statePayload(store) {
  tickLocal(store);
  save(store);
  const user = currentUser(store);
  const localLiving = store.fighters.filter((f) => f.status === "living").map(publicFighter);
  const localGate = store.fighters.filter((f) => f.status === "gate").map(publicFighter);
  const localDead = store.fighters.filter((f) => f.status === "dead").length;
  const last = currentLocalRound(store);
  const localMatches = last
    ? store.matches
        .filter((m) => m.roundId === last.id)
        .sort((a, b) => a.seq - b.seq)
        .map((m) => publicMatch(store, m))
        .filter(Boolean)
    : [];
  return {
    ...demoState,
    maxRoster: MAX_ROSTER,
    sparksMax: SPARKS_MAX,
    gemini: false,
    living: [...localLiving, ...demoState.living],
    gate: localGate,
    deadCount: demoState.deadCount + localDead,
    admittedToday: admittedToday(store),
    me: user
      ? {
          id: user.id,
          username: user.username,
          sparksUsed: sparksToday(store, user.id),
          slots: { used: slotsUsed(store, user.id), max: 15 },
        }
      : null,
    static: true,
    local: true,
    round: last
      ? {
          id: last.id,
          number: last.number,
          status: last.status,
          startedAt: last.startedAt,
          completedAt: last.completedAt,
          batchIndex: last.batchIndex,
          nextBatchAt: last.nextBatchAt,
          notes: last.notes,
          matchesTotal: last.matchesTotal ?? localMatches.length,
          matchesDone: last.matchesDone ?? localMatches.length,
        }
      : demoState.round,
    matches: localMatches.length ? [...localMatches, ...demoState.matches] : demoState.matches,
  };
}

async function fireSpark(store, body) {
  const user = requireUser(store);
  const prompt = String(body?.prompt || "").trim().slice(0, 200);
  if (prompt.length < 8) {
    fail("Please write at least 8 characters (200 max).");
  }
  const used = sparksToday(store, user.id);
  if (used >= SPARKS_MAX) {
    fail("You've used all 10 image generations for today. Try again tomorrow.", 429);
  }
  const seed =
    Number.isFinite(Number(body?.seed)) && Number(body.seed) >= 0
      ? Number(body.seed)
      : Math.floor(Math.random() * 99999);
  const apiKey = pollenKey();
  const remote = sparkUrl(prompt, seed, apiKey);
  let image = remote;
  try {
    await loadRemoteImage(remote);
  } catch {
    image = stampSvg(prompt, seed);
  }
  const spark = {
    id: id(10),
    userId: user.id,
    prompt,
    seed,
    image,
    createdAt: nowIso(),
  };
  store.sparks.push(spark);
  save(store);
  return {
    id: spark.id,
    seed: spark.seed,
    image: spark.image,
    sparksUsed: sparksToday(store, user.id),
    sparksMax: SPARKS_MAX,
  };
}

function submitVessel(store, body) {
  const user = requireUser(store);
  const name = String(body?.name || "").trim().slice(0, 40);
  const sparkId = String(body?.sparkId || "").trim();
  if (name.length < 2) fail("Please enter a fighter name (at least 2 characters).");
  if (/^fighter[\s_-]?\d*$/i.test(name)) {
    fail("That name is reserved. Please choose another.");
  }
  const spark = store.sparks.find((s) => s.id === sparkId && s.userId === user.id);
  if (!spark) fail("Pick an image you generated today.");
  if (store.fighters.some((f) => f.sparkId === spark.id)) {
    fail("That image is already a fighter.", 409);
  }
  if (admittedToday(store) >= MAX_ROSTER) {
    fail("The daily limit of 256 new fighters has been reached. Try again tomorrow.", 409);
  }
  const livingN = demoState.living.length + store.fighters.filter((f) => f.status === "living").length;
  const status = livingN >= MAX_ROSTER ? "gate" : "living";
  const fighter = {
    id: spark.id.slice(0, 12) + "f",
    userId: user.id,
    owner: user.username,
    name,
    prompt: spark.prompt,
    sparkId: spark.id,
    image: spark.image,
    wins: 0,
    status,
    createdAt: nowIso(),
    diedAt: null,
    killedBy: null,
    killerName: null,
  };
  store.fighters.push(fighter);
  save(store);
  return { fighter: publicFighter(fighter), queued: status === "gate" };
}

function getFighter(store, idParam) {
  tickLocal(store);
  save(store);
  const local = store.fighters.find((f) => f.id === idParam);
  if (local) {
    const fights = store.matches
      .filter((m) => m.leftId === local.id || m.rightId === local.id)
      .sort((a, b) => (b.judgedAt || "").localeCompare(a.judgedAt || ""))
      .map((m) => {
        const pub = publicMatch(store, m);
        const opponent = pub.left.id === local.id ? pub.right : pub.left;
        const round = store.rounds.find((r) => r.id === m.roundId);
        return {
          id: m.id,
          round: round?.number || 1,
          status: m.status,
          winnerId: m.winnerId,
          foughtAt: m.judgedAt,
          opponent: { id: opponent.id, name: opponent.name, image: opponent.image },
        };
      });
    return { fighter: publicFighter(local), fights };
  }
  const hit = demoFighters[idParam];
  if (!hit) fail("Fighter not found.", 404);
  return hit;
}

function getMatch(store, idParam) {
  tickLocal(store);
  save(store);
  const local = store.matches.find((m) => m.id === idParam);
  if (local) {
    const match = publicMatch(store, local);
    if (!match) fail("Match not found.", 404);
    return { match };
  }
  const hit = demoMatches[idParam];
  if (!hit) fail("Match not found.", 404);
  return hit;
}

function myFighters(store) {
  const user = requireUser(store);
  const fighters = store.fighters
    .filter((f) => f.userId === user.id)
    .sort((a, b) => {
      const rank = { living: 0, gate: 1, dead: 2 };
      return (
        (rank[a.status] ?? 2) - (rank[b.status] ?? 2) ||
        (b.careerWins ?? b.wins ?? 0) - (a.careerWins ?? a.wins ?? 0) ||
        (b.createdAt || "").localeCompare(a.createdAt || "")
      );
    })
    .map(publicFighter);
  return {
    fighters,
    slots: { used: slotsUsed(store, user.id), max: 15 },
  };
}

function resurrectFighter(store, idParam) {
  const user = requireUser(store);
  const fighter = store.fighters.find((f) => f.id === idParam && f.userId === user.id);
  if (!fighter) fail("No such vessel of yours.", 404);
  if (fighter.status !== "dead") fail("Only the dead can be raised.", 409);
  if (slotsUsed(store, user.id) >= 15) fail("All 15 of your vessel slots are filled. Free one first.", 409);
  fighter.status = "living";
  fighter.wins = 0;
  fighter.createdAt = nowIso();
  fighter.diedAt = null;
  fighter.killedBy = null;
  fighter.killerName = null;
  save(store);
  return { fighter: publicFighter(fighter), queued: false };
}

export async function localApi(path, opts = {}) {
  const method = (opts.method || "GET").toUpperCase();
  const body = opts.json || {};
  const store = load();

  if (path === "/api/health") return { ok: true, name: "kiln-local" };
  if (path === "/api/auth/me") return mePayload(store);
  if (path === "/api/state") return statePayload(store);
  if (path === "/api/ash") {
    tickLocal(store);
    save(store);
    const dead = [
      ...store.fighters.filter((f) => f.status === "dead").map(publicFighter),
      ...demoAsh.dead,
    ];
    return { dead };
  }
  if (path === "/api/auth/register" && method === "POST") return register(store, body.username, body.password);
  if (path === "/api/auth/login" && method === "POST") return login(store, body.username, body.password);
  if (path === "/api/auth/logout" && method === "POST") {
    setSession("");
    return { ok: true };
  }
  if (path === "/api/forge/spark" && method === "POST") return fireSpark(store, body);
  if (path === "/api/fighters" && method === "POST") return submitVessel(store, body);
  if (path === "/api/me/fighters" && method === "GET") return myFighters(store);

  const resurrect = path.match(/^\/api\/fighters\/(.+)\/resurrect$/);
  if (resurrect && method === "POST") return resurrectFighter(store, decodeURIComponent(resurrect[1]));

  const fighter = path.match(/^\/api\/fighters\/(.+)$/);
  if (fighter && method === "GET") return getFighter(store, decodeURIComponent(fighter[1]));

  const match = path.match(/^\/api\/matches\/(.+)$/);
  if (match && method === "GET") return getMatch(store, decodeURIComponent(match[1]));

  fail("This action isn't available right now.", 501);
}
