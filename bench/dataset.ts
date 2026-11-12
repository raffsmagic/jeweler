/**
 * The benchmark set for "should the app lock this copy?" (passwords, keys,
 * tokens, card numbers, codes). Every value is generated here from a fixed
 * seed: nothing real, nothing committed. Positives cover the shapes the app must
 * lock; negatives are the look-alikes and everyday copies it must leave alone.
 *
 * Provider prefixes are assembled at run time so the source file itself
 * doesn't look like a leaked key to scanners.
 */

export interface Case {
  id: string;
  text: string;
  /** True when the app should lock it. */
  locked: boolean;
  /** Group for per-kind catch and false-alarm rates. */
  kind: string;
}

/** Small deterministic PRNG (mulberry32) so every run sees the same set. */
function rng(seed: number) {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

const LOWER = "abcdefghijklmnopqrstuvwxyz";
const UPPER = LOWER.toUpperCase();
const DIGITS = "0123456789";
const SYMBOLS = "!@#$%^&*-_=+?";
const HEX = "0123456789abcdef";
const B58 = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz";
const B64URL = LOWER + UPPER + DIGITS + "-_";
const WORDS = ["river", "maple", "orbit", "lantern", "copper", "violet", "summit", "pickle", "harbor", "tiger", "nova", "basil", "falcon", "cedar", "ember", "quartz", "willow", "comet", "saffron", "otter"];
const SEED_WORDS = ["abandon", "ability", "able", "about", "above", "absent", "absorb", "abstract", "absurd", "abuse", "access", "accident", "account", "accuse", "achieve", "acid", "acoustic", "acquire", "across", "act", "action", "actor", "actress", "actual"];

export function buildDataset(seed = 20261004): Case[] {
  const r = rng(seed);
  const pick = <T,>(xs: readonly T[] | string): T => xs[Math.floor(r() * xs.length)] as T;
  const str = (alphabet: string, n: number) => Array.from({ length: n }, () => pick<string>(alphabet)).join("");
  const word = () => pick(WORDS);
  const cap = (w: string) => w[0].toUpperCase() + w.slice(1);
  const cases: Case[] = [];
  const add = (kind: string, locked: boolean, make: () => string, n: number) => {
    for (let i = 0; i < n; i++) cases.push({ id: `${kind}-${i + 1}`, text: make(), locked, kind });
  };
  const generated = (n: number) => {
    // At least one of each class, then shuffle.
    const chars = [pick<string>(LOWER), pick<string>(UPPER), pick<string>(DIGITS), pick<string>(SYMBOLS), ...str(LOWER + UPPER + DIGITS + SYMBOLS, n - 4)];
    for (let i = chars.length - 1; i > 0; i--) {
      const j = Math.floor(r() * (i + 1));
      [chars[i], chars[j]] = [chars[j], chars[i]];
    }
    return chars.join("");
  };
  const P = (...parts: string[]) => parts.join("");

  // ---- Should lock -----------------------------------------------------------
  add("generated_password", true, () => generated(8 + Math.floor(r() * 25)), 40);
  add("typed_password", true, () => pick([
    () => `${cap(word())}${2000 + Math.floor(r() * 30)}${pick<string>("!@#$")}`,
    () => `${word()}${pick<string>("@#$&")}${word()}${Math.floor(r() * 100)}`,
    () => `${cap(word())}${pick<string>(".!_")}${cap(word())}${Math.floor(r() * 10)}`,
    () => `P${pick<string>("@a")}ssw0rd${pick<string>("!1#")}`,
    () => `${word()}${word()}${Math.floor(r() * 1000)}`,
  ])(), 30);
  add("passphrase", true, () => Array.from({ length: 4 }, word).join(pick(["-", ".", "_"])) + Math.floor(r() * 10), 10);
  add("password_in_sentence", true, () => pick([
    () => `my wifi password is ${word()}${Math.floor(r() * 100)}`,
    () => `Password: ${generated(12)}`,
    () => `login is jamie@example.com / ${cap(word())}${Math.floor(r() * 100)}!`,
    () => `the door code is ${Math.floor(1000 + r() * 9000)} and the alarm pin is ${Math.floor(1000 + r() * 9000)}`,
    () => `user: admin\npass: ${generated(14)}`,
  ])(), 15);
  add("provider_key", true, () => pick([
    () => P("sk", "-proj-", str(B64URL, 48)),
    () => P("sk", "-ant-api03-", str(B64URL, 80)),
    () => P("sk", "_live_", str(LOWER + UPPER + DIGITS, 24)),
    () => P("AK", "IA", str(UPPER + DIGITS, 16)),
    () => P("AI", "za", str(B64URL, 35)),
    () => P("gh", "p_", str(LOWER + UPPER + DIGITS, 36)),
    () => P("xox", "b-", str(DIGITS, 12), "-", str(DIGITS, 12), "-", str(LOWER + UPPER + DIGITS, 24)),
    () => P("hf", "_", str(LOWER + UPPER, 34)),
  ])(), 24);
  add("unknown_token", true, () => pick([
    () => str(LOWER + UPPER + DIGITS, 32 + Math.floor(r() * 32)),
    () => str(HEX, 40),
    () => `${str(LOWER + DIGITS, 8)}.${str(B64URL, 27)}`,
  ])(), 20);
  add("jwt", true, () => `eyJhbGciOiJIUzI1NiJ9.eyJ${str(B64URL, 40)}.${str(B64URL, 43)}`, 6);
  add("private_key", true, () => pick([
    () => P("-----BEGIN ", pick(["OPENSSH", "RSA", "EC"]), " PRIV", "ATE KEY-----\n", str(B64URL, 64), "\n", str(B64URL, 64)),
    () => `0x${str(HEX, 64)}`,
    () => P("xp", "rv", str(B58, 107)),
  ])(), 12);
  add("config_line", true, () => pick([
    () => `DB_PASSWORD=${generated(16)}`,
    () => `export STRIPE_KEY=${str(LOWER + UPPER + DIGITS, 30)}`,
    () => `  "apiKey": "${str(LOWER + UPPER + DIGITS, 32)}",`,
    () => `postgres://app:${generated(12).replace(/[@:/]/g, "x")}@db.internal:5432/app`,
    () => `Authorization: Bearer ${str(B64URL, 40)}`,
  ])(), 20);
  add("signed_link", true, () => pick([
    () => `https://app.example.com/reset?token=${str(B64URL, 32)}`,
    () => `https://files.example-cdn.com/a.pdf?X-Amz-Signature=${str(HEX, 64)}&X-Amz-Expires=600`,
  ])(), 8);
  add("seed_phrase", true, () => Array.from({ length: pick([12, 24]) }, () => pick(SEED_WORDS)).join(" "), 6);
  add("one_time_code", true, () => String(Math.floor(100000 + r() * 900000)), 8);

  // ---- Should leave alone ----------------------------------------------------
  add("prose", false, () => pick([
    "Meeting moved to Thursday at 3pm, see you there",
    "Can you send me the deck before the call?",
    "Dinner plans for Saturday, bring the good olive oil.",
    "The quick brown fox jumps over the lazy dog.",
    "I think the onboarding needs a better explainer for the camera permission.",
    "Your password is incorrect. Try again or reset it.",
    "Remember to change your password every 90 days.",
    "Use a password manager instead of reusing passwords.",
  ]), 24);
  add("identifier", false, () => pick([
    () => `${word()}${cap(word())}${Math.floor(r() * 10)}`,
    () => `get${cap(word())}By${cap(word())}`,
    () => `${word()}_${word()}_${Math.floor(r() * 100)}`,
    () => `${cap(word())}${cap(word())}Controller`,
  ])(), 20);
  add("file_or_path", false, () => pick([
    () => `${word()}-${word()}-v${Math.floor(r() * 9)}.mp4`,
    () => `~/Projects/${word()}/src/${word()}.ts`,
    () => `Q${1 + Math.floor(r() * 4)}-2026_${cap(word())}_Final.pdf`,
    () => `/Users/jamie/Downloads/IMG_${Math.floor(1000 + r() * 9000)}.HEIC`,
  ])(), 16);
  add("id_or_hash", false, () => pick([
    () => `${str(HEX, 8)}-${str(HEX, 4)}-4${str(HEX, 3)}-a${str(HEX, 3)}-${str(HEX, 12)}`,
    () => str(HEX, 7),
    () => `#${str(HEX, 6)}`,
    () => `ORD-${Math.floor(r() * 1e8)}`,
    () => `1Z${str(UPPER + DIGITS, 16)}`,
    () => str(UPPER + DIGITS, 6),
  ])(), 24);
  add("code", false, () => pick([
    "const user = await db.getUser(id);",
    "items[0].name = 'Clip';",
    "if (password.length < 8) return error('too short');",
    "export const handler = async (req) => new Response('ok');",
    "SELECT id, email FROM users WHERE created_at > now() - interval '7 days';",
    "password: string;",
    "const apiKey = process.env.API_KEY;",
    "max_tokens: 4096",
  ]), 24);
  add("command", false, () => pick([
    "git push origin main",
    "npm install hono",
    "gcloud auth application-default login",
    "gh secret set API_TOKEN --env prod",
    "docker compose up -d",
    "docker logs -f web-1",
  ]), 18);
  add("link", false, () => pick([
    () => `https://www.youtube.com/watch?v=${str(B64URL, 11)}`,
    () => `https://github.com/${word()}/${word()}/pull/${Math.floor(r() * 900)}`,
    () => `https://meet.google.com/${str(LOWER, 3)}-${str(LOWER, 4)}-${str(LOWER, 3)}`,
    () => `https://www.example.com/blog/${word()}-${word()}?utm_source=newsletter`,
  ])(), 20);
  add("contact_or_date", false, () => pick([
    () => `${word()}@${word()}.com`,
    () => `555-01${String(Math.floor(r() * 100)).padStart(2, "0")}`,
    () => `2026-10-${String(1 + Math.floor(r() * 28)).padStart(2, "0")}T12:34:56Z`,
    () => `${Math.floor(1 + r() * 12)}:${String(Math.floor(r() * 60)).padStart(2, "0")}PM`,
    () => "123 Main St, Springfield, IL 62701",
    () => `v${Math.floor(r() * 5)}.${Math.floor(r() * 20)}.${Math.floor(r() * 100)}-beta`,
  ])(), 24);
  add("short_word", false, () => pick(["that", "next", "published", "Clip", "acme-data-lake", "C++17", "$29.99", "@JohnSmith1990", "x=5&y=10"]), 18);

  return cases;
}
