/**
 * Passwords in the wild: how many real human passwords do the rules and the
 * shipped model catch? Streams a public leaked-password list through the
 * checkers in memory. Nothing is written to disk and no password is printed:
 * only counts and masked shapes (a = lower, A = upper, 9 = digit).
 *
 *   npx tsx bench/leaked.ts [url] [model.json]
 *
 * Default list: the 000webhost unique-password list as redistributed in
 * SecLists (720,302 lines). Only the gate's range (one token, 8-64 chars, has a
 * letter) is judged, since that's what the model sees in the app; the rest is
 * counted and skipped. Every 200th line by CRC32 is also marked as the
 * "sample" so bench/leaked.py can judge exactly the same subset with the
 * Python-only checkers (credline, CredSweeper).
 */
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { detectSecret } from "../rules/baseline-rules";
import { gated, rawScore, type Jewel } from "../runtime/jewel";

const URL_ = process.argv[2] ?? "https://raw.githubusercontent.com/danielmiessler/SecLists/master/Passwords/Leaked-Databases/000webhost.txt";
const MODEL = JSON.parse(readFileSync(process.argv[3] ?? join(import.meta.dirname, "..", "models", "jeweler-v1.json"), "utf8")) as Jewel;
export const SAMPLE_EVERY = 200;

const CRC = (() => { const t = new Uint32Array(256); for (let n = 0; n < 256; n++) { let c = n; for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1; t[n] = c >>> 0; } return t; })();
export function crc32(s: string): number { let c = 0xffffffff; for (const b of new TextEncoder().encode(s)) c = CRC[(c ^ b) & 0xff] ^ (c >>> 8); return (c ^ 0xffffffff) >>> 0; }
export const inSample = (line: string) => crc32(line) % SAMPLE_EVERY === 0;

const shape = (t: string) => t.replace(/[a-z]/g, "a").replace(/[A-Z]/g, "A").replace(/[0-9]/g, "9");
/** Coarse structure, the way password-cracking mask statistics group them. */
function bucket(t: string): string {
  const lower = /[a-z]/.test(t), upper = /[A-Z]/.test(t), digit = /[0-9]/.test(t), sym = /[^A-Za-z0-9]/.test(t);
  if (sym) return "has symbol";
  if (/^[a-z]+[0-9]+$/.test(t)) return "lower+digits";
  if (/^[A-Z][a-z]+[0-9]+$/.test(t)) return "Word+digits";
  if (/^[0-9]+[a-z]+$/.test(t)) return "digits+lower";
  if (lower && !upper && !digit) return "lower only";
  if (lower && upper && digit) return "mixed case+digits";
  if (lower && upper) return "mixed case";
  if (lower && digit) return "lower,digits mixed";
  if (upper && digit) return "UPPER+digits";
  if (upper) return "UPPER only";
  return "other";
}

async function main() {
  const res = await fetch(URL_);
  if (!res.ok || !res.body) throw new Error(`fetch failed: ${res.status}`);
  const reader = res.body.pipeThrough(new TextDecoderStream()).getReader();
  let total = 0, judged = 0, rule = 0, model = 0, either = 0, sampled = 0, sampleEither = 0;
  const byBucket = new Map<string, { n: number; rule: number; model: number; either: number }>();
  const byLen = new Map<number, { n: number; either: number }>();
  const missShapes = new Map<string, number>();
  const scores: number[] = [];
  let carry = "";
  const handle = (line: string) => {
    total++;
    if (!gated(line)) return;
    const t = line.trim();
    judged++;
    const r = detectSecret(t) !== null;
    const s = rawScore(MODEL, t);
    const m = s >= MODEL.threshold;
    rule += +r; model += +m; either += +(r || m);
    scores.push(s);
    const b = byBucket.get(bucket(t)) ?? { n: 0, rule: 0, model: 0, either: 0 };
    b.n++; b.rule += +r; b.model += +m; b.either += +(r || m); byBucket.set(bucket(t), b);
    const L = Math.min(t.length, 20); const l = byLen.get(L) ?? { n: 0, either: 0 }; l.n++; l.either += +(r || m); byLen.set(L, l);
    if (!(r || m)) missShapes.set(shape(t), (missShapes.get(shape(t)) ?? 0) + 1);
    if (inSample(line)) { sampled++; sampleEither += +(r || m); }
  };
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    const parts = (carry + value).split("\n");
    carry = parts.pop() ?? "";
    for (const p of parts) handle(p.replace(/\r$/, ""));
  }
  if (carry) handle(carry);
  const pct = (a: number, b: number) => (b ? ((100 * a) / b).toFixed(1) + "%" : "-");
  console.log(`# Passwords in the wild (${new Date().toISOString().slice(0, 10)})\n`);
  console.log(`Source: ${URL_}\nModel: Jewel ${MODEL.version} at threshold ${MODEL.threshold}. Streamed in memory; nothing written, no password printed.\n`);
  console.log(`${total.toLocaleString()} lines; ${judged.toLocaleString()} pass the gate (one token, 8-64 chars, has a letter) and are judged.\n`);
  console.log(`| Checker | Caught of ${judged.toLocaleString()} | Share |\n| - | - | - |`);
  console.log(`| rules | ${rule.toLocaleString()} | ${pct(rule, judged)} |\n| Jewel ${MODEL.version} | ${model.toLocaleString()} | ${pct(model, judged)} |\n| rules + model | ${either.toLocaleString()} | ${pct(either, judged)} |\n`);
  console.log(`Sample (every ${SAMPLE_EVERY}th line by CRC32, for bench/leaked.py): ${sampled} judged, rules + model catch ${sampleEither} (${pct(sampleEither, sampled)}).\n`);
  console.log(`## By structure\n\n| Structure | Judged | rules | model | either |\n| - | - | - | - | - |`);
  for (const [k, v] of [...byBucket].sort((a, b) => b[1].n - a[1].n)) console.log(`| ${k} | ${v.n.toLocaleString()} | ${pct(v.rule, v.n)} | ${pct(v.model, v.n)} | ${pct(v.either, v.n)} |`);
  console.log(`\n## By length (20 = 20 or more)\n\n| Length | Judged | either |\n| - | - | - |`);
  for (const [k, v] of [...byLen].sort((a, b) => a[0] - b[0])) console.log(`| ${k} | ${v.n.toLocaleString()} | ${pct(v.either, v.n)} |`);
  console.log(`\n## Most common shapes among misses (masked)\n\n| Shape | Misses |\n| - | - |`);
  for (const [k, v] of [...missShapes].sort((a, b) => b[1] - a[1]).slice(0, 15)) console.log(`| \`${k}\` | ${v.toLocaleString()} |`);
  scores.sort((a, b) => a - b);
  const q = (p: number) => scores[Math.floor(p * (scores.length - 1))].toFixed(2);
  console.log(`\nModel score quartiles over judged lines: p10 ${q(0.1)}, p25 ${q(0.25)}, p50 ${q(0.5)}, p75 ${q(0.75)}, p90 ${q(0.9)}. At threshold 0.3 the model alone would catch ${pct(scores.filter((s) => s >= 0.3).length, judged)}, at 0.7 ${pct(scores.filter((s) => s >= 0.7).length, judged)}.`);
}

main().catch((e) => { console.error(e); process.exit(1); });
