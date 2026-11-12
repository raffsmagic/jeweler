// Packs the library the way npm would publish it, installs the tarball into a throwaway
// project, and checks that a consumer can import it (Node ESM) and typecheck against it
// (moduleResolution NodeNext and Bundler). Run after `npm run build`: npm run test:pack
import { execFileSync } from "node:child_process";
import { mkdtempSync, readdirSync, rmSync, writeFileSync } from "node:fs";
import { createRequire } from "node:module";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

const root = fileURLToPath(new URL("..", import.meta.url));
const dir = mkdtempSync(join(process.env.TMPDIR ?? tmpdir(), "jewel-pack-"));
/** @param {string} cmd @param {string[]} args @param {string} cwd */
const run = (cmd, args, cwd) => execFileSync(cmd, args, { cwd, encoding: "utf8", stdio: ["ignore", "pipe", "inherit"] });
try {
  const out = JSON.parse(run("npm", ["pack", "--json", "--ignore-scripts", "--pack-destination", dir], root));
  const packed = Array.isArray(out) ? out[0] : Object.values(out)[0]; // npm <12: [..]; npm 12: { name: .. }
  const files = packed.files.map((/** @type {{path: string}} */ f) => f.path).sort();
  console.log(`packed ${packed.filename}: ${files.length} files, ${(packed.size / 1e3).toFixed(0)} KB`);
  const stray = files.filter((/** @type {string} */ f) => !/^(dist\/|package\.json$|README\.md$|LICENSE$|CHANGELOG\.md$|SECURITY\.md$)/.test(f));
  if (stray.length) throw new Error(`unexpected files in the package: ${stray.join(", ")}`);

  const app = join(dir, "app");
  run("mkdir", ["-p", app], dir);
  writeFileSync(join(app, "package.json"), JSON.stringify({ name: "app", private: true, type: "module" }));
  run("npm", ["install", "--no-audit", "--no-fund", "--offline", join(dir, packed.filename)], app);

  writeFileSync(join(app, "smoke.mjs"), `
import { score, gated, rawScore, parseJewel, threshold, model } from "jeweler";
import { createRequire } from "node:module";
const raw = createRequire(import.meta.url)("jeweler/model.json");
if (parseJewel(raw).version !== model.version || raw.weights["4"] !== model.weights["4"]) throw new Error("raw JSON and built-in model differ");
const s = score("kal73mor!Qx");
if (typeof s !== "number" || s < 0 || s > 1 || threshold !== model.threshold) throw new Error("built-in model");
if (score("hello world") !== null) throw new Error("gate should skip two words");
if (score("kal73mor!Qx", parseJewel(raw)) !== s) throw new Error("passing a model");
if (!gated("Thursday2026") || typeof rawScore("x") !== "number") throw new Error("api");
console.log("node import ok");
`);
  console.log(run(process.execPath, ["smoke.mjs"], app).trim());

  writeFileSync(join(app, "consumer.ts"), `
import { score, threshold, model, parseJewel, type Jewel } from "jeweler";
const s: number | null = score("Thursday2026");
const locked: boolean = s !== null && s >= threshold;
const other: Jewel = parseJewel(JSON.parse(JSON.stringify(model)));
const again: number | null = score("Thursday2026", other);
const v: number = model.version;
export { locked, again, v };
`);
  const tsc = createRequire(import.meta.url).resolve("typescript/bin/tsc");
  for (const [mod, res] of [["NodeNext", "NodeNext"], ["ESNext", "Bundler"]]) {
    run(process.execPath, [tsc, "--noEmit", "--strict", "--skipLibCheck", "false", "--target", "ES2022", "--lib", "ES2022,DOM", "--module", mod, "--moduleResolution", res, "consumer.ts"], app);
    console.log(`typecheck ok (${res})`);
  }
} finally {
  rmSync(dir, { recursive: true, force: true });
}
