import { describe, it, beforeEach } from "node:test";
import assert from "node:assert/strict";
import { webcrypto } from "node:crypto";

if (!globalThis.crypto?.subtle) globalThis.crypto = webcrypto;

const mem = new Map();
globalThis.localStorage = {
  getItem: (k) => (mem.has(k) ? mem.get(k) : null),
  setItem: (k, v) => {
    mem.set(String(k), String(v));
  },
  removeItem: (k) => {
    mem.delete(String(k));
  },
  clear: () => mem.clear(),
};

globalThis.Image = class Image {
  set src(_v) {
    queueMicrotask(() => this.onerror?.(new Event("error")));
  }
};

const { localApi } = await import("../src/local.js");

async function throwsStatus(fn, message, status) {
  await assert.rejects(fn, (err) => {
    assert.equal(err.message, message);
    if (status != null) assert.equal(err.status, status);
    return true;
  });
}

describe("local (browser) kiln", { concurrency: false }, () => {
  beforeEach(() => {
    mem.clear();
  });

  it("starts logged out", async () => {
    const me = await localApi("/api/auth/me");
    assert.equal(me.user, null);
    assert.equal(me.sparksMax, 10);
  });

  it("registers, persists a session, and logs out", async () => {
    const reg = await localApi("/api/auth/register", {
      method: "POST",
      json: { username: "AshWalker", password: "secret1" },
    });
    assert.equal(reg.user.username, "ashwalker");
    assert.equal((await localApi("/api/auth/me")).user.username, "ashwalker");

    const state = await localApi("/api/state");
    assert.equal(state.me.username, "ashwalker");
    assert.equal(state.local, true);

    await localApi("/api/auth/logout", { method: "POST", json: {} });
    assert.equal((await localApi("/api/auth/me")).user, null);
  });

  it("logs back in with the same password", async () => {
    await localApi("/api/auth/register", {
      method: "POST",
      json: { username: "walker", password: "secret1" },
    });
    await localApi("/api/auth/logout", { method: "POST", json: {} });
    const log = await localApi("/api/auth/login", {
      method: "POST",
      json: { username: "WALKER", password: "secret1" },
    });
    assert.equal(log.user.username, "walker");
  });

  it("returns clear errors for bad register/login", async () => {
    await throwsStatus(
      () => localApi("/api/auth/register", { method: "POST", json: { username: "ab", password: "secret1" } }),
      "Username must be 3–20 letters, numbers, or underscores.",
      400
    );
    await throwsStatus(
      () => localApi("/api/auth/register", { method: "POST", json: { username: "walker", password: "123" } }),
      "Password must be at least 6 characters.",
      400
    );
    await throwsStatus(
      () => localApi("/api/auth/register", { method: "POST", json: { username: "kiln", password: "secret1" } }),
      "That username is reserved. Please choose another.",
      400
    );
    await localApi("/api/auth/register", {
      method: "POST",
      json: { username: "walker", password: "secret1" },
    });
    await throwsStatus(
      () => localApi("/api/auth/register", { method: "POST", json: { username: "walker", password: "secret1" } }),
      "That username is already taken.",
      409
    );
    await localApi("/api/auth/logout", { method: "POST", json: {} });
    await throwsStatus(
      () => localApi("/api/auth/login", { method: "POST", json: { username: "walker", password: "nope123" } }),
      "Wrong username or password.",
      401
    );
    await throwsStatus(
      () => localApi("/api/auth/login", { method: "POST", json: { username: "ghost", password: "secret1" } }),
      "Wrong username or password.",
      401
    );
  });

  it("does not use the old gallery error copy", async () => {
    await assert.rejects(
      () => localApi("/api/auth/login", { method: "POST", json: { username: "nope", password: "secret1" } }),
      (err) => {
        assert.doesNotMatch(err.message, /GitHub Pages cut|Throw clay|live flue|static kiln/i);
        return true;
      }
    );
  });

  it("requires login before forging", async () => {
    await throwsStatus(
      () => localApi("/api/forge/spark", { method: "POST", json: { prompt: "abcdefgh" } }),
      "Please log in first.",
      401
    );
  });

  it("fires a local spark and enters a fighter", async () => {
    await localApi("/api/auth/register", {
      method: "POST",
      json: { username: "smith", password: "secret1" },
    });
    await throwsStatus(
      () => localApi("/api/forge/spark", { method: "POST", json: { prompt: "short" } }),
      "Please write at least 8 characters (200 max).",
      400
    );
    const spark = await localApi("/api/forge/spark", {
      method: "POST",
      json: { prompt: "Cathedral-shaped stone elemental with a bell-tower head", seed: 7 },
    });
    assert.ok(spark.id);
    assert.equal(spark.seed, 7);
    assert.equal(spark.sparksUsed, 1);
    assert.match(spark.image, /^data:image\/svg\+xml/);

    const entered = await localApi("/api/fighters", {
      method: "POST",
      json: { name: "Bell Colossus", sparkId: spark.id },
    });
    assert.equal(entered.fighter.name, "Bell Colossus");
    assert.equal(entered.fighter.owner, "smith");
    assert.equal(entered.queued, false);

    const state = await localApi("/api/state");
    assert.ok(state.living.some((f) => f.id === entered.fighter.id));

    const page = await localApi(`/api/fighters/${entered.fighter.id}`);
    assert.equal(page.fighter.name, "Bell Colossus");
  });

  it("serves demo fighters and a 404 with a normal message", async () => {
    const hit = await localApi("/api/fighters/hook");
    assert.equal(hit.fighter.name, "The Hook");
    await throwsStatus(() => localApi("/api/fighters/nope"), "Fighter not found.", 404);
    await throwsStatus(() => localApi("/api/matches/nope"), "Match not found.", 404);
  });
});
