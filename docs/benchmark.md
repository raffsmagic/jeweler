# Lock benchmark: which checker best spots passwords and keys

Run 2026-10-05 with `bench/` (how to run it: README.md). Naming (since 2026-11-11): jeweler's model is versioned v1, v2...; **v1 = Jewel 3** (`models/jeweler-v1.json`). Jewel 1 and 2 were trained on private text and are no longer in this repo. Older naming: the model is **Jewel**, numbered (Jewel 1 = `models/jewel-1.json`). In rounds 1-3 it was labelled `tiny`; the tables below use the current names. The test set is 387 generated cases, all fake: 199 that the app should lock (generated and typed passwords, passphrases, passwords inside sentences, provider keys, unknown tokens, JWTs, private keys, config lines, signed links, recovery phrases, one-time codes) and 188 look-alikes it should leave alone (prose, identifiers, file names, ids and hashes, code, commands, links, contacts and dates, short words). Jev is the reference. Apple's on-device model wasn't tested: Apple Intelligence is off on this Mac.

"rules+X" means the rules run first and X checks what they let through (lock if either says so), which is how a second layer would work in the app.

## Ranked by F1

| Checker | Cases | Catches (recall) | Right when it locks (precision) | F1 | Missed | False alarms | Median time | Threshold |
| - | - | - | - | - | - | - | - | - |
| rules+jewel | 387 | 95.5% | 96.0% | 0.957 | 9 | 8 | 0.001 ms | 0.5 |
| rules+jev@0.5 | 387 | 90.5% | 100.0% | 0.950 | 19 | 0 | 331 ms | 0.5 |
| rules+credline | 387 | 88.4% | 99.4% | 0.936 | 23 | 1 | 1.89 ms | 0.5 |
| rules | 387 | 83.4% | 100.0% | 0.910 | 33 | 0 | 0.002 ms | 0.5 |
| rules+credsweeper | 387 | 84.9% | 96.0% | 0.901 | 30 | 7 | 0.03 ms | 0.5 |
| rules+laya | 387 | 95.5% | 81.5% | 0.880 | 9 | 43 | 32.01 ms | 0.5 |
| rules+privacy_filter | 387 | 84.9% | 91.4% | 0.880 | 30 | 16 | 33.42 ms | 0.5 |
| jev@0.5 | 387 | 76.9% | 100.0% | 0.869 | 46 | 0 | 331 ms | 0.5 |
| laya | 387 | 88.4% | 80.4% | 0.842 | 23 | 43 | 32.01 ms | 0.5 |
| jewel | 387 | 64.3% | 94.1% | 0.764 | 71 | 8 | 0.001 ms | 0.5 |
| credline | 387 | 54.3% | 99.1% | 0.701 | 91 | 1 | 1.89 ms | 0.74 |
| privacy_filter | 387 | 55.3% | 87.3% | 0.677 | 89 | 16 | 33.42 ms | 0.5 |
| jev | 387 | 46.7% | 100.0% | 0.637 | 106 | 0 | 331 ms | 0.8 |
| credsweeper | 387 | 24.1% | 87.3% | 0.378 | 151 | 7 | 0.03 ms | 0.62 |

## Right answers by kind

