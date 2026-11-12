# jeweler

Tells you whether a piece of text is a password, key or code: right where your code runs, with nothing sent anywhere.

```sh
npm install jeweler
```

```ts
import { score, threshold } from "jeweler";

const s = score(text);                        // 0 to 1, or null when it isn't something jeweler judges
const isSecret = s !== null && s >= threshold;
```

What it says:

```ts
score("Summer2026!")          // 0.99  password
score("Tr0ub4dor&3")          // 0.98  password
score("x7Kp2mQ9vL4w")         // 1.00  generated password
score("nbB-Pdv-v3v-WUc")      // 0.98  Apple-style generated password

score("Thursday2026")         // 0.32  a day and a year
score("handleSubmit")         // 0.01  code
score("INV-2026-0142")        // 0.00  an invoice number

score("see you at noon")      // null  a sentence, not a single token
score("someone@example.com")  // null  an email: leave it to your own rules
```

## Where it helps

- **Clipboard managers:** don't keep a copied password in history.
- **Chat, email and comments:** warn before someone sends a password.
- **Notes and shared docs:** flag a password pasted where others can read it.
- **Logs and analytics:** scrub secrets before they're stored, on the device or on your server.
- **Terminals and shell history:** keep typed passwords out of history.
- **Forms and support tools:** catch a password typed into the wrong field.

## Why jeweler

- **Private:** it runs locally. The text never leaves your app or your server to be checked.
- **Tiny and fast:** adds about 145 KB to your app (58 KB download), no dependencies, about a quarter of a millisecond per check.
- **Runs anywhere JavaScript runs:** browsers, Node 20+, Deno, Bun, React Native. It's an ES module, so load it with `import`; `require("jeweler")` works only on Node 22.12 and later.

## What it doesn't do

- It judges single tokens of 8 to 64 characters. Sentences, links, emails, file names and plain numbers return `null`, and so does anything that isn't a string (like `null` from a clipboard API).
- It reads only plain English letters as letters for now. Accents lower the score (`Sommér2026!` 0.84, `Summer2026!` 0.99), and text with no plain letters at all (`ПАРОЛЬ123!`) returns `null`. Model v2 will handle these.
- Keys with a known prefix (`sk-...`, `AKIA...`, `ghp_...`) and numbers with a checksum (cards) are better caught by exact rules; use a secret scanner alongside it. jeweler is for what those rules miss: passwords people make up and generated ones without a prefix.
- Passphrases of plain words (`correct-horse-battery-staple`) mostly slip by.

## The model

jeweler has one model built in, with its own version: today **model v1** (`model.version`). The library and the model are versioned separately:

- **jeweler 0.1.0, 0.1.1, ...** for code changes. The model stays the same.
- **model v1, v2, ...** when the model gets better. Each one ships in a new jeweler version, noted in [CHANGELOG.md](CHANGELOG.md), and the raw model file is in this repo (`models/jeweler-v1.json`).

To stay on one model, pin the jeweler version. To try another model file, pass it in: `score(text, parseJewel(json))`.

Also exported: `gated(text)` (would jeweler judge this?), `rawScore(text)` (score without that check), `parseJewel(json)` (validate a model you load yourself) and the `Jewel` types. How the model was tested: [docs/benchmark.md](docs/benchmark.md).

---

# How Jewel is made

Everything below is for working on the models themselves.

## How it fits together

