# Jewel autoresearch

An agent does Jewel's research: it changes `research/train.py`, runs it, keeps the change if the model got better on a frozen exam, reverts it if not, and repeats, for as long as it is left running. The design is Karpathy's [autoresearch](https://github.com/karpathy/autoresearch) (March 2026): one file the agent edits, one file it never edits, one metric, a log of every try. Humans edit this file to steer the research; the agent reads it and goes.

## Setup

Before the first experiment, with the human:

1. **Agree on a run tag** from today's date (e.g. `oct5`). The branch `autoresearch/<tag>` must not exist yet.
2. **Create the branch**: `git checkout -b autoresearch/<tag>`. The working tree may hold other uncommitted work; leave it alone (see "Git, safely").
3. **Read the in-scope files**: `README.md` and `docs/benchmark.md` (what Jewel is and what we already know), `research/prepare.py` (the exam, the metric, the limits: read-only), `research/train.py` (the file you edit), `runtime/jewel.ts` (what the shipped runtime can compute).
4. **Check the data**: `uv run research/prepare.py` loads every suite, asks the baseline rules once (`npx tsx bench/rules-stdin.ts`, so Node is needed) and prints the sizes and the floors. If it asks for `bench/out/negatives.jsonl`, the human builds it (README, step 2).
5. **Create `research/results.tsv`** with just the header row (below). The baseline is logged after the first run.
6. **Confirm and go.**

## Experimentation

Each run is `uv run research/train.py`: it trains, scores the pruned model on the exam, and prints a summary. A run takes about 15-30 seconds; the hard limit is 300 seconds in all.

**Sweeps count as one experiment.** Training is cheap and your thinking is not: when an idea has a dose or a knob (how many of a pattern, `C`, a weight), try three or four values in one run (`for dose in (200, 400, 800): ...`), call `prepare.evaluate` for each (every call prints a summary; the last one is what the log reads, so end with the best setting re-run or ordered last), and log the best as the experiment, naming the values tried in the description. Keep the whole run under the time limit.

**You can:** edit `research/train.py`, and only that file. Everything in it is fair game: which fake passwords and how many, generated negatives (everyday-shaped copies the model must leave alone), class or sample weights, the feature configuration, the linear model and its regularisation, the pruning threshold.

**You cannot:**
- Edit `research/prepare.py`, `bench/jewel.py`, `bench/everyday.json`, `bench/holdout.py`, `bench/dataset.ts` or anything under `runtime/`. The exam is the ground truth; the feature code is the runtime's contract.
- Add dependencies. scikit-learn, numpy and scipy are what there is.
- Change what the model computes beyond the `FEATURES` knobs (`char_n`, `shape_n`, `boundary`, `dense`, `dim`) or ship anything but a linear model over those hashed features: that is what `runtime/jewel.ts` can run. An idea that needs new feature code or a non-linear model is worth writing down in the results description, not trying here.
- Read the exam into training. Never load `bench/everyday.json`, `bench/holdout.py`'s generators or `bench/out/dataset.jsonl` in `train.py`, and never use their words in a generator: `prepare.evaluate` fails a run whose added training texts appear in the exam (`leak`) or use exam words (`peek`, it names them). Wrap new generated data in `prepare.clean()` to drop accidental exact matches.
- Touch real secrets. Training data is generated or comes from our repos' text (`prepare.train_negatives()`). The real passwords in the exam are streamed into memory by `prepare.py` and must never be written, cached, printed or looked at; the owner's history is counts only. Print no text from any suite.

**The exam is Jewel's actual job.** the baseline rules run before Jewel in the app, so `prepare.py` asks the rules once and removes everything they lock from every suite (the summary's `rules_first` line says how much: about 110 of the 249 fresh passwords, 104 of the 128 benchmark keys, 1% of the real passwords, 1 everyday copy). What remains is what only Jewel can catch: human passwords, generated passwords with no symbol, unprefixed tokens, and the harmless copies that look like them.

