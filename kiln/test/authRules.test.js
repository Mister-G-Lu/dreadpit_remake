import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { validateCredentials } from "../src/authRules.js";

describe("login form validation", () => {
  it("requires both fields", () => {
    assert.equal(validateCredentials("login", "", ""), "Please enter a username and password.");
    assert.equal(validateCredentials("login", "walker", ""), "Please enter a username and password.");
    assert.equal(validateCredentials("login", "", "secret1"), "Please enter a username and password.");
    assert.equal(validateCredentials("register", "  ", "secret1"), "Please enter a username and password.");
  });

  it("allows any non-empty login pair (server checks the rest)", () => {
    assert.equal(validateCredentials("login", "x", "y"), "");
  });

  it("enforces register username and password rules", () => {
    assert.equal(
      validateCredentials("register", "ab", "secret1"),
      "Username must be 3–20 letters, numbers, or underscores."
    );
    assert.equal(
      validateCredentials("register", "bad name", "secret1"),
      "Username must be 3–20 letters, numbers, or underscores."
    );
    assert.equal(
      validateCredentials("register", "walker", "123"),
      "Password must be at least 6 characters."
    );
    assert.equal(validateCredentials("register", "walker", "secret1"), "");
    assert.equal(validateCredentials("register", "Ash_1", "secret1"), "");
  });
});
