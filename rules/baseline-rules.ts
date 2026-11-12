/**
 * Baseline rules: regular expressions and small checks that run before the model.
 * Jewel is tuned for what these miss, so swap in your own app's rules to tune it for yours.
 *
 *   detectSecret     credentials, signed links, card numbers, SSNs, IBANs,
 *                    one-time codes, recovery phrases, random tokens.
 *   redactPersonal   emails and phone numbers masked, links cut to scheme,
 *                    host and path.
 *   labelUrl         scheme, host and path of one link.
 */

export interface SecretMatch {
  /** Smart-card type, e.g. "api_key" */
  type: string;
  /** Shown on the locked card, e.g. "OpenAI API key" */
  label: string;
}

const KNOWN: { re: RegExp; type: string; label: string }[] = [
  { re: /\bsk-proj-[A-Za-z0-9_-]{20,}/, type: "api_key", label: "OpenAI API key" },
  { re: /\bsk-ant-[A-Za-z0-9_-]{20,}/, type: "api_key", label: "Anthropic API key" },
  { re: /\bsk-or-v\d-[A-Za-z0-9]{20,}/, type: "api_key", label: "OpenRouter API key" },
  { re: /\bsk-[A-Za-z0-9_-]{20,}/, type: "api_key", label: "API key" },
  { re: /\b(sk|rk|pk)_(live|test)_[A-Za-z0-9]{16,}/, type: "api_key", label: "Stripe key" },
  { re: /\b(AKIA|ASIA)[0-9A-Z]{16}\b/, type: "api_key", label: "AWS access key" },
  { re: /\bAIza[0-9A-Za-z_-]{35}\b/, type: "api_key", label: "Google API key" },
  { re: /\b(ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{36}\b|\bgithub_pat_[A-Za-z0-9_]{22,}/, type: "secret_token", label: "GitHub token" },
  { re: /\bglpat-[A-Za-z0-9_-]{20}\b/, type: "secret_token", label: "GitLab token" },
  { re: /\bxox[abposr]-[A-Za-z0-9-]{10,}/, type: "secret_token", label: "Slack token" },
  { re: /\bnpm_[A-Za-z0-9]{36}\b/, type: "secret_token", label: "npm token" },
  { re: /\bSG\.[A-Za-z0-9_-]{22}\.[A-Za-z0-9_-]{43}\b/, type: "api_key", label: "SendGrid key" },
  { re: /\bhf_[A-Za-z0-9]{30,}\b/, type: "secret_token", label: "Hugging Face token" },
  { re: /\bphx_[A-Za-z0-9]{30,}\b/, type: "api_key", label: "PostHog personal key" },
  { re: /\bGOCSPX-[A-Za-z0-9_-]{20,}/, type: "secret_token", label: "Google OAuth secret" },
  { re: /\beyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}/, type: "jwt_token", label: "JWT" },
  { re: /-----BEGIN [A-Z ]*PRIVATE KEY(?: BLOCK)?-----/, type: "ssh_key", label: "private key" },
  { re: /\bAGE-SECRET-KEY-1[0-9A-Z]{50,}/, type: "ssh_key", label: "private key" },
  { re: /\b[xyzt]prv[1-9A-HJ-NP-Za-km-z]{100,}/, type: "ssh_key", label: "extended private key" },
  { re: /^\s*(?:0x)?[0-9a-fA-F]{64}\s*$/, type: "ssh_key", label: "hex secret" },
  { re: /\b(?:ssh-(?:rsa|ed25519|dss)|ecdsa-sha2-nistp\d+) AAAA[0-9A-Za-z+/]{40,}/, type: "public_key", label: "public key" },
  { re: /-----BEGIN (?:[A-Z]+ )*PUBLIC KEY(?: BLOCK)?-----/, type: "public_key", label: "public key" },
  { re: /\b[a-z][a-z0-9+.-]*:\/\/[^\s:/@]+:[^\s@/]{3,}@/i, type: "password", label: "credential URL" },
  { re: /\bBearer\s+[A-Za-z0-9._~+/-]{20,}=*/, type: "secret_token", label: "bearer token" },
];