| Kind | Should lock | credline | jev | privacy_filter | rules | jev@0.5 | rules+credline | rules+jev@0.5 | rules+privacy_filter |
| - | - | - | - | - | - | - | - | - | - |
| generated_password | yes | 13/40 | 11/40 | 22/40 | 37/40 | 39/40 | 37/40 | 40/40 | 37/40 |
| typed_password | yes | 0/30 | 5/30 | 9/30 | 19/30 | 16/30 | 19/30 | 21/30 | 19/30 |
| passphrase | yes | 4/10 | 0/10 | 0/10 | 0/10 | 0/10 | 4/10 | 0/10 | 0/10 |
| password_in_sentence | yes | 12/15 | 15/15 | 9/15 | 9/15 | 15/15 | 12/15 | 15/15 | 9/15 |
| provider_key | yes | 24/24 | 20/24 | 21/24 | 24/24 | 24/24 | 24/24 | 24/24 | 24/24 |
| unknown_token | yes | 15/20 | 7/20 | 13/20 | 20/20 | 18/20 | 20/20 | 20/20 | 20/20 |
| jwt | yes | 6/6 | 4/6 | 6/6 | 6/6 | 6/6 | 6/6 | 6/6 | 6/6 |
| private_key | yes | 8/12 | 8/12 | 11/12 | 12/12 | 12/12 | 12/12 | 12/12 | 12/12 |
| config_line | yes | 18/20 | 20/20 | 19/20 | 17/20 | 20/20 | 20/20 | 20/20 | 20/20 |
| signed_link | yes | 8/8 | 3/8 | 0/8 | 8/8 | 3/8 | 8/8 | 8/8 | 8/8 |
| seed_phrase | yes | 0/6 | 0/6 | 0/6 | 6/6 | 0/6 | 6/6 | 6/6 | 6/6 |
| one_time_code | yes | 0/8 | 0/8 | 0/8 | 8/8 | 0/8 | 8/8 | 8/8 | 8/8 |
| prose | no | 24/24 | 24/24 | 24/24 | 24/24 | 24/24 | 24/24 | 24/24 | 24/24 |
| identifier | no | 20/20 | 20/20 | 20/20 | 20/20 | 20/20 | 20/20 | 20/20 | 20/20 |
| file_or_path | no | 16/16 | 16/16 | 15/16 | 16/16 | 16/16 | 16/16 | 16/16 | 15/16 |
| id_or_hash | no | 23/24 | 24/24 | 17/24 | 24/24 | 24/24 | 23/24 | 24/24 | 17/24 |
| code | no | 24/24 | 24/24 | 24/24 | 24/24 | 24/24 | 24/24 | 24/24 | 24/24 |
| command | no | 18/18 | 18/18 | 16/18 | 18/18 | 18/18 | 18/18 | 18/18 | 16/18 |
| link | no | 20/20 | 20/20 | 20/20 | 20/20 | 20/20 | 20/20 | 20/20 | 20/20 |
| contact_or_date | no | 24/24 | 24/24 | 20/24 | 24/24 | 24/24 | 24/24 | 24/24 | 20/24 |
| short_word | no | 18/18 | 18/18 | 16/18 | 18/18 | 18/18 | 18/18 | 18/18 | 16/18 |

## Round 2 (2026-10-05): Laya and our own Jewel

- **Laya** (convaiinnovations/laya, 421M, Apache 2.0) asks questions the way Jev does, but locally. It catches the most (rules plus Laya: 95.5%) and raises the most false alarms (43: ids, code, sentences that mention passwords). Smallest build is about 450 MB, so it's too big to bundle. Asking it only about single tokens cuts false alarms to 9 at 91% caught.
- **Our own model, Jewel** (`bench/jewel.py`): logistic regression over character patterns, trained on fake passwords from other seeds plus 39,497 harmless lines from our repos' tracked source and docs (anything our rules flag was removed first). It only judges single tokens of 8-64 characters that aren't links, emails, numbers or file names. Rules plus Jewel: **95.5% caught, 8 false alarms, under 0.01 ms, about 600 KB** (prunable). Caveat: the benchmark flatters it, because its training data comes from the same generator as the test set. The honest check is the owner's real history, which it never trained on: it would newly lock 26 of 1,245 items, and roughly 20 of those look like real passwords and tokens (including the 15 the rules already found); the rest are long ids.
- **Benchmarks elsewhere:** public classifier leaderboards (MTEB classification, TextClass) rank general text tasks, not "is this a password", so this benchmark is the one that answers our question.

## Round 3 (2026-10-05): held-out tests

`bench/holdout.py` (run order in its header).

**Fresh passwords** from 12 generators no checker was tuned on (Python `secrets`; 25 each, 300 total). Caught: rules 120, Jewel 221, credline 55, Laya 247, **rules plus Jewel 270 (90%)**. Everyone misses passphrases written with spaces ("anchor velvet raven quill"); the rules miss 4-digit PINs (on purpose: too many false alarms). Jewel misses CamelCase memorable passwords (`MeadowRavenQuill?3`), which the rules catch, so the two cover each other.

