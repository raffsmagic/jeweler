/**
 * Jewel, runtime. Scores how likely a copied text is a password or key, on the
 * device, in well under a millisecond, for any model JSON. The package's entry
 * point (runtime/index.ts) adds the built-in model. No dependencies; needs only TextEncoder.
 *
 * Jewel answers with a number, not a verdict: `score` is 0-1 (null when the
 * gate says this isn't the kind of text Jewel judges). What to do at what
 * threshold is the app's call: a typical app flags a text at `jewel.threshold`;
 * another app might warn, blur or refuse to sync.
 *
 * `features` must compute exactly what bench/jewel.py's `features` does;
 * runtime/parity.ts checks that against Python's scores before a model ships.
 */

/** How the text becomes features. Absent in Jewel 1's file, which used these defaults. */
export interface JewelFeatures {
  /** Longest character n-gram of the lowercased text. */
  char_n: number;
  /** Longest n-gram of the shape (a = lower, A = upper, 9 = digit, symbols kept). */
  shape_n: number;
  /** Wrap the text in ^ and $ so "starts with a digit" is a feature. */
  boundary: boolean;
  /** Length, entropy, character classes, word count, spaces. */
  dense: boolean;
  /** Hash buckets. */
  dim: number;
  /** The whole shape collapsed into runs (Thursday2026 -> Aa9, kal73mor -> a9a) as one more gram. Absent in Jewel 1. */
  runs?: boolean;
}
export const JEWEL_1_FEATURES: JewelFeatures = { char_n: 4, shape_n: 6, boundary: false, dense: true, dim: 32768 };

export interface Jewel {
  /** Model version: 1, 2, ... (models/jeweler-v<n>.json; v1 is the research notes' Jewel 3). */
  version: number;
  created?: string;
  features?: JewelFeatures;
  dim: number;
  bias: number;
  /** The threshold the model was evaluated at; apps may pick their own. */
  threshold: number;
  /** Hashed feature index → weight; only non-zero weights. */
  weights: Record<string, number>;
}

const CRC_TABLE = (() => {
  const t = new Uint32Array(256);
  for (let n = 0; n < 256; n++) {
    let c = n;
    for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
    t[n] = c >>> 0;
  }
  return t;
})();
const encoder = new TextEncoder();

/** zlib.crc32 of the UTF-8 bytes, as Python computes it. */
function crc32(s: string): number {
  let c = 0xffffffff;
  for (const b of encoder.encode(s)) c = CRC_TABLE[(c ^ b) & 0xff] ^ (c >>> 8);
  return (c ^ 0xffffffff) >>> 0;
}

const shape = (t: string) => t.replace(/[a-z]/g, "a").replace(/[A-Z]/g, "A").replace(/[0-9]/g, "9");

function entropy(chars: string[]): number {
  if (!chars.length) return 0;
  const counts = new Map<string, number>();
  for (const c of chars) counts.set(c, (counts.get(c) ?? 0) + 1);
  let h = 0;
  for (const n of counts.values()) h -= (n / chars.length) * Math.log2(n / chars.length);
  return h;
}

/**
 * Python's whitespace (str.isspace, and \s in its str regexes), which is not JavaScript's \s:
 * Python adds U+001C-U+001F and U+0085, JavaScript adds U+FEFF (the byte-order mark).
 */
const WS = "\\t\\n\\v\\f\\r\\x1c-\\x20\\x85\\xa0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000";
const WS_ANY = new RegExp(`[${WS}]`);
const WS_RUN = new RegExp(`[${WS}]+`);
const SYMBOL = new RegExp(`[^A-Za-z0-9${WS}]`);
const WS_ONE = new RegExp(`[${WS}]`);
/** Python's str.strip(): whitespace at both ends. A loop, not a regex: /\s+$/ is quadratic on long inner whitespace runs. */
function pyStrip(s: string): string {
  let a = 0;
  let b = s.length;
  while (a < b && WS_ONE.test(s[a])) a++;
  while (b > a && WS_ONE.test(s[b - 1])) b--;
  return a === 0 && b === s.length ? s : s.slice(a, b);
}
/** The first `max` code points of s, like Python's s[:max]. */
function firstCodePoints(s: string, max: number): string {
  let n = 0;
  let end = 0;
  for (const ch of s) {
    if (n++ === max) break;
    end += ch.length;
  }
  return s.slice(0, end);
}
/** Code points in s, counting at most to `max + 1`. */
function codePoints(s: string, max: number): number {
  let n = 0;
  for (const _ of s) if (++n > max) break;
  return n;
}
/** Python's re.fullmatch(r"[\w.+-]+@[\w-]+\.[\w.]+"), where \w is any letter, digit or underscore in Unicode. */
const EMAIL = /^[\p{L}\p{N}_.+-]+@[\p{L}\p{N}_-]+\.[\p{L}\p{N}_.]+$/u;

