import test from "node:test";
import assert from "node:assert/strict";
import { loginDestination } from "../src/loginDestination.js";

test("a known deep link is restored after sign-in", () => {
  assert.deepEqual(loginDestination({ pathname: "/lab", search: "?view=demo", hash: "#replay" }, "admin"), {
    pathname: "/lab", search: "?view=demo", hash: "#replay",
  });
});

test("an unknown or external destination falls back to the role home", () => {
  for (const pathname of ["//example.com", "https://example.com", "/login", "/unknown"]) {
    assert.equal(loginDestination({ pathname }, "admin"), "/admin");
  }
  assert.equal(loginDestination(null, "token_holder"), "/market");
});
