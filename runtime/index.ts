/**
 * jeweler: is this copied text a password, key or code? Everything runs on the device.
 *
 *   import { score, threshold } from "jeweler";
 *   const s = score(text);              // 0-1, or null when the text isn't the kind Jewel judges
 *   if (s !== null && s >= threshold) hide(text);
 *
 * `score` uses the model built in (`model.version`). To try another model JSON, for example a
 * newer version from Hugging Face, pass it: score(text, parseJewel(json)).
 */
import latest from "./model.js";
import { gated, parseJewel, rawScore as rawScoreWith, score as scoreWith, type Jewel, type JewelFeatures } from "./jewel.js";

export { gated, parseJewel };
export type { Jewel, JewelFeatures };

/** The built-in model `score` uses; `model.version` is its version (v1, v2, ...). */
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
  return typeof a === "string" ? scoreWith((b as Jewel | undefined) ?? latest, a) : scoreWith(a, b as string);
}

/** Like `score`, but ignores the gate. For tools and tests. */
export function rawScore(text: string, model?: Jewel): number;
export function rawScore(model: Jewel, text: string): number;
export function rawScore(a: string | Jewel, b?: string | Jewel): number {
  return typeof a === "string" ? rawScoreWith((b as Jewel | undefined) ?? latest, a) : rawScoreWith(a, b as string);
}
