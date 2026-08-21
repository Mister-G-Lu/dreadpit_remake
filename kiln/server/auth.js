import { randomBytes, scryptSync, timingSafeEqual } from "node:crypto";
import { id, nowIso } from "./db.js";

export function hashPassword(password, salt = randomBytes(16).toString("hex")) {
  const hash = scryptSync(password, salt, 32).toString("hex");
  return { hash, salt };
}

export function verifyPassword(password, hash, salt) {
  const next = scryptSync(password, salt, 32);
  const prev = Buffer.from(hash, "hex");
  if (next.length !== prev.length) return false;
  return timingSafeEqual(next, prev);
}

export function parseCookies(req) {
  const header = req.headers.cookie || "";
  const out = {};
  for (const part of header.split(";")) {
    const i = part.indexOf("=");
    if (i < 0) continue;
    out[part.slice(0, i).trim()] = decodeURIComponent(part.slice(i + 1).trim());
  }
  return out;
}

export function setSessionCookie(res, token, secure) {
  const parts = [
    `kiln_session=${token}`,
    "Path=/",
    "HttpOnly",
    "SameSite=Lax",
    `Max-Age=${60 * 60 * 24 * 30}`,
  ];
  if (secure) parts.push("Secure");
  res.setHeader("Set-Cookie", parts.join("; "));
}

export function clearSessionCookie(res, secure) {
  const parts = [
    "kiln_session=",
    "Path=/",
    "HttpOnly",
    "SameSite=Lax",
    "Max-Age=0",
  ];
  if (secure) parts.push("Secure");
  res.setHeader("Set-Cookie", parts.join("; "));
}

export function isSecure(req) {
  return req.headers["x-forwarded-proto"] === "https" || req.secure;
}

export function createSession(db, userId) {
  const token = randomBytes(24).toString("hex");
  db.prepare("INSERT INTO sessions (token, user_id, created_at) VALUES (?, ?, ?)").run(
    token,
    userId,
    nowIso()
  );
  return token;
}

export function register(db, username, password) {
  const name = String(username || "").trim().toLowerCase();
  if (!/^[a-z0-9_]{3,20}$/.test(name)) {
    throw Object.assign(new Error("Username: 3–20 letters, numbers, underscore."), {
      status: 400,
    });
  }
  if (name === "kiln" || name === "system") {
    throw Object.assign(new Error("That name is reserved."), { status: 400 });
  }
  if (String(password || "").length < 6) {
    throw Object.assign(new Error("Password must be at least 6 characters."), {
      status: 400,
    });
  }
  const exists = db.prepare("SELECT id FROM users WHERE username = ?").get(name);
  if (exists) {
    throw Object.assign(new Error("That name is already taken."), { status: 409 });
  }
  const { hash, salt } = hashPassword(password);
  const userId = id();
  db.prepare(
    "INSERT INTO users (id, username, pass_hash, pass_salt, created_at) VALUES (?, ?, ?, ?, ?)"
  ).run(userId, name, hash, salt, nowIso());
  return { id: userId, username: name };
}

export function login(db, username, password) {
  const name = String(username || "").trim().toLowerCase();
  const row = db.prepare("SELECT * FROM users WHERE username = ?").get(name);
  if (!row || row.id === "system" || !verifyPassword(password, row.pass_hash, row.pass_salt)) {
    throw Object.assign(new Error("Wrong username or password."), { status: 401 });
  }
  return { id: row.id, username: row.username };
}
