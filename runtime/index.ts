/**
 * jeweler: is this copied text a password, key or code? Everything runs on the device.
 *
 *   import { score, threshold } from "jeweler";
 *   const s = score(text);              // 0-1, or null when the text isn't the kind Jewel judges
 *   if (s !== null && s >= threshold) hide(text);
 *
 * `score` uses the model built in (`model.version`). To try another model JSON, for example a
 * newer version from Hugging Face, pass it: score(text, parseJewel(json)). Anything that isn't a
 * string (null from a clipboard or form API, say) scores null.
 */
import latest from "./model.js";
import { gated, parseJewel, rawScore as rawScoreWith, score as scoreWith, type Jewel, type JewelFeatures } from "./jewel.js";

export { gated, parseJewel };
export type { Jewel, JewelFeatures };

// Frozen, so no caller can change the threshold or weights for everyone else in the process.
Object.freeze(latest.weights);
if (latest.features) Object.freeze(latest.features);
Object.freeze(latest);

/** The built-in model `score` uses; `model.version` is its version (v1, v2, ...). Read-only. */
export const model: Jewel = latest;
/** The threshold the default model was tested at. Your app may pick its own. */
export const threshold: number = latest.threshold;

/**
 * How likely the text is a password, key or code: 0-1, or null when the gate skips it
 * (more than one word, under 8 or over 64 characters, a link, path, email, plain number or file name).
 */
export function score(text: string, model?: Jewel): number | null;
/** The older form, kept so code written against runtime/jewel.ts keeps working. */
export function score(model: Jewel, text: string): number | null;
export function score(a: string | Jewel, b?: string | Jewel): number | null {
  if (typeof a === "string") return scoreWith(pick(b), a);
  if (isModel(a)) return scoreWith(a, b as string);
  return null; // null, undefined, a number...: not text, so nothing to judge
}

/** Like `score`, but ignores the gate. For tools and tests. */
export function rawScore(text: string, model?: Jewel): number;
export function rawScore(model: Jewel, text: string): number;
export function rawScore(a: string | Jewel, b?: string | Jewel): number {
  if (typeof a === "string") return rawScoreWith(pick(b), a);
  if (isModel(a)) return rawScoreWith(a, b as string);
  throw new TypeError(`jeweler: text must be a string, got ${a === null ? "null" : typeof a}`);
}

function isModel(m: unknown): m is Jewel {
  return typeof m === "object" && m !== null && "weights" in m;
}

/** The model to use: the built-in one, or one the caller passed. */
function pick(m: unknown): Jewel {
  if (m === undefined) return latest;
  if (isModel(m)) return m;
  throw new TypeError("jeweler: the second argument must be a model (load one with parseJewel) or left out");
}
