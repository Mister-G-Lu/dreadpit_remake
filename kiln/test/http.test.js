import { describe, it, before, after } from "node:test";
import assert from "node:assert/strict";
import { createServer } from "node:http";
import { openDb } from "../server/db.js";
import { createApp } from "../server/app.js";

class CookieJar {
  constructor() {
    this.cookie = "";
  }

  absorb(res) {
    const raw = typeof res.headers.getSetCookie === "function" ? res.headers.getSetCookie() : [];
    const line = raw[0] || res.headers.get("set-cookie") || "";
    if (!line) return;
    if (/Max-Age=0/i.test(line) || /kiln_session=;/i.test(line)) {
      this.cookie = "";
      return;
    }
    const m = line.match(/kiln_session=[^;]+/);
    if (m) this.cookie = m[0];
  }
}

describe("HTTP auth integration", { concurrency: false }, () => {
  let db;
  let server;
  let base;
  const jar = new CookieJar();

  async function req(path, { method = "GET", json, authed = true } = {}) {
    const headers = {};
    if (json !== undefined) headers["Content-Type"] = "application/json";
    if (authed && jar.cookie) headers.Cookie = jar.cookie;
    const res = await fetch(base + path, {
      method,
      headers,
      body: json !== undefined ? JSON.stringify(json) : undefined,
    });
    jar.absorb(res);
    const data = await res.json().catch(() => ({}));
    return { status: res.status, data, headers: res.headers };
  }

  before(async () => {
    db = openDb(":memory:");
    const app = createApp(db);
    server = createServer(app);
    await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
    const { port } = server.address();
    base = `http://127.0.0.1:${port}`;
  });

  after(async () => {
    await new Promise((resolve) => server.close(resolve));
    db.close();
  });

  it("reports health", async () => {
    const { status, data } = await req("/api/health", { authed: false });
    assert.equal(status, 200);
    assert.equal(data.ok, true);
    assert.equal(data.name, "kiln");
  });

  it("register validation uses plain English", async () => {
    let res = await req("/api/auth/register", {
      method: "POST",
      json: { username: "ab", password: "secret1" },
      authed: false,
    });
    assert.equal(res.status, 400);
    assert.equal(res.data.error, "Username must be 3–20 letters, numbers, or underscores.");

    res = await req("/api/auth/register", {
      method: "POST",
      json: { username: "walker", password: "123" },
      authed: false,
    });
    assert.equal(res.status, 400);
    assert.equal(res.data.error, "Password must be at least 6 characters.");
  });

  it("registers, sets an HttpOnly session cookie, and returns /me", async () => {
    jar.cookie = "";
    const res = await req("/api/auth/register", {
      method: "POST",
      json: { username: "Walker", password: "secret1" },
    });
    assert.equal(res.status, 200);
    assert.equal(res.data.user.username, "walker");
    assert.match(jar.cookie, /^kiln_session=/);
    const setCookie = res.headers.get("set-cookie") || "";
    assert.match(setCookie, /HttpOnly/i);
    assert.doesNotMatch(setCookie, /GitHub Pages|live flue/i);

    const me = await req("/api/auth/me");
    assert.equal(me.status, 200);
    assert.equal(me.data.user.username, "walker");
    assert.equal(me.data.sparksMax, 10);
  });

  it("rejects a second register of the same name", async () => {
    const res = await req("/api/auth/register", {
      method: "POST",
      json: { username: "walker", password: "secret1" },
      authed: false,
    });
    assert.equal(res.status, 409);
    assert.equal(res.data.error, "That username is already taken.");
  });

  it("logs out and requires login again", async () => {
    const out = await req("/api/auth/logout", { method: "POST", json: {} });
    assert.equal(out.status, 200);
    const me = await req("/api/auth/me");
    assert.equal(me.data.user, null);
  });

  it("rejects a bad password then accepts the real one", async () => {
    let res = await req("/api/auth/login", {
      method: "POST",
      json: { username: "walker", password: "nope123" },
    });
    assert.equal(res.status, 401);
    assert.equal(res.data.error, "Wrong username or password.");
    assert.doesNotMatch(res.data.error, /flue|clay|gallery/i);

    res = await req("/api/auth/login", {
      method: "POST",
      json: { username: "walker", password: "secret1" },
    });
    assert.equal(res.status, 200);
    assert.equal(res.data.user.username, "walker");
    const me = await req("/api/auth/me");
    assert.equal(me.data.user.username, "walker");
  });

  it("blocks forging without a session and with a short prompt", async () => {
    const saved = jar.cookie;
    jar.cookie = "";
    let res = await req("/api/forge/spark", {
      method: "POST",
      json: { prompt: "abcdefghijklmnop" },
      authed: false,
    });
    assert.equal(res.status, 401);
    assert.equal(res.data.error, "Please log in first.");

    jar.cookie = saved;
    res = await req("/api/forge/spark", { method: "POST", json: { prompt: "tiny" } });
    assert.equal(res.status, 400);
    assert.equal(res.data.error, "Please write at least 8 characters (200 max).");
  });

  it("returns normal 404s", async () => {
    const f = await req("/api/fighters/does-not-exist");
    assert.equal(f.status, 404);
    assert.equal(f.data.error, "Fighter not found.");
    const m = await req("/api/matches/does-not-exist");
    assert.equal(m.status, 404);
    assert.equal(m.data.error, "Match not found.");
  });

  it("exposes public state without a session", async () => {
    jar.cookie = "";
    const res = await req("/api/state", { authed: false });
    assert.equal(res.status, 200);
    assert.equal(res.data.me, null);
    assert.ok(Array.isArray(res.data.living));
  });
});