**The owner's real history** (1,262 items, read in memory, never trained on; only counts and masked shapes printed). 71 items are locked or would be locked by the current rules. Of the rest, Jewel would lock 5, and all 5 are password-shaped (two look like part of one password copied twice); credline would lock 22 (links, file names, long logs); Laya 115 (links, prose). Jewel only judges single tokens, so it isn't expected to catch the rules' multi-word locks (card numbers, sign-in links, config lines).

## Round 4 (2026-10-05): CredSweeper, and real human passwords

**Samsung CredSweeper** (pip `credsweeper`, MIT): about 200 regex rules, then a 2.86M-parameter ONNX validator (11.5 MB, 34 hand features) that only confirms what the rules found. Run as `bench/models.py credsweeper` at its "medium" threshold (0.62). Alone: 24.1% caught, 7 false alarms (5 UUIDs, a command containing one). Rules plus CredSweeper: 84.9% caught (rules alone 83.4%), 7 false alarms, 0.03 ms. It is perfect on config lines (20/20, the rules get 17/20) and gets 19/24 provider keys and 6/15 passwords in sentences, but 0/40 generated passwords, 0/30 typed passwords, 0/20 unknown tokens, 0/6 JWTs and 0/12 private keys: a bare string never becomes a candidate, so the validator never sees it. **Verdict: no gain for the app.** The three config lines it adds are a rules fix, not an 11.5 MB dependency.

**Passwords in the wild** (`bench/leaked.ts`, `bench/leaked.py`): the first measure of recall on passwords real people chose. The public 000webhost unique-password list (as redistributed in SecLists: 720,302 lines, leaked 2015) is streamed from GitHub into memory; nothing is written and no password is printed, only counts and masked shapes. 564,898 lines pass the gate (one token, 8-64 characters, has a letter).

| Checker | Caught of 564,898 | Share |
| - | - | - |
| rules | 7,437 | 1.3% |
| Jewel 1 | 531,269 | 94.0% |
| rules + Jewel 1 | 532,540 | 94.3% |

On the same list sampled every 200th line by CRC32 (2,836 passwords), so the slow checkers finish in seconds: Jewel (the unpruned pickle) 94.0%, credline 1.0%, CredSweeper 0.8%. The off-the-shelf scanners do not see bare passwords at all; the rules barely do (they need a symbol or a known format), which is exactly the gap the model was built for.

By structure, Jewel 1 catches 99.4% of `lower+digits` (356,205 passwords, the most common structure), 99.8% of `Word+digits`, 95.1% of mixed case with digits, 84.3% of `digits+lower`, 55.8% of passwords with a symbol (the rules add most of what it gets there), and 2.6% of all-lowercase (342). Recall is flat across lengths 8-20 (93-98%). The most common missed shapes are digit-first (`9aaaaaaa`, `99aaaaaa`) and `99-Aaa-99`, which is a date and arguably right to leave alone. Score quartiles: p10 0.71, p50 0.99; at threshold 0.3 the model would catch 96.5%, at 0.7 90.2%.

Two cautions. First, 000webhost is one site from 2015 with a letters-and-digits policy, so symbols are rare and the list says little about password-manager output (the fresh-generator test covers that). Second, this is the mirror image of the backlog: catching 99.8% of `Word+digits` is the same behaviour as locking `Thursday2026`. The wild test gives the recall side of that trade; the everyday-negatives work gives the other side.

## Round 5 (2026-10-05): the experiment loop, 84 variants on frozen sets

