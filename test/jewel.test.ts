/**
 * The library's tests: the TypeScript runtime must answer exactly like Python
 * (bench/jewel.py) on every model in models/, and the public API must behave as
 * documented. The fixture is frozen Python output: uv run bench/fixtures.py
 */
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";
import { gated, parseJewel, rawScore, score, type Jewel } from "../runtime/jewel";

const ROOT = new URL("..", import.meta.url);
const fixture = JSON.parse(readFileSync(new URL("test/fixtures/parity.json", ROOT), "utf8")) as {
  models: string[];
  rows: { text: string; gated: boolean; scores: Record<string, number> }[];
};
const modelFiles = readdirSync(new URL("models/", ROOT)).filter((f) => /^jeweler-v\d+\.json$/.test(f));
const models = new Map<string, Jewel>(
  modelFiles.map((f) => {
    const m = parseJewel(JSON.parse(readFileSync(new URL(`models/${f}`, ROOT), "utf8")));
    return [String(m.version), m];
  }),
);
const newest = [...models.values()].sort((a, b) => b.version - a.version)[0];
/** Masked shape for failure messages: a/A/9, symbols kept. */
const mask = (t: string) => JSON.stringify(t.replace(/[a-z]/g, "a").replace(/[A-Z]/g, "A").replace(/[0-9]/g, "9"));

test("the fixture covers every model", () => {
  assert.deepEqual([...models.keys()].sort(), [...fixture.models].sort(), "re-run: uv run bench/fixtures.py");
});

test("gate matches Python on every fixture text", () => {
  const wrong = fixture.rows.filter((r) => gated(r.text) !== r.gated).map((r) => `${mask(r.text)} python=${r.gated}`);
  assert.deepEqual(wrong, []);
});

for (const [version, model] of models) {
  test(`model v${version}: scores match Python within 1e-9, no decision flips`, () => {
    let worst = 0;
    const flips: string[] = [];
    for (const r of fixture.rows) {
      const py = r.scores[version];
      const ts = rawScore(model, r.text);
      worst = Math.max(worst, Math.abs(ts - py));
      if (ts >= model.threshold !== py >= model.threshold) flips.push(mask(r.text));
    }
    assert.ok(worst < 1e-9, `largest difference ${worst}`);
    assert.deepEqual(flips, []);
  });

  test(`model v${version}: score is null off the gate and 0-1 on it`, () => {
    for (const r of fixture.rows) {
      const s = score(model, r.text);
      if (!gated(r.text)) assert.equal(s, null, mask(r.text));
      else assert.ok(s !== null && s >= 0 && s <= 1 && Number.isFinite(s), mask(r.text));
    }
  });
}

test("gate: lengths, whitespace, links, paths, emails, numbers, file names", () => {
  assert.equal(gated("Ab3defg"), false); // 7
  assert.equal(gated("Ab3defgh"), true); // 8
  assert.equal(gated("A" + "b".repeat(63)), true); // 64
  assert.equal(gated("A" + "b".repeat(64)), false); // 65
  assert.equal(gated("  Ab3defgh \n"), true); // trimmed first
  assert.equal(gated("two words!"), false);
  assert.equal(gated("https://example.com"), false);
  assert.equal(gated("ssh://host/x"), false);
  assert.equal(gated("/etc/hosts1"), false);
  assert.equal(gated("someone@example.com"), false);
  assert.equal(gated("1234567890"), false);
  assert.equal(gated("report.json"), false);
  assert.equal(gated("😀😀😀😀😀😀😀😀a"), true); // counted in code points, like Python
});

test("score is deterministic and the model is not mutated", () => {
  const m = newest;
  const before = JSON.stringify(m);
  const a = score(m, "kal73mor!Qx");
  const b = score(m, "kal73mor!Qx");
  assert.equal(a, b);
  assert.equal(JSON.stringify(m), before);
});

test("parseJewel rejects things that are not a model", () => {
  const good = newest;
  assert.throws(() => parseJewel(null), TypeError);
  assert.throws(() => parseJewel({}), TypeError);
  assert.throws(() => parseJewel({ ...good, weights: [] }), TypeError);
  assert.throws(() => parseJewel({ ...good, bias: "0" }), TypeError);
  assert.throws(() => parseJewel({ ...good, dim: 0 }), TypeError);
  assert.throws(() => parseJewel({ ...good, features: { ...good.features!, char_n: -1 } }), TypeError);
  assert.equal(parseJewel(good), good);
});

test("hostile input stays linear: megabytes of whitespace or one huge token", () => {
  const m = newest;
  for (const t of ["a" + " ".repeat(2_000_000) + "a", " ".repeat(1_000_000) + "Kal73mor!Qx" + "\n".repeat(1_000_000), "x".repeat(5_000_000)]) {
    const t0 = performance.now();
    score(m, t);
    rawScore(m, t);
    const ms = performance.now() - t0;
    assert.ok(ms < 1000, `${ms.toFixed(0)} ms on ${t.length.toLocaleString()} characters`);
  }
});

test("jeweler: score(text) uses the newest model; another model can be passed in", async () => {
  const lib = await import("../runtime/index");
  assert.equal(lib.model.version, newest.version, "runtime/model.js must point at the newest models/jeweler-v<n>.json");
  assert.equal(lib.threshold, newest.threshold);
  for (const r of fixture.rows) {
    assert.equal(lib.score(r.text), score(newest, r.text), mask(r.text));
    assert.equal(lib.rawScore(r.text), rawScore(newest, r.text), mask(r.text));
  }
  const older: Jewel = { ...newest, bias: newest.bias - 2 }; // stands in for another model JSON
  assert.equal(lib.score("kal73mor!Qx", older), score(older, "kal73mor!Qx"));
  assert.equal(lib.score(older, "kal73mor!Qx"), score(older, "kal73mor!Qx"));
  assert.notEqual(lib.score("kal73mor!Qx", older), lib.score("kal73mor!Qx"));
  assert.equal(lib.score("two words"), null);
});

test("non-string input: score is null, gated is false, rawScore says what's wrong", async () => {
  const lib = await import("../runtime/index");
  for (const bad of [null, undefined, 12345678, {}, ["Summer2026!"]] as unknown[]) {
    assert.equal(lib.score(bad as string), null);
    assert.equal(lib.gated(bad as string), false);
    assert.equal(gated(bad as string), false);
  }
  assert.throws(() => lib.rawScore(null as unknown as string), /text must be a string, got null/);
  assert.throws(() => lib.rawScore(newest, undefined as unknown as string), /text must be a string, got undefined/);
  assert.throws(() => lib.score("Summer2026!", 5 as unknown as Jewel), /must be a model/);
  assert.equal(lib.score(newest, null as unknown as string), null);
});

test("the built-in model is frozen", async () => {
  const lib = await import("../runtime/index");
  assert.ok(Object.isFrozen(lib.model) && Object.isFrozen(lib.model.weights) && Object.isFrozen(lib.model.features));
  assert.throws(() => { (lib.model as { threshold: number }).threshold = 0; }, TypeError);
  assert.throws(() => { (lib.model.weights as Record<string, number>)["4"] = 99; }, TypeError);
  assert.equal(lib.threshold, newest.threshold);
});
