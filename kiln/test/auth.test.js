import { describe, it, beforeEach } from "node:test";
import assert from "node:assert/strict";
import { openDb } from "../server/db.js";
import {
  createSession,
  hashPassword,
  login,
  parseCookies,
  register,
  verifyPassword,
} from "../server/auth.js";
import { userByToken } from "../server/db.js";

function freshDb() {
  return openDb(":memory:");
}

function throwsWith(fn, message, status) {
  assert.throws(fn, (err) => {
    assert.equal(err.message, message);
    if (status != null) assert.equal(err.status, status);
    return true;
  });
}

describe("auth (sqlite)", { concurrency: false }, () => {
  let db;
  beforeEach(() => {
    db = freshDb();
  });

  it("hashes and verifies a password", () => {
    const { hash, salt } = hashPassword("secret1");
    assert.equal(verifyPassword("secret1", hash, salt), true);
    assert.equal(verifyPassword("secret2", hash, salt), false);
  });

  it("registers a lowercased username and logs in", () => {
    const user = register(db, "AshWalker", "secret1");
    assert.equal(user.username, "ashwalker");
    assert.ok(user.id);
    const again = login(db, "ASHWALKER", "secret1");
    assert.equal(again.id, user.id);
    assert.equal(again.username, "ashwalker");
  });

  it("rejects short usernames with a clear message", () => {
    throwsWith(
      () => register(db, "ab", "secret1"),
      "Username must be 3–20 letters, numbers, or underscores.",
      400
    );
  });

  it("rejects usernames with spaces or symbols", () => {
    throwsWith(
      () => register(db, "bad name", "secret1"),
      "Username must be 3–20 letters, numbers, or underscores.",
      400
    );
    throwsWith(
      () => register(db, "nope!", "secret1"),
      "Username must be 3–20 letters, numbers, or underscores.",
      400
    );
  });

  it("rejects reserved names", () => {
    throwsWith(
      () => register(db, "kiln", "secret1"),
      "That username is reserved. Please choose another.",
      400
    );
    throwsWith(
      () => register(db, "system", "secret1"),
      "That username is reserved. Please choose another.",
      400
    );
  });

  it("rejects short passwords", () => {
    throwsWith(() => register(db, "walker", "123"), "Password must be at least 6 characters.", 400);
  });

  it("rejects duplicate usernames", () => {
    register(db, "walker", "secret1");
    throwsWith(() => register(db, "WALKER", "secret1"), "That username is already taken.", 409);
  });

  it("does not leak whether the username exists", () => {
    register(db, "walker", "secret1");
    throwsWith(() => login(db, "walker", "nope123"), "Wrong username or password.", 401);
    throwsWith(() => login(db, "nobody", "secret1"), "Wrong username or password.", 401);
  });

  it("blocks logging in as the system user", () => {
    throwsWith(() => login(db, "kiln", "x"), "Wrong username or password.", 401);
  });

  it("creates a session token that resolves to the user", () => {
    const user = register(db, "walker", "secret1");
    const token = createSession(db, user.id);
    const row = userByToken(db, token);
    assert.equal(row.id, user.id);
    assert.equal(userByToken(db, "nope"), null);
    assert.equal(userByToken(db, ""), null);
  });

  it("parses cookies", () => {
    assert.deepEqual(parseCookies({ headers: { cookie: "kiln_session=abc; other=1" } }), {
      kiln_session: "abc",
      other: "1",
    });
    assert.deepEqual(parseCookies({ headers: {} }), {});
  });
});
