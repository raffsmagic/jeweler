/**
 * Checks that runtime/jewel.ts scores exactly like Python (bench/export.py)
 * for every text in bench/out/parity.jsonl. Run before shipping a model:
 *   uv run bench/export.py 2 && npx tsx runtime/parity.ts models/jeweler-v2.json
 */
import { readFileSync } from "node:fs";
import { rawScore, type Jewel } from "./jewel";

const model = JSON.parse(readFileSync(process.argv[2] ?? "models/jeweler-v1.json", "utf8")) as Jewel;
const rows = readFileSync("bench/out/parity.jsonl", "utf8").trim().split("\n").map((l) => JSON.parse(l) as { text: string; score: number });
let worst = 0;
let flips = 0;
for (const r of rows) {
  const s = rawScore(model, r.text);
  worst = Math.max(worst, Math.abs(s - r.score));
  if (s >= model.threshold !== r.score >= model.threshold) flips++;
}
console.log(`${rows.length} texts: largest difference ${worst.toExponential(2)}, decisions that differ: ${flips}`);
if (worst > 1e-6 || flips) process.exit(1);