1. **Generate** fake passwords, keys and codes of every kind (`bench/dataset.ts`, `bench/holdout.py`), and look-alikes that must stay unlocked. Nothing real. What kinds and why: [docs/corpus.md](docs/corpus.md).
2. **Collect harmless text** so the model learns what normal copies look like (`bench/negatives.py`; Jewel 3 uses 14 public, permissively licensed repos, listed in [docs/public-negatives.md](docs/public-negatives.md); Jewel 1 and 2 used private repos).
3. **Train** (`bench/jewel.py`): character 1-4 grams of the text and 1-6 grams of its shape (`Aa9!`), optionally the whole shape collapsed into runs (`Thursday2026` → `Aa9`) as one more gram, plus length, variety and word count; logistic regression; only single tokens of 8-64 characters are judged (the gate). The feature configuration travels inside the model JSON and the runtime honours it, so variants ship without runtime changes.
4. **Evaluate** (`bench/run.ts report`, `bench/holdout.py`, `bench/curve.py`, `bench/leaked.ts`): the benchmark, fresh generators the model never saw (seeded, so frozen), other people's generators (Apple, OpenSSL), 160 hand-written everyday copies that must stay unlocked (`bench/everyday.json`), real human passwords from a public leaked list streamed in memory, and the owner's clipboard history read locally (counts and masked shapes only).
   **Improve** (`bench/loop.py`): train dozens of variants (features, regularisation, training mixes) and score every one on those same frozen sets in one table, `bench/out/loop.md`. Ship a variant with `bench/export.py <n> --pkl out/loop/<variant>.pkl`.
   **Research** (`research/`): autoresearch, after [Karpathy](https://github.com/karpathy/autoresearch). An agent edits one file (`research/train.py`: data, features config, model, pruning), runs it, and keeps the change only if `fp94` improved on the frozen exam in `research/prepare.py` (which it never edits): the share of the everyday copies locked at the threshold that keeps 94% recall on about 5,500 real passwords and never fewer of the other passwords than the shipped model catches (floors read from the shipped `models/jeweler-v<n>.json` at load, false-alarm caps as guards: nothing measured may get worse). the baseline rules are asked first and everything they lock leaves the exam, so Jewel is tuned for what only it can catch. Every try is a row in `research/results.tsv`; the rules are `research/program.md`. Ship what it kept with `bench/export.py <n> --from-json research/out/candidate.json`.
5. **Export** (`bench/export.py`): prune weights, write `models/jeweler-v<n>.json`, and check that the TypeScript runtime scores exactly like Python (`runtime/parity.ts`).
6. **Ship**: the package (`npm run build`) is the runtime compiled plus the newest `models/jeweler-v<n>.json` built in; apps depend on it. After exporting a model, run `uv run bench/fixtures.py` so the tests cover it, then `npm run check`.

## Run it

```sh
npm install
npm run check                                                    # the library: typecheck, tests (parity with Python), build, packed-install check
uv run bench/fixtures.py                                         # refresh the parity fixture after a model or feature change
npx tsx bench/run.ts export && npx tsx bench/run.ts export-train   # test and training sets
npx tsx bench/run.ts rules                                       # the baseline rules
uv run bench/jewel.py --history                                   # train; count extra locks on local clipboard history
uv run bench/models.py                                           # other local models (credline, privacy-filter, Laya, CredSweeper)
OPENROUTER_API_KEY=… npx tsx bench/run.ts jev                    # Jev, the reference (~$0.10, fake data only)
npx tsx bench/run.ts report                                      # ranked report in bench/out/report.md
uv run bench/holdout.py gen && npx tsx bench/holdout-rules.ts && uv run bench/holdout.py   # held-out tests
uv run bench/export.py 2 --from-json research/out/candidate.json && npx tsx runtime/parity.ts models/jeweler-v2.json # ship model v2
npx tsx bench/leaked.ts && uv run bench/leaked.py                # real human passwords (public list, streamed in memory)
uv run bench/loop.py                                             # the experiment loop: every variant on the same frozen sets -> bench/out/loop.md
uv run research/prepare.py                                       # autoresearch: check the exam once, then point an agent at research/program.md
uv run research/train.py > research/run.log 2>&1; grep "^fp94:" research/run.log   # one experiment by hand (about 15 s)
```

Everything generated lands in `bench/out/` (gitignored). To run autoresearch from Claude Code: `Workflow` with `scriptPath: .claude/workflows/autoresearch.js` and `args: { experiments: 16, tag: "<date>" }`, after the setup in `research/program.md` (branch `autoresearch/<tag>`, header row in `research/results.tsv`); or tell any agent "read research/program.md and start". `rules/baseline-rules.ts` is a snapshot of the baseline rules; re-copy it when they change.

## Rules for this repo

- Never commit a real password, key or token, or any of the owner's clipboard text. Generators assemble provider prefixes at run time so the source doesn't look like a leak.
- Real history is only read locally, in memory; report counts and masked shapes.
- Only fake or public text goes to Jev or any other hosted model.
- A new model ships only if it beats the current one on all three tests (benchmark, fresh generators, real history).
- Models must stay small: aim under 25M parameters; 50M is the hard ceiling for anything bundled (today's is 5,080 weights).
- Public leaked-password lists are for testing only (`bench/leaked.ts`, `bench/leaked.py`): streamed in memory, never saved, never trained on, never printed. Counts and masked shapes only.

## Publishing

`npm run check`, bump `version` and `CHANGELOG.md`, then `npm publish` (`prepack` builds `dist/`).