**The goal is simple: get the lowest `fp94`.** At the threshold that catches 94% of the real passwords in the exam, and never fewer of the other passwords than the shipped model catches at its own 94% threshold (the `floors` line: `models/jewel-1.json` today, computed at load, so they move when a new model ships), how many of the 159 everyday copies lock? Lower is better. The threshold is the lowest of the three (`t94_from` says which one binds), so recall never falls below the shipped model on any suite: a change that scores password-manager strings lower pays for it in `fp94` instead of hiding the loss. That threshold ships inside the candidate.

**Limits** (`limits_ok` in the summary says whether they hold): the model JSON stays at or under 1 MB (Jewel 1 is 77 KB; size is not a worry below that, so never trade accuracy for bytes), scoring stays under 1 ms per text in Python, the run finishes within 300 seconds, `leak` and `peek` are 0. A run that breaks a limit is discarded whatever its `fp94`.

**Guards** (`guards_ok`): false alarms on the other harmless suites must not exceed the shipped model's at its threshold (the `floors` line's caps: benchmark look-alikes 8 of 50, `bench_neg_fp94`; held-out repo tokens 1 of 228, `repo_fp94`). A run that breaks a guard is discarded whatever its `fp94`. `history94` (the owner's unlocked single-token copies, labels unknown) is information. `kb` is the size.

Nothing we measure may get worse than the shipped model: recall floors sit inside the metric, false-alarm caps are guards. The only number that moves is `fp94`, downwards.

**Simplicity criterion:** all else being equal, simpler is better. A small gain that adds ugly code is not worth it; removing something and getting equal or better results is a win. An `fp94` improvement of one item (0.00625) that adds twenty lines? Probably not. The same from deleting code? Keep.

**Resolution:** 160 everyday items means one item is 0.00625 of `fp94`. Keep only strict improvements; a one-item gain is real but small, so prefer it when the change is also simple.

**The first run** is the baseline: run `train.py` unchanged and log it as `keep`. If the baseline itself breaks a guard (it can, when the exam or the floors changed since the recipe was found), restoring the guards is the first goal: the first run with `guards_ok` yes is kept whatever its `fp94`, and from then on the normal rule applies against the best kept row that had `guards_ok` yes.

## Output format

The run ends with a summary like this (`---` then one key per line):

```
fp94:             0.125786
everyday_locked:  20/159
t94:              0.7221
t94_from:         fresh (wild 0.7694, fresh 0.7221, bench 0.8005)
wild_recall_t:    0.9494
wild_recall_05:   0.9735
wild_n:           5513
fresh94:          0.9856 (137/139 gated)
bench_pos94:      1.0000 (24/24)
bench_neg_fp94:   0.2200 (11/50)
repo_fp94:        0.0000 (0/228)
history94:        3/23 (at 0.5: 6)
auc:              0.9623
weights:          9352
kb:               140.6
train_seconds:    14.4
total_seconds:    15.0
ms_per_text:      0.041
leak:             0
peek:             0
limits_ok:        yes
guards_ok:        no (bench_neg 11 > 8)
floors:           jeweler-v1.json at its t94 0.8093: fresh 135/139, bench 24/24; caps look-alikes 2/50, repo 0/317
rules_first:      removed by the baseline rules: wild 54/5567, everyday 1/160, fresh 110/249, bench_pos 104/128, bench_neg 0/50, repo 0/228, history 15/38
everyday_by_kind: word_year 0/12 | report_tag 3/12 | ...
fresh_by_kind:    safari 12/12 | ...
```

Read the key numbers out of the log without flooding your context:

```
grep -E "^(fp94|fresh94|kb|limits_ok|guards_ok|everyday_locked|t94|t94_from|bench_neg_fp94|repo_fp94|history94|everyday_by_kind|fresh_by_kind):" research/run.log
```

## Logging results

Every experiment gets one row in `research/results.tsv` (tab-separated, no tabs or commas inside the description). Six columns:

```
commit	fp94	fresh94	kb	status	description
```

1. git commit hash, short (7 characters)
2. `fp94` (e.g. `0.381250`); `1.000000` for a crash
3. `fresh94`, the first number only (e.g. `0.8835`); `0.0000` for a crash
4. `kb` (e.g. `75.9`); `0.0` for a crash
5. status: `keep`, `discard` or `crash`
6. what the experiment tried, in a few words

Example:

```
commit	fp94	fresh94	kb	status	description
a1b2c3d	0.381250	0.8835	75.9	keep	baseline (Jewel 1 recipe)
b2c3d4e	0.300000	0.8795	80.2	keep	1500 generated everyday-shaped negatives
c3d4e5f	0.393750	0.8835	75.9	discard	C=1
d4e5f6g	1.000000	0.0000	0.0	crash	class_weight dict with a typo
```

`results.tsv` stays untracked during the run and is committed when the run is written up.

## The experiment loop

On the branch `autoresearch/<tag>`, LOOP FOREVER:

1. Look at the git state: `git branch --show-current` and `git log --oneline -5 -- research/train.py`.
2. Change `research/train.py` with one experimental idea. One idea per run, so the log says what mattered.
3. Commit only that file: `git commit -m "<what you tried>" -- research/train.py`. Note the hash: `git rev-parse --short HEAD`.
4. Run it: `uv run research/train.py > research/run.log 2>&1` (redirect everything; never tee the output into your context).
5. Read the results with the grep above.
6. If the grep prints nothing, the run crashed: `tail -n 40 research/run.log`, fix anything dumb (a typo, an import) with `git commit --amend --no-edit -- research/train.py`, rerun. If the idea itself is broken, log `crash` and revert.
7. Append the row to `results.tsv`.
8. If `limits_ok` and `guards_ok` are both `yes` and `fp94` is strictly lower than the best kept `fp94` among rows that had `guards_ok` yes (or no such row exists yet): keep. The branch advances. Write `guards no` in the description of any row that failed them.
9. Otherwise revert: `git reset --soft HEAD~1 && git checkout HEAD -- research/train.py`. Only that file moves; nothing else in the working tree changes.

If you feel stuck, rewinding to an older kept commit is allowed but should be rare. Combine near misses, revisit a discarded idea at another dose, try the levers below in another order.

**Timeout:** a run should take under a minute. Over 300 seconds (`total_seconds`, or no summary after six minutes of wall clock), kill it and treat it as a failure. If a fit that used to take seconds takes minutes, note `train_seconds` in the description: that is a finding (ill-conditioned data), not a limit to wait out.

**Crashes:** easy and dumb, fix and rerun; fundamentally broken, log `crash` and move on.

**NEVER STOP.** Once the loop has begun, do not pause to ask whether to continue. The human may be asleep and expects the loop to run until they stop it. Out of ideas? Reread the summary per kind (`everyday_by_kind`, `fresh_by_kind`), reread `docs/benchmark.md` and `docs/corpus.md`, combine near misses, try more radical data changes.

## Git, safely

The working tree may carry uncommitted work that is not yours. So: never `git add -A`, `git stash`, `git reset --hard` or `git checkout <branch>` in this loop. Commit and revert with the path-limited commands above, which touch `research/train.py` and nothing else. The human merges the branch when the run is written up.

## What we already know (so you don't redo it)

- `docs/benchmark.md` round 5 and `docs/loop.md`: 84 variants on the same exam. **Features barely matter; data does.** Seven feature configurations land within noise of each other. Everyday-shaped negatives are the lever and a trade: 500 of them took everyday false alarms from 37.5% to 24% and wild recall from 93.9% to 89.7%; 3,000 gave 15% and 81%. At equal (94%) recall the best variant locked 26% of everyday copies against Jewel 1's 39%. `bench/loop.py` has a generator (`everyday_train`, word list `EW`) you may copy, except that five of its words are exam words; `peek` will name them.
- What Jewel 1 locks that it should not: 12/12 word+year (`Thursday2026`), 11/12 report tags (`Q3Report2026`), 15/20 product names, 8/16 CamelCase phrases, 7/16 version strings. What it misses: CamelCase word passwords (`fresh_by_kind` memorable_caps 0/25), plain-word passwords.
- About 97% of the repo text is multi-token, which the gate never shows the model. The gate (`jewel.gated`) is fixed; what you train on is not.
- `docs/corpus.md` lists password kinds marked "add" that no generator makes yet (CamelCase words, keyboard walks, name + year, leetspeak, pronounceable, non-English); each is a few lines of Python.
- Two thirds of real human passwords have the `Word+digits` or `lower+digits` shape, which is exactly the everyday shape. The exam rewards whatever separates `Thursday2026` from `thursday26!`: digits count, year-ness, capitalisation, symbol, word-likeness. The model can only learn those from data that shows the contrast.

- Run `oct5` (`research/runs/oct5.tsv`, 6 experiments under an earlier rule that only watched fresh recall): everyday-shaped negatives alone slid the threshold down (fp94 0.381 to 0.338, but repo and look-alike false alarms up); boundary markers on and dense features off then helped (0.269); **2,000 human-shaped positives (lowercase word+digits, name+birth year, keyboard walks, Capitalised+digits+symbol) were the big win** (0.188: the wild passwords mostly have that shape and dataset.ts barely makes it), at the cost of 15 fresh passwords, which is why the floors now sit inside the metric; 1,000 random positives over all ASCII punctuation fixed most of that loss (repo code had taught the model that `- , ; / ( )` mean "not a password"). Final kept state: 0.175 (28 of 160), 121 KB, fresh 214 of 249, benchmark 127 of 128. Under the current rule that state's threshold would have to drop to the fresh floor, so redo the path in an order that never dips.

- Run `oct5b` (`research/runs/oct5b.tsv`, 16 experiments under the floors rule, before the exam was scoped to the rules' misses): the whole oct5 recipe as one step (32 of 160), product-model and platform-version negatives (30), CamelCase-word positives with the look-alikes weighted up (24, flattered: 153 given rows were exam texts, found by the reviewer, and that step re-scores at 27 with both caps broken), then the honest base plus **1,000 pronounceable positives and 800 positives with digits inside short letter runs (the shape of the real passwords nearest the threshold: `kal73mor`, not `monkey12`)** and `@CamelCase` handle and `word++;` negatives: 19 of 160, fresh 221/249, caps held. Discards: letters-only negatives, weighting the human positives or the tag-shaped negatives (each slid the wild threshold and tripped the repo cap), dropping the multi-line repo lines (repo tokens 1 to 9: the prose teaches code punctuation). `train.py` starts from that end state. On the rules-first exam it scores 20 of 159 with look-alikes at 11 of 50 against a cap of 8, so the first job is the cap. CamelCase-word passwords are no longer in the exam (the rules lock them: symbol plus digit), so the camel positives may be dead weight now.

## Levers in `train.py`

Data: everyday-shaped negatives (patterns, word lists disjoint from the exam, dose), new positive kinds, dropping or down-weighting multi-token negatives, deduplication, sample weights, class weights, more seeds of `bench/dataset.ts` (`npx tsx bench/run.ts export-train` writes 12; the generator is in `bench/dataset.ts`, read-only, but you can call its output, and 50 seeds cost nothing). Features: the five knobs plus `runs` (the whole shape collapsed into runs as one more gram, added by hand on 2026-10-06: 18 to 15 of 159; try it off and on with any big data change). Model: `C`, `class_weight`, solver, `SGDClassifier` or `LinearSVC` with calibration (still linear). Pruning: `PRUNE`.