function features(text: string, cfg: JewelFeatures): Map<number, number> {
  const dim = cfg.dim;
  const t = firstCodePoints(pyStrip(text), 256);
  const f = new Map<number, number>();
  const add = (k: number, v: number) => f.set(k, (f.get(k) ?? 0) + v);
  const grams = (s: string, prefix: string, max: number) => {
    const cs = Array.from(s);
    for (let n = 1; n <= max; n++) for (let i = 0; i + n <= cs.length; i++) add(crc32(prefix + cs.slice(i, i + n).join("")) % dim, 1);
  };
  const wrap = (s: string) => (cfg.boundary ? "^" + s + "$" : s);
  grams(wrap(t.toLowerCase()), "c", cfg.char_n);
  grams(wrap(shape(t)), "s", cfg.shape_n);
  if (cfg.runs) {
    // The whole shape collapsed into runs (Thursday2026 -> Aa9), at most 16, as one more gram.
    const runs: string[] = [];
    for (const ch of Array.from(shape(t))) if (!runs.length || runs[runs.length - 1] !== ch) runs.push(ch);
    add(crc32("r" + runs.slice(0, 16).join("")) % dim, 1);
  }
  let norm = 0;
  for (const v of f.values()) norm += v * v;
  norm = Math.sqrt(norm) || 1;
  for (const [k, v] of f) f.set(k, v / norm);
  if (cfg.dense) {
    const chars = Array.from(t);
    const classes = [/[a-z]/, /[A-Z]/, /[0-9]/, SYMBOL].filter((re) => re.test(t)).length;
    const words = t.split(WS_RUN).filter(Boolean).length;
    const dense: [string, number][] = [
      ["len", Math.min(chars.length, 128) / 128],
      ["entropy", entropy(chars) / 6],
      ["classes", classes / 4],
      ["words", Math.min(words, 20) / 20],
      ["spaces", WS_ANY.test(t) ? 1 : 0],
    ];
    for (const [name, v] of dense) add(crc32("d" + name) % dim, v);
  }
  return f;
}

/**
 * The gate: Jewel only judges what could be a typed or generated password, one
 * token of 8-64 characters that isn't a link, path, email, plain number or file
 * name. Everything else is for the app's rules.
 */
export function gated(text: string): boolean {
  if (typeof text !== "string") return false;
  const t = pyStrip(text);
  const n = codePoints(t, 64);
  if (n < 8 || n > 64 || WS_ANY.test(t) || /^(https?:\/\/|www\.|\/|~\/)/i.test(t) || t.includes("://")) return false;
  if (EMAIL.test(t) || !/[A-Za-z]/.test(t)) return false;
  return !/\.[A-Za-z][A-Za-z0-9]{1,4}$/.test(t);
}

/**
 * Checks that a parsed model JSON (from a fetch, an asset bundle, a file) is a
 * Jewel this runtime can score, and returns it typed. Throws a TypeError naming
 * the first problem. The built-in model is already valid.
 */
export function parseJewel(json: unknown): Jewel {
  const fail = (why: string): never => {
    throw new TypeError(`Not a Jewel model: ${why}`);
  };
  const isObj = (v: unknown): v is Record<string, unknown> => typeof v === "object" && v !== null && !Array.isArray(v);
  const posInt = (v: unknown) => Number.isInteger(v) && (v as number) > 0;
  if (!isObj(json)) return fail("expected an object");
  if (!posInt(json.version)) fail("version must be a positive integer");
  if (!posInt(json.dim)) fail("dim must be a positive integer");
  if (typeof json.bias !== "number" || !Number.isFinite(json.bias)) fail("bias must be a finite number");
  if (typeof json.threshold !== "number" || !(json.threshold >= 0 && json.threshold <= 1)) fail("threshold must be 0-1");
  if (!isObj(json.weights)) fail("weights must be an object of index → weight");
  for (const [k, v] of Object.entries(json.weights as Record<string, unknown>)) {
    if (!/^\d+$/.test(k) || Number(k) >= (json.dim as number)) fail(`weight index ${k} outside 0-${(json.dim as number) - 1}`);
    if (typeof v !== "number" || !Number.isFinite(v)) fail(`weight ${k} must be a finite number`);
  }
  if (json.features !== undefined) {
    const f = json.features;
    if (!isObj(f)) return fail("features must be an object");
    if (!posInt(f.char_n) || !posInt(f.shape_n)) fail("features.char_n and features.shape_n must be positive integers");
    if (typeof f.boundary !== "boolean" || typeof f.dense !== "boolean") fail("features.boundary and features.dense must be booleans");
    if (f.dim !== json.dim) fail("features.dim must equal dim");
    if (f.runs !== undefined && typeof f.runs !== "boolean") fail("features.runs must be a boolean");
  }
  return json as unknown as Jewel;
}

/** Probability (0-1) that the text is a password or key, ignoring the gate. For parity checks and tools. */
export function rawScore(jewel: Jewel, text: string): number {
  if (typeof text !== "string") throw new TypeError(`jeweler: text must be a string, got ${text === null ? "null" : typeof text}`);
  let z = jewel.bias;
  for (const [k, v] of features(text, jewel.features ?? { ...JEWEL_1_FEATURES, dim: jewel.dim })) z += (jewel.weights[k] ?? 0) * v;
  return 1 / (1 + Math.exp(-z));
}

/** Jewel's answer: 0-1 when the text is something Jewel judges, null when the gate skips it. */
export function score(jewel: Jewel, text: string): number | null {
  return gated(text) ? rawScore(jewel, text) : null;
}
