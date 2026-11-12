/**
 * the baseline rules as a filter for Python: reads a JSON array of texts on stdin,
 * prints a JSON array of booleans (true = the rules lock it). Nothing touches
 * disk, so bench/loop.py can ask about in-memory samples of real passwords.
 *   echo '["Summer2026!","hello"]' | npx tsx bench/rules-stdin.ts
 */
import { readFileSync } from "node:fs";
import { detectSecret } from "../rules/baseline-rules";

const texts = JSON.parse(readFileSync(0, "utf8")) as string[];
process.stdout.write(JSON.stringify(texts.map((t) => detectSecret(t) !== null)));