/** Names that make `name = value` / `name: value` a secret. */
const SECRET_NAME = /secret|token|passw(?:or)?d|pwd|pass|api[_-]?key|private[_-]?key|access[_-]?key|client[_-]?secret/i;
const PASSWORD_NAME = /pass|pwd/i;
/** Token counts and settings, not tokens: `max_tokens: 4096`, `tokenizer: …`. */
const NOT_SECRET_NAME = /tokens\b|token_?(?:count|limit|type|url|uri|endpoint|usage)|tokenizer/i;
/** A whole line that is one assignment of a single value: `DB_PASS=…`, `"password": "…",`, `const apiKey = "…"`. */
const ASSIGNMENT =
  /^\s*(?:export\s+|const\s+|let\s+|var\s+)?["']?([\w.-]+)["']?\s*[=:]\s*["']?([^\s"'(),;{}<>]{4,})["']?\s*[,;]?\s*$/;
/** "my password is hunter22", "Password: x1y2" anywhere in a sentence. */
const PASSWORD_PHRASE = /\b(?:password|passcode|passwd|pwd)\b\s*(?:is\b|[:=])\s*["']?([^\s"'(),;{}<>]{4,})/i;
/** Values that are code, not secrets: type annotations, member access, env lookups, placeholders. */
const NOT_A_VALUE =
  /^(?:string|number|boolean|bool|int|str|any|unknown|object|array|null|undefined|none|nil|true|false|required|optional)\b|^[$@%]|^(?:process\.env|os\.environ|env\.|import\.meta)|^[A-Za-z_$][\w$]*(?:\.[A-Za-z_$][\w$]*)+$/i;
/** Words that follow "password is/:" in messages, not passwords. */
const NOT_A_PASSWORD = /^(?:incorrect|invalid|wrong|expired|empty|missing|must|should|cannot|the|your|not|too|reset|changed)$/i;

function secretAssignment(text: string): SecretMatch | null {
  for (const line of text.split("\n")) {
    const m = ASSIGNMENT.exec(line);
    if (!m || !SECRET_NAME.test(m[1]) || NOT_SECRET_NAME.test(m[1]) || NOT_A_VALUE.test(m[2])) continue;
    const password = PASSWORD_NAME.test(m[1]);
    if (!password && /^\d+$/.test(m[2])) continue; // `timeout_token_ms: 5000`
    return password ? { type: "password", label: "password" } : { type: "env_vars", label: "config secret" };
  }
  const phrase = PASSWORD_PHRASE.exec(text);
  // "Your password is incorrect." — the sentence's full stop isn't part of the word.
  const value = phrase?.[1].replace(/[.!?,;:]+$/, "");
  if (phrase && value && !NOT_A_VALUE.test(value) && !NOT_A_PASSWORD.test(value)) return { type: "password", label: "password" };
  return null;
}

/** Query or fragment parameters that make a link a key: sign-in, reset and signed links. */
const SECRET_PARAM =
  /(?:^|[?&#;/])(?:token|access_token|id_token|refresh_token|code|key|api_key|apikey|sig|signature|secret|password|pwd|otp|auth|session|sessionid|x-amz-signature|x-amz-credential|x-goog-signature|x-goog-credential)=/i;
const URL_RE = /\bhttps?:\/\/[^\s<>"'`]+/gi;

function hasSecretLink(text: string): boolean {
  for (const raw of text.match(URL_RE) ?? []) {
    try {
      const u = new URL(raw);
      if (SECRET_PARAM.test(u.search + u.hash)) return true;
    } catch {
      // Not a URL after all.
    }
  }
  return false;
}

function luhn(digits: string): boolean {
  let sum = 0;
  for (let i = 0; i < digits.length; i++) {
    let d = digits.charCodeAt(digits.length - 1 - i) - 48;
    if (i % 2 === 1) {
      d *= 2;
      if (d > 9) d -= 9;
    }
    sum += d;
  }
  return sum % 10 === 0;
}

/** 13–19 digits, single spaces or dashes between groups, a card network's first digit, passing Luhn. */
function hasCardNumber(text: string): boolean {
  for (const m of text.match(/(?<![\d-])\d(?:[ -]?\d){12,18}(?![\d])/g) ?? []) {
    const digits = m.replace(/\D/g, "");
    if (/^[2-6]/.test(digits) && luhn(digits)) return true;
  }
  return false;
}

const SSN = /\b(?!000|666|9\d\d)\d{3}-(?!00)\d{2}-(?!0000)\d{4}\b/;

function ibanValid(iban: string): boolean {
  const moved = iban.slice(4) + iban.slice(0, 4);
  let rem = 0;
  for (const ch of moved) {
    const n = /\d/.test(ch) ? ch : String(ch.charCodeAt(0) - 55);
    for (const d of n) rem = (rem * 10 + Number(d)) % 97;
  }
  return rem === 1;
}

/** Two letters, two check digits, 11–30 letters or digits (spaces allowed), passing mod 97. */
function hasIban(text: string): boolean {
  for (const m of text.match(/\b[A-Z]{2}\d{2}(?: ?[A-Z0-9]){11,30}\b/g) ?? []) {
    if (ibanValid(m.replace(/ /g, ""))) return true;
  }
  return false;
}

const OTP = /^(?:\d{6,8}|\d{3}[ -]\d{3})$/;
const SEED_LENGTHS = new Set([12, 15, 18, 21, 24]);

function isSeedPhrase(t: string): boolean {
  if (!/^[a-z]{3,8}(?: [a-z]{3,8})+$/.test(t)) return false;
  return SEED_LENGTHS.has(t.split(" ").length);
}

/** Shannon entropy in bits per character. */
function entropy(s: string): number {
  const counts = new Map<string, number>();
  for (const c of s) counts.set(c, (counts.get(c) ?? 0) + 1);
  let h = 0;
  for (const n of counts.values()) {
    const p = n / s.length;
    h -= p * Math.log2(p);
  }
  return h;
}

/** One unbroken token that looks random: long, mixed classes, high entropy, not a URL or path. */
function looksLikeRandomToken(text: string): boolean {
  const t = text.trim();
  if (t.length < 24 || t.length > 500 || /\s/.test(t)) return false;
  if (/^(https?:\/\/|\/|~\/|[a-z]:\\)/i.test(t) || /^[\w.+-]+@[\w-]+\.[\w.]+$/.test(t)) return false;
  if (/^[0-9a-f-]{36}$/i.test(t)) return false; // UUIDs are ids, not secrets
  const classes = [/[a-z]/, /[A-Z]/, /[0-9]/].filter((re) => re.test(t)).length;
  return classes >= 3 && entropy(t) >= 4.0;
}

/**
 * Apple's generated strong passwords (Passwords app, Safari): four groups of three
 * (`abC-d3f-ghi-jkl`) or, in older versions, three groups of six, joined by
 * hyphens, with at least one digit, one capital and one lowercase letter
 * (so ids like `INV-202-610-045` stay unlocked).
 */
const APPLE_PASSWORD = /^(?=[^\s]*\d)(?=[^\s]*[A-Z])(?=[^\s]*[a-z])(?:[A-Za-z0-9]{3}(?:-[A-Za-z0-9]{3}){3}|[A-Za-z0-9]{6}(?:-[A-Za-z0-9]{6}){2})$/;

/**
 * Symbols that show up in passwords; `_ - .` alone only make identifiers, slugs
 * and file names. Letters and digits of any script are letters and digits, not
 * symbols, so `Zürich2026` and `Søndergaard1` are words with a number, not passwords.
 */
const PASSWORD_SYMBOL = /[^\p{L}\p{N}_.-]/u;
/** Code, queries, handles, dates and times that mix the same character classes. */
const NOT_A_PASSWORD_SHAPE =
  /^\d{4}-\d{2}-\d{2}|^\d{1,2}:\d{2}|^[a-z0-9-]+(?:\.[a-z0-9-]+)+(?:[/:?#]|$)|^[@#$][A-Za-z][\w.]*$|^#[0-9a-f]{3,8}$|[A-Za-z_]\w*\(.*\)|=>|->|::|\[\w*\]|^\w+=[^&]*(?:&\w+=[^&]*)+$/i;

/**
 * One short unbroken string shaped like a typed or generated password, e.g. a
 * mix like `k8Q=v2#Lp`: 8-64 characters, no spaces, at least one symbol other
 * than `_ - .`, and either all four classes (lower, upper, digit, symbol) or,
 * from 12 characters, three of them; not a URL, path, email, handle, color
 * or bit of code.
 */
function looksLikePassword(text: string): boolean {
  const t = text.trim();
  if (t.length < 8 || t.length > 64 || /\s/.test(t)) return false;
  if (/^(https?:\/\/|\/|~\/|[a-z]:\\)/i.test(t) || t.includes("://") || /^[\w.+-]+@[\w-]+\.[\w.]+$/.test(t)) return false;
  if (!PASSWORD_SYMBOL.test(t) || NOT_A_PASSWORD_SHAPE.test(t)) return false;
  const classes = [/\p{Ll}/u, /\p{Lu}/u, /\p{N}/u, PASSWORD_SYMBOL].filter((re) => re.test(t)).length;
  if (classes < 3 || (classes === 3 && t.length < 12)) return false;
  return entropy(t) >= 2.75;
}

export function detectSecret(text: string | null | undefined): SecretMatch | null {
  if (!text) return null;
  for (const k of KNOWN) if (k.re.test(text)) return { type: k.type, label: k.label };
  const assignment = secretAssignment(text);
  if (assignment) return assignment;
  if (hasSecretLink(text)) return { type: "secret_link", label: "signed URL" };
  if (hasCardNumber(text)) return { type: "credit_card", label: "card number" };
  if (SSN.test(text)) return { type: "ssn", label: "US SSN" };
  if (hasIban(text)) return { type: "iban", label: "IBAN" };
  const t = text.trim();
  if (OTP.test(t)) return { type: "otp", label: "OTP" };
  if (isSeedPhrase(t)) return { type: "seed_phrase", label: "seed phrase" };
  if (/^[0-9a-f]{32,}$/i.test(t)) return { type: "secret_token", label: "random token" };
  if (looksLikeRandomToken(text)) return { type: "secret_token", label: "random token" };
  if (looksLikePassword(text)) return { type: "password", label: "password" };
  if (APPLE_PASSWORD.test(t)) return { type: "password", label: "password" };
  return null;
}

/** Scheme, host and path only: no credentials, query or fragment. */
export function labelUrl(url: string): string {
  try {
    const u = new URL(url);
    return `${u.protocol}//${u.host}${u.pathname}`;
  } catch {
    return url.split(/[?#]/)[0];
  }
}

const EMAIL = /[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}/gi;
/** +E.164, or 2–4 digit groups joined by spaces, dots or dashes (a sentence's full stop may follow); checked for 10–15 digits below. */
const PHONE = /(?<![\w.:/-])(?:\+\d{1,3}[\s.-]?)?(?:\(\d{2,4}\)[\s.-]?)?\d{2,4}(?:[\s.-]\d{2,4}){1,4}(?![\w:/-]|\.\w)|\+\d{10,15}\b/g;

function isPhone(m: string): boolean {
  const digits = m.replace(/\D/g, "").length;
  if (digits < 10 || digits > 15) return false;
  if (/\d{4}-\d{2}-\d{2}/.test(m)) return false; // ISO date (and time)
  if (/^\d{1,3}(?:\.\d{1,3}){3}$/.test(m)) return false; // IPv4
  return true;
}

/** The text with emails and phone numbers masked and every link cut to its scheme, host and path. */
export function redactPersonal(text: string): string {
  return text
    .replace(URL_RE, (u) => labelUrl(u))
    .replace(EMAIL, "[email]")
    .replace(PHONE, (m) => (isPhone(m) ? "[phone]" : m));
}
