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
  return { users: [], sparks: [], fighters: [] };
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
  const user = currentUser(store);
  const localLiving = store.fighters.filter((f) => f.status === "living").map(publicFighter);
  const localGate = store.fighters.filter((f) => f.status === "gate").map(publicFighter);
  const localDead = store.fighters.filter((f) => f.status === "dead").length;
  return {
    ...demoState,
    maxRoster: MAX_ROSTER,
    sparksMax: SPARKS_MAX,
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
  const local = store.fighters.find((f) => f.id === idParam);
  if (local) {
    return {
      fighter: publicFighter(local),
      fights: [],
    };
  }
  const hit = demoFighters[idParam];
  if (!hit) fail("Fighter not found.", 404);
  return hit;
}

function getMatch(idParam) {
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
  if (match && method === "GET") return getMatch(decodeURIComponent(match[1]));

  fail("This action isn't available right now.", 501);
}
