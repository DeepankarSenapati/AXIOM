import test from "node:test";
import assert from "node:assert/strict";
import { createHmac } from "node:crypto";
import { getUser, setToken } from "../src/auth.js";

const storage = new Map();
globalThis.localStorage = {
  getItem: (key) => storage.get(key) ?? null,
  setItem: (key, value) => storage.set(key, value),
  removeItem: (key) => storage.delete(key),
};

function signedToken(payload) {
  const header = Buffer.from(JSON.stringify({ alg: "HS256", typ: "JWT" })).toString("base64url");
  const body = Buffer.from(JSON.stringify(payload), "utf8").toString("base64url");
  const signature = createHmac("sha256", "test-only-key").update(`${header}.${body}`).digest("base64url");
  return `${header}.${body}.${signature}`;
}

test("reads signed JWT payloads containing base64url characters and UTF-8", () => {
  for (const email of ["xxx?@example.com", "xxx~@example.com", "café@example.com"]) {
    const token = signedToken({ sub: "demo-user", role: "token_holder", email });
    if (email.includes("?")) assert.match(token.split(".")[1], /_/);
    if (email.includes("~")) assert.match(token.split(".")[1], /-/);
    setToken(token);
    assert.equal(getUser().email, email);
  }
});

test("invalid payloads are treated as signed out", () => {
  setToken("not-a-valid-token");
  assert.equal(getUser(), null);
});
