import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");

function read(rel) {
  return readFileSync(join(root, rel), "utf8");
}

const GALLERY_POETRY = /This GitHub Pages cut is the gallery|Throw clay on a live flue|static kiln/;

describe("user-facing error copy", () => {
  it("does not reject login with gallery poetry", () => {
    for (const file of ["src/api.js", "src/local.js", "src/pages/Enter.jsx", "server/auth.js", "server/app.js"]) {
      assert.doesNotMatch(read(file), GALLERY_POETRY, file);
    }
  });

  it("keeps auth errors in plain English", () => {
    const auth = read("server/auth.js");
    assert.match(auth, /Wrong username or password/);
    assert.match(auth, /Password must be at least 6 characters/);
    assert.match(auth, /Username must be 3–20 letters, numbers, or underscores/);
    const app = read("server/app.js");
    assert.match(app, /Please log in first/);
    assert.doesNotMatch(app, /Enter the kiln first/);
  });
});