`bench/loop.py` trains every variant and scores it on the same four frozen sets: the benchmark (387), the fresh generators (300, now seeded so they never change), **160 hand-written everyday copies that must stay unlocked** (`bench/everyday.json`: word+year tags, report names, product names, identifiers, places, versions, order codes, plain words, CamelCase phrases) and 5,567 real human passwords (every 100th gated line of the 000webhost list, streamed). Variants: 7 feature configurations (Jewel 1's; boundary markers; 64k hash buckets; longer grams; no dense features; a smaller 16k-bucket model) × C in {1, 4, 16} × 4 training mixes (base; base plus 500, 1,500 or 3,000 generated everyday-shaped negatives from words disjoint from the test list). Fits take about 2 seconds each; the whole grid ran in 4.3 minutes. Full table: [loop.md](loop.md).

**Jewel 1 as the baseline row reproduces its numbers** (rules + Jewel 95.5% / 8 false alarms, fresh 90.3%, wild 93.9%) and adds the number we never had: it locks **60 of the 160 everyday copies (37.5%)**: 12/12 word+year, 11/12 report tags, 14/20 product names, 8/16 CamelCase phrases, 6/16 version strings, but only 3/28 identifiers, 4/20 names and places, 2/20 order codes and 0/16 plain words.

What the grid says:

1. **Features don't matter; data does.** All seven feature configurations on the base mix land within noise of each other: everyday false alarms 37-40%, wild recall 92.6-94.5%. Boundary markers, more hash buckets and longer n-grams buy nothing; a 16k-bucket model with 3-grams is as good as Jewel 1 at half the weights. The model is limited by what it has seen, not by what it can represent.
2. **Everyday-shaped negatives are the lever, and it is a trade.** Each dose moves the model along one frontier: at C=4, 500 negatives take everyday false alarms from 37.5% to 24% and wild recall from 93.9% to 89.7%; 1,500 → 16% and 85%; 3,000 → 15% and 81%. Roughly five points of real-password recall per ten points of false alarms, because two thirds of real human passwords have exactly the `Word+digits` and `lower+digits` shape the negatives teach it to leave alone.
3. **The threshold alone can't fix Jewel 1.** At whatever threshold keeps 94% wild recall, Jewel 1 still locks 39% of everyday copies; the best variant trained with everyday negatives locks 26% at the same recall. Training reorders the scores; the threshold only slides along them.
4. **Regularisation sets the size.** C=1 gives 3-5k weights (40-60 KB) with the best wild recall but about 20 benchmark false alarms (ids and identifiers); C=16 gives 7-9k weights (110-140 KB) with 2-7. C=4 (Jewel 1's) is the middle.
5. **What nothing fixes:** version and platform strings (`arm64-apple`, `x86_64-linux`, ISO timestamps: 6/16 in every variant) and about 8/20 product names. Those need a rule or a word list, not more training.

Candidates for Jewel 2, each a different answer to "how much real-password recall is a false alarm worth" (pick one, then run the owner's history, export, parity and the app's staging test):

| Candidate | ~KB | Everyday false alarms | Wild recall | Fresh (rules + Jewel) | Benchmark false alarms (rules + Jewel) |
| - | - | - | - | - | - |
| Jewel 1 (`jewel1/C4/base`) | 76 | 37.5% | 93.9% | 90.3% | 8 |
| `boundary_64k/C4/+everyday1500` | 92 | 16.3% | 88.0% | 89.0% | 11 |
| `boundary_char5_shape8/C4/+everyday3000` | 105 | 12.5% | 86.1% | 89.0% | 7 |
| `small_16k/C16/+everyday3000` | 87 | 8.7% | 81.8% | 86.7% | 2 |

Caveat: 160 everyday items means each one is 0.6 points, so differences under about 5 points are noise; the set should grow before fine choices are made. The 000webhost list is one site's 2015 passwords and overweights `lower+digits`; wild recall on password-manager output is covered by the fresh set instead.

## Round 6 (2026-10-06): autoresearch, two runs

The experiment loop became an agent. `research/` follows Karpathy's autoresearch (March 2026): `prepare.py` is the frozen exam, `train.py` the one file the agent edits, `program.md` its rules, `results.tsv` the log; `.claude/workflows/autoresearch.js` runs one agent per experiment and an adversarial reviewer every fourth. The exam: 5,567 real passwords (every 100th gated line of the 000webhost list, streamed, never written), the 160 everyday copies, 249 gated fresh passwords, the benchmark's 128 gated passwords and 50 gated look-alikes, 228 gated repo tokens held out of training, and the owner's unlocked single-token history (counts only). The metric, `fp94`: the share of everyday copies locked at the threshold that keeps 94% of the real passwords. A run takes 15-30 seconds; an experiment about four minutes with the agent's thinking.

**Run oct5** (6 experiments, stopped): the rule only held real-password recall fixed and *watched* the generated-password tests. The agent took everyday locks from 61 to 28 of 160 (`research/runs/oct5.tsv`), but fresh-generator recall slid from 220 to 214 of 249 and the benchmark from 128 to 127. Owner's call: accuracy never goes down. **Run oct5b** (16 experiments, `research/runs/oct5b.tsv`) therefore moved the floors inside the metric: the threshold is the lowest of the one keeping 94% of wild passwords, the one keeping Jewel 1's 220 fresh and the one keeping all 128 benchmark keys, and look-alike (10 of 50) and repo-token (1 of 228) false alarms are hard caps. Scoring any password lower now drags the threshold down and shows up as false alarms; locking one more harmless copy discards the run. Under that rule run oct5's result re-scores as 42 of 160 and breaks the look-alike cap.

The kept chain of run oct5b (everything at the candidate's own threshold; nothing below Jewel 1 anywhere):

| Step | Change | Everyday locked (of 160) | Fresh caught (of 249) | Benchmark keys (of 128) | Look-alikes locked (of 50) | Repo tokens locked (of 228) | KB |
| - | - | - | - | - | - | - | - |
| Jewel 1 | baseline recipe | 61 | 220 | 128 | 10 | 1 | 76 |
| 1 | run oct5's recipe in one step: boundary markers on, dense features off, 3,000 everyday-shaped negatives, 2,000 human-shaped and 1,000 full-punctuation positives, given positives weighted ×3 | 32 | 220 | 128 | 8 | 0 | 118 |
| 2 | 4 everyday patterns for product models and platform versions | 30 | 220 | 128 | 9 | 0 | 122 |
| 3 | 300 CamelCase-word positives, given look-alikes weighted ×3 | 24 (flattered; see 5) | 235 | 128 | 6 | 1 | 141 |
| 4 | **honest base: training rows that are exam strings dropped; 1,000 pronounceable positives (`vorbatel92`); 800 positives with digits inside short letter runs; 500 `@CamelCase` handle and 200 `word++;` negatives** | **19** | 221 | 128 | 10 | 0 | 137 |

Ten discards taught as much as the keeps. What the two runs say:

1. **Data, again, and under floors the order matters.** Run oct5's path (negatives first, then human-shaped positives) is penalised under the floors because it dips before it recovers; the same recipe as one step passes. The floors are a real constraint on the search, not just on the result.
2. **The real passwords nearest the threshold are not `Word+digits`.** Of the 64 wild passwords within 0.03 of the threshold at step 3, three were word+digits; most were short lowercase strings with a digit or two inside (`ab1cd2ef`, 26 of them 8 characters long). Positives of that shape (digit runs inside letter runs of two or three) lifted the threshold by 0.08 with no everyday copy following, the biggest honest gain of the run.
3. **The 38,000 multi-line repo lines earn their place** although the gate never shows Jewel multi-token text: dropping them sent held-out repo tokens from 1 to 9 locked (they teach that code punctuation is not a password) and letters-only copies up (`plain_word` 1 to 4). Down-weight, don't drop.
4. **CamelCase-word passwords need a counterweight.** 1,000 CamelCase positives alone caught 25 of 25 but taught "capitals inside a word run" rather than the symbol+digit tail, and camelCase identifiers broke the look-alike cap; 300 with the look-alikes weighted up caught 12 of 25 and held the cap. Still the weakest kind: 3 of 25 at the end, and the fresh floor sits one item from binding.
5. **The exam had a hole, and the agent found it.** `bench/dataset.ts` repeats 16 fixed strings in every seed, so 153 training rows were exam strings (459 at ×3), and the look-alike cap at step 3 was held partly by memorising 12 of the 50 exam look-alikes: measured honestly that step is 27 of 160 and breaks both caps. The reviewer flagged it, experiment 13 measured it, step 4 removed the rows in `train.py`. The next run moves the cleaning into the frozen `prepare.py` so no trainer can lean on it.
6. **Balanced class weights make every negative a threshold slide.** Adding negative mass lowers every score, so targeted negatives (letters-only, tag-shaped) cut their kinds but let other kinds in at the lower threshold and tripped the repo cap of 1. Sample weights on the positives are the way to pay for negatives.
7. **What remains** at step 4: product names 8 of 20 and report tags 3 of 12 (Capitalised+digits, exactly the shape of a typed password), version strings 2 of 16, and the CamelCase passwords above. The product-model negatives use the suffixes `Pro`/`Max`, which three everyday items also use (`iPhone17Pro`, `Boeing737MAX`); the peek check sees only 4-letter words, so this was accepted knowingly and is noted here.

**Candidate** (`research/out/candidate.json`, step 4): boundary markers on, dense features off, 9,117 weights, 137 KB, threshold 0.772 inside the file (94% wild recall by construction); AUC wild-vs-everyday 0.963 (Jewel 1: 0.826); on the owner's 38 unlocked single-token copies it locks 18 (Jewel 1: 21 of 40, the database moved between runs); `runtime/parity.ts` scores it identically in TypeScript. Not shipped as Jewel 2 yet: the next run re-scopes the exam to the copies the baseline rules miss (Jewel's actual job, since rules run first and catch 134 of the 300 fresh and 166 of the 387 benchmark cases) and cleans the training data in the frozen file; the owner's history and the app's staging decide after that. Resolution caveat as in round 5: one everyday item is 0.6 points.

## Round 7 (2026-10-06): the exam becomes Jewel's job, and one feature by hand

**Run oct5c** (`research/runs/oct5c.tsv`, 13 experiments, then the 14th agent stalled and the batch stopped) ran on a re-scoped exam: `prepare.py` now asks the baseline rules once per run and removes everything they lock from every suite, because rules run first in the app and a copy they lock never reaches Jewel. The rules take 110 of the 249 fresh passwords (every one with a symbol, so all the CamelCase-word passwords), 104 of the 128 benchmark keys, 54 of the 5,567 real passwords and 1 everyday copy. What is left (5,513 real passwords, 159 everyday copies, 139 fresh, 24 benchmark keys, 50 look-alikes, 228 repo tokens, 23 history items) is what only Jewel can catch. The floors and caps are now read from `models/jewel-1.json` at load (its recall and false alarms on this exam at its own 94% threshold: fresh 137 of 139, benchmark 24 of 24, look-alikes 8 of 50, repo 1 of 228), so they move when a new model ships. Training data is cleaned against the exam inside the frozen file; the leak check covers every training text.

| Step | Change | Everyday locked (of 159) | Look-alikes (of 50) | Repo (of 228) | KB |
| - | - | - | - | - | - |
| start | run oct5b's recipe on this exam | 20, guards broken | 11 | 0 | 141 |
| 1 | 400 numbered lowerCamel identifier negatives (`launchDenver3`: the one shape behind 5 of the 11) | 22 | 6 | 0 | 151 |
| 2 | product-model pattern with the exam's own suffixes deleted; 300 CamelCase-word positives replaced by random letters whose case comes in runs; 200 dashed pronounceable positives | 18 | 2 | 0 | 122 |
| 3 | every short exam token (`Pro`, `At`, `pm`, `INV/ORD/PO/CASE`) out of the everyday generator | 18, honest | 2 | 0 | 118 |
| **hand** | **`runs` feature: the whole shape collapsed into runs (`Thursday2026` → `Aa9`, `kal73mor` → `a9a`) as one more gram** | **15** | 2 | 0 | 113 |

Fresh 137 of 139 and benchmark 24 of 24 held at every kept step (they are inside the metric). The candidate's threshold is 0.8145, real-password recall 94% by construction, AUC real passwords vs everyday 0.972 (Jewel 1: 0.826); `runtime/parity.ts` reproduces it in TypeScript.

What this round says:

1. **The look-alike cap was one shape.** Five of the eleven locked look-alikes were lowerCamel identifiers ending in a digit; 400 negatives of that shape fixed the cap and 800 did no more, while every digit-ended negative erodes the real-password tail in proportion to its dose. Smallest dose that holds the cap.
2. **The CamelCase positives were a hidden cost** of the whole oct5b line: they held the fresh floor through whole words, which lifted every CamelCase everyday copy and the `@handle` look-alikes. Random letters with case drawn in runs defend the same fresh items without words. Now that the rules lock CamelCase-word passwords, that kind is out of Jewel's exam altogether.
3. **Tokens, not shapes, again.** The reviewer found short exam tokens under the peek check's four-letter floor (`Pro`, `Max`, `At`, `pm`, the `INV/ORD/PO/CASE` prefixes), inherited from `bench/loop.py`'s generator. Swapping `Pro/Max` alone sent product names back from 6 to 9 (that gain was the token); removing all of them left 18 of 159 unchanged (the rest is shape). The honest generator is the kept state.
4. **Negative mass slides the threshold.** Under balanced class weights, an eight-digit date tag (`Launch20260514`) unlocked one copy and locked two more, because 40% of the real passwords just under the threshold carry eight digits (birth dates, phone numbers).
5. **The `runs` feature is a small, real gain, and a lesson in scaling.** As one strong whole-string feature (value 1 after normalisation) plus a length-bucketed one it was a disaster: 59 of 159, the model memorised the training generators' signatures. Counted like any other gram it gives 18 → 15 with AUC up and the model smaller. Two items is inside the noise of 159, so it is kept on the AUC and the size, not the count.
6. **The loop stalled on the environment, not the research.** Two runs took 32 minutes of wall clock for 18 seconds of CPU (a hang in the GitHub stream or the Node rules call; all stages take under 3 seconds when measured alone), which is what the stalled agent was waiting on. `prepare.py` now has a 120-second deadline with one retry on the stream, a 120-second timeout on the rules call, and prints per-stage load times.

**Is the loop worth its cost?** Three runs: 35 experiments, about 7 million agent tokens, 14 hours of wall clock, 61 → 15 everyday copies locked with nothing below Jewel 1. Training is 17 seconds per run; nearly all the time is the agent reading and reasoning. It found what a grid would not (the digits-inside password shape, the prose lines' job, the CamelCase cost, two exam leaks, token-specific gains), and the adversarial reviewer paid for itself twice. It cannot touch structure (features, model class, rules, the exam), which is where this round's hand experiment and the next gains live. Use it as a lab assistant for recipe tuning when the exam or the features change, overnight, with dose sweeps inside one experiment (now in `program.md`); do structure by hand.

**Jewel 2** (exported 2026-10-07 as `models/jewel-2.json` from `research/out/candidate.json`; parity 693 texts, 0 differing decisions): boundary markers, no dense features, `runs` on, 7,518 weights, 113 KB, threshold 0.8145. On the copies the baseline rules leave to Jewel: 15 of 159 everyday copies locked (Jewel 1: 61), 94% of real human passwords, 137 of 139 fresh, 24 of 24 benchmark keys, 2 of 50 look-alikes, 0 of 228 repo tokens, 3 of 23 unlocked history items (Jewel 1: 8 at 0.5). On the owner's unlocked single-token history (38 items, 15 of which the rules lock) it locks the same 3 as Jewel 1, all symbol-bearing password shapes. Left before the app's production: the staging run. Still open: product names 5 of 20 and the two report tags; `version_platform` 2 of 16.

## Round 8 (2026-11-11): Jewel 3, trained on public text only

Jewel 1 and 2 learned their harmless text from the owner's private repos, so neither can be published. Jewel 3 replaces that text with 39,248 lines from 14 public, permissively licensed repos (list, commits and licenses: [public-negatives.md](public-negatives.md)). The exam's repo suite was redrawn from the same text (317 tokens, was 228); the caps come from scoring the shipped model on it, so the comparison stays fair. Run as one headless experiment (Fable 5.2, `exp/public-negatives`): the unchanged recipe locked 21 everyday copies; two dose changes in `research/train.py` won them back (case-run alnum positives 400 → 800, `GIVEN_WEIGHT` 3 → 2).

`research/prepare.py` fix (owner approved): the saved threshold is now rounded down. Rounding to nearest put it just above the item that sets t94, so the file caught 136 of 139 fresh while the exam measured 137.

| On the rebuilt exam | Jewel 2 | Jewel 3 |
| - | - | - |
| Everyday copies locked (fp94) | 16/160 | 16/160 |
| Real passwords caught (5,511) | 94.0% | 94.3% |
| Fresh passwords | 137/139 | 137/139 |
| Benchmark keys | 24/24 | 24/24 |
| Look-alikes locked | 2/50 | 2/50 |
| Repo tokens locked | 1/317 | 0/317 |
| Owner's history (9 unlocked gated items) | 2 | 4 |

The two extra history locks are both things worth locking (a key-shaped token and a temporary login code). **Jewel 3** (exported 2026-11-11 as `models/jewel-3.json`; parity 693 texts, 0 differing decisions): same features as Jewel 2, 8,474 weights, 127 KB, threshold 0.7949. Never worse than Jewel 2 on anything measured, and publishable. Margins are one item; a rerun on other repo draws would size the noise. Left before the app's production: the staging run.

## Blind test with other people's generators (2026-10-05)

Generators we didn't write: Apple's own strong-password generator (`SecCreateSharedWebCredentialPassword`, the one Safari and Passwords use; 50 passwords) and `openssl rand -base64` (50). Before: rules 0 and 19, Jewel 35 (70%) and 50 (100%). Apple's real format is four groups of three (`nbB-Pdv-v3v-WUc`), which none of our generators made, so Jewel only half-recognized it. A rule for Apple's format (four groups of three, or three of six, with a digit, a capital and a lowercase letter) now locks all 50, with no new false alarms on the benchmark or the owner's history. Lesson: the generators must copy real formats exactly, so every password manager's real output goes into the corpus.

## Off-the-shelf local Jev alternatives (checked 2026-10-05)

The Jev Decision Index (huggingface.co/spaces/multimodalart/jev-decision-index) benchmarks 70 open Jev-style models against Jev 1.13 on 43 general decision tasks. **None is under 50M parameters.** The smallest are GLiNER 2.5 small (74M, skill score 3.8), Julia 1 (141M, 5.5), Verdict (151M, 1.9) and Laya (421M, 6.0), against Jev's 57.9. Good scores start around 2B parameters (Decider 2B, 29.0), and the best open ones are 26-31B (about 57). Also checked: Kev (0.8-9B), Lev (Interfaze, 4B; franckverrot/lev, 350M), OpenJev (151M up to 26B). General decision models can't be small; a single-question model like ours can.

## What round 1 said

1. **Our rules are the strongest single checker** (83% caught, no false alarms after the fix below), and they're instant. Nothing else should replace them.
2. **Jev's production setting is too strict.** At 0.8 it catches only 47%; at 0.5 it catches 77% with still no false alarms. Rules plus Jev at 0.5 is the best combination (90.5%), so a threshold of 0.5 is the better setting for a hosted check.
3. **credline (credential-line-32m) is the best local second layer.** Rules plus credline catches 88.4% with one false alarm, in about 2 ms per copy on the Mac, and adds 128 MB to the app. It's the only checker that caught some passphrases.
4. **OpenAI's privacy-filter isn't worth it here:** about 1 GB, 33 ms per copy, and 16 false alarms (ids, paths, dates).
5. **Everyone misses word-based passwords** like `Maple_Quartz1` or `lanternpickle520` and most passphrases. That's the gap to close, probably with a rule for word-plus-digit shapes, which needs care to avoid locking ordinary identifiers.
6. **Bug fixed during the run:** "Your password is incorrect." was locked because the full stop hid the exception for "incorrect".
