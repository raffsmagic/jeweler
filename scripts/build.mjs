// Builds the published package into dist/: the runtime (tsc) and the newest models/jeweler-v<n>.json
// as the built-in model (dist/model.js) plus the raw JSON (jeweler/model.json).
import { execFileSync } from "node:child_process";
import { copyFileSync, readdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { createRequire } from "node:module";

const root = new URL("..", import.meta.url);
/** @param {string} p */
const at = (p) => new URL(p, root);
rmSync(at("dist"), { recursive: true, force: true });
const tsc = createRequire(import.meta.url).resolve("typescript/bin/tsc");
execFileSync(process.execPath, [tsc, "-p", "tsconfig.build.json"], { cwd: root, stdio: "inherit" });

const version = (/** @type {string} */ f) => Number(/^jeweler-v(\d+)\.json$/.exec(f)?.[1] ?? NaN);
const newest = readdirSync(at("models")).filter((f) => version(f) > 0).sort((a, b) => version(a) - version(b)).at(-1);
if (!newest) throw new Error("no models/jeweler-v<n>.json");
const json = JSON.stringify(JSON.parse(readFileSync(at(`models/${newest}`), "utf8")));
copyFileSync(at(`models/${newest}`), at("dist/model.json"));
// JSON.parse of a string literal loads faster than an object literal this size.
writeFileSync(at("dist/model.js"), `/** The built-in model, generated from models/${newest} by scripts/build.mjs. */\nexport default JSON.parse(${JSON.stringify(json)});\n`);
copyFileSync(at("runtime/model.d.ts"), at("dist/model.d.ts"));
console.log(`built dist/ with model ${newest}`);
