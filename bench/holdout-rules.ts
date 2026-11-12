/**
 * The rules' verdicts for holdout.py, so Python can compare without porting them.
 * Writes out/holdout-rules.json: booleans for the fresh set (regenerated in Python,
 * so passed in via out/holdout-fresh.jsonl when present) and, for the local the app
 * databases, only the ids of items the rules would lock. No copied text is written.
 */

import { execFileSync } from "node:child_process";
import { existsSync, readFileSync, writeFileSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";
import { detectSecret } from "../rules/baseline-rules";

const OUT = join(import.meta.dirname, "out");
const freshFile = join(OUT, "holdout-fresh.jsonl");
const fresh = existsSync(freshFile)
  ? readFileSync(freshFile, "utf8").trim().split("\n").map((l) => !!detectSecret((JSON.parse(l) as { text: string }).text))
  : [];

const history: string[] = [];
const historyFile = process.env.JEWEL_HISTORY_JSONL;
if (historyFile && existsSync(historyFile)) {
  const lines = readFileSync(historyFile, "utf8").split("\n").filter((l) => l.trim());
  lines.forEach((l, i) => {
    const r = JSON.parse(l) as { text?: string; sensitive?: boolean };
    if (r.text && !r.sensitive && detectSecret(r.text)) history.push(`h:${i}`);
  });
}
writeFileSync(join(OUT, "holdout-rules.json"), JSON.stringify({ fresh, history }));
console.log(`fresh ${fresh.filter(Boolean).length}/${fresh.length} locked by rules; history ${history.length} unlocked items the rules would lock`);
