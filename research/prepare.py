# /// script
# requires-python = ">=3.11"
# dependencies = ["scikit-learn", "numpy", "scipy"]
# ///
"""Autoresearch for Jewel, the frozen half: the exam, the one metric and the limits.

Autoresearch (Karpathy, March 2026, github.com/karpathy/autoresearch): an agent edits
one file (train.py), runs it, keeps the change if the metric improved, reverts it if
not, and loops all night. This is the file the agent never edits. It loads the frozen
test sets, scores a candidate exactly as the shipped TypeScript runtime would (the
pruned, rounded weights), and prints the summary every run ends with. Humans edit it,
to grow the exam; the agent only reads it. The agent's instructions are program.md.

    uv run research/prepare.py        # one-time: check the data, describe the exam

The exam (the same for every candidate), after the baseline rules have had their turn:
rules run before Jewel in the app, so every text the rules lock is removed from every
suite (asked once per run through bench/rules-stdin.ts, in memory). What is left is
Jewel's actual job.
- wild: every 100th gated line (CRC32) of the public 000webhost password list,
  streamed from GitHub into memory and never written: about 5,500 real human
  passwords. They set the threshold.
- everyday: bench/everyday.json, 160 hand-written ordinary copies that must stay
  unlocked (Thursday2026, iPhone17Pro, node_modules). The metric is measured here.
- fresh: passwords from 12 generators the trainer never saw (bench/holdout.py, seeded).
- bench: bench/dataset.ts with the test seed; the cases that pass the gate.
- repo: single-token lines of our repos' text that pass the gate, held out of the
  training negatives (crc32 % 4 == 0): identifiers, flags, fragments developers copy.
- history: the owner's copy history export, read-only, counts only (skipped when they are
  absent or JEWEL_HISTORY=0). The agent never sees this text, so it cannot fit it.

The metric, fp94: the share of everyday copies scoring at or above t94, the threshold
that keeps 94% recall on the wild passwords and never fewer of the other passwords
than the shipped model (SHIPPED) catches at its own 94% threshold. Those floors, and
the caps on look-alike and repo false alarms, are computed from the shipped model file
at load, so they move when a new model ships. Lower is better. A change that scores
passwords lower pays for it in fp94 instead of hiding the loss; a change that locks
more harmless look-alikes than the shipped model is discarded. The candidate's
exported threshold is t94, so an app that locks at it gets 94% of real passwords by
construction.

Training data is cleaned against the exam here: train_cases() and train_negatives()
never contain an exam text, and evaluate() fails a run whose training texts do.
"""
from __future__ import annotations

import json
import os
import re
import sqlite3
import subprocess
import sys
import time
import urllib.request
import zlib
from datetime import date
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
BENCH, OUT, RESEARCH = ROOT / "bench", ROOT / "bench" / "out", ROOT / "research"
sys.path.insert(0, str(BENCH))
from jewel import DEFAULT_FEATURES, gated, matrix  # noqa: E402  (frozen: runtime/jewel.ts computes exactly this)

# ---- constants (fixed; the agent does not change them) ----
RECALL = 0.94          # wild recall every candidate is held to
WILD_EVERY = 100       # every Nth gated line of the list is the sample
WILD_URL = "https://raw.githubusercontent.com/danielmiessler/SecLists/master/Passwords/Leaked-Databases/000webhost.txt"
TIME_LIMIT = 300       # seconds for all of train.py, training and exam together
KB_LIMIT = 1000        # model JSON hard cap (Jewel 1: 77 KB): size is not a worry below this
MS_LIMIT = 1.0         # scoring time per text in Python; the TypeScript runtime is faster
REPO_HOLDOUT_MOD = 4   # gated repo lines with crc32 % 4 == 0 are exam, the rest are training
SHIPPED = ROOT / "models" / "jeweler-v1.json"  # the shipped model, whose numbers are the floors and caps (newest models/jeweler-v<n>.json)
# Optional: your own copy history, as a JSONL export ({"text": ..., "sensitive": true|false} per line). Read-only,
# in memory, counts only.
HISTORY = os.environ.get("JEWEL_HISTORY_JSONL", "")

log = lambda *a: print(*a, file=sys.stderr, flush=True)


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(l) for l in Path(path).read_text().splitlines() if l.strip()]


STAGE: dict[str, float] = {}  # seconds per load stage, printed in the summary: a hang shows where it hung


def timed(name: str, fn):
    t = time.time()
    try:
        return fn()
    finally:
        STAGE[name] = round(time.time() - t, 1)


def wild_sample() -> list[str]:
    """Stream the public list; keep every WILD_EVERY-th gated line in memory. Nothing is written.
    A stalled stream (GitHub throttling) is abandoned after DEADLINE seconds and tried once more."""
    DEADLINE = 120
    for attempt in (1, 2):
        picked, total, t0 = [], 0, time.time()
        try:
            with urllib.request.urlopen(WILD_URL, timeout=30) as r:
                for raw in r:
                    line = raw.decode("utf-8", "replace").rstrip("\r\n")
                    total += 1
                    if gated(line) and zlib.crc32(line.encode()) % WILD_EVERY == 0:
                        picked.append(line.strip())
                    if total % 50000 == 0 and time.time() - t0 > DEADLINE:
                        raise TimeoutError(f"stream too slow: {total:,} lines in {time.time() - t0:.0f}s")
            if len(picked) < 1000:
                raise RuntimeError(f"wild sample too small ({len(picked)} of {total} lines)")
            return picked
        except (TimeoutError, OSError, RuntimeError) as e:
            log(f"wild stream attempt {attempt} failed: {e}")
            if attempt == 2:
                raise
    raise RuntimeError("unreachable")


def rules_lock(texts: list[str]) -> list[bool]:
    """the baseline rules, asked once, in memory (bench/rules-stdin.ts): true where the rules lock the text."""
    r = subprocess.run(["npx", "--no-install", "tsx", str(BENCH / "rules-stdin.ts")], input=json.dumps(texts), capture_output=True, text=True, check=True, cwd=ROOT, timeout=120)
    return json.loads(r.stdout)


def repo_split() -> tuple[list[str], list[str]]:
    """Our repos' harmless text: (training negatives before cleaning, held-out gated tokens for the exam)."""
    negs = [n["text"] for n in load_jsonl(OUT / "negatives.jsonl")]
    hold = sorted({t.strip() for t in negs if gated(t) and zlib.crc32(t.strip().encode()) % REPO_HOLDOUT_MOD == 0})
    holdset = set(hold)
    return [t for t in negs if t.strip() not in holdset], hold


def history_texts() -> list[str] | None:
    """Unlocked gated items from the owner's local copy history export, in memory only."""
    if os.environ.get("JEWEL_HISTORY", "1") == "0":
        return None
    if not HISTORY or not Path(HISTORY).exists():
        return None
    rows = [json.loads(l) for l in Path(HISTORY).read_text().splitlines() if l.strip()]
    texts = [r["text"] for r in rows if r.get("text") and not r.get("sensitive")]
    return [t.strip() for t in texts if gated(t)]


_EXAM: dict | None = None
RULES_REMOVED: dict[str, str] = {}


def exam() -> dict:
    """Every frozen suite, loaded once per process, with the rules' locks removed."""
    global _EXAM
    if _EXAM is None:
        bench = [c for c in load_jsonl(OUT / "dataset.jsonl") if gated(c["text"])]
        fresh = [c for c in load_jsonl(OUT / "holdout-fresh.jsonl") if gated(c["text"])]
        raw = {
            "wild": timed("wild", wild_sample),
            "everyday": json.loads((BENCH / "everyday.json").read_text())["items"],
            "fresh": fresh,
            "bench_pos": [c["text"] for c in bench if c["locked"]],
            "bench_neg": [c["text"] for c in bench if not c["locked"]],
            "repo": timed("repo", lambda: repo_split()[1]),
            "history": timed("history", history_texts),
        }
        text_of = lambda x: x["text"] if isinstance(x, dict) else x
        flat = [text_of(x) for k, v in raw.items() if v for x in v]
        locked = iter(timed("rules", lambda: rules_lock(flat)))
        ex = {}
        for k, v in raw.items():
            if not v:
                ex[k] = v
                continue
            keep = [x for x in v if not next(locked)]
            RULES_REMOVED[k] = f"{len(v) - len(keep)}/{len(v)}"
            ex[k] = keep
        _EXAM = ex
    return _EXAM


def exam_texts() -> set[str]:
    ex = exam()
    return {(x["text"] if isinstance(x, dict) else x).strip() for v in ex.values() if v for x in v}


def train_cases() -> list[dict]:
    """bench/out/train.jsonl (12 seeds of bench/dataset.ts) minus every case whose text is in the exam."""
    bad = exam_texts()
    return [c for c in load_jsonl(OUT / "train.jsonl") if c["text"].strip() not in bad]


def train_negatives() -> list[str]:
    """What train.py may use as harmless text: our repos' lines, the exam's held-out tokens and any exam text removed."""
    bad = exam_texts()
    return [t for t in repo_split()[0] if t.strip() not in bad]


def clean(texts: list[str]) -> list[str]:
    """Drop any training text that is also in the exam (exact match), so a new generator can't leak by chance."""
    bad = exam_texts()
    return [t for t in texts if t.strip() not in bad]


def _words(text: str) -> set[str]:
    return {w.lower() for w in re.findall(r"[A-Z]?[a-z]{4,}|[A-Z]{5,}", text)}


def test_words() -> set[str]:
    """Words of the everyday list and of the fresh generators: a trainer that uses them is peeking."""
    from holdout import WORDS as fresh_words  # bench/holdout.py
    ws = set(w.lower() for w in fresh_words)
    for e in json.loads((BENCH / "everyday.json").read_text())["items"]:
        ws |= _words(e["text"])
    return ws


def scorer(weights: dict, bias: float, features: dict):
    """The shipped arithmetic: hashed features, pruned rounded weights, sigmoid."""
    w = np.zeros(features["dim"], dtype=np.float64)
    for k, v in weights.items():
        w[int(k)] = v

    def score(texts: list[str]) -> np.ndarray:
        if not texts:
            return np.zeros(0)
        return 1 / (1 + np.exp(-(matrix(texts, features) @ w + bias)))

    return score


_FLOORS: dict | None = None


def floors() -> dict:
    """The shipped model's counts on this exam at its own 94%-wild threshold: recall floors and false-alarm caps."""
    global _FLOORS
    if _FLOORS is None:
        ex = exam()
        j = json.loads(SHIPPED.read_text())
        score = scorer(j["weights"], j["bias"], j.get("features") or {**DEFAULT_FEATURES, "dim": j["dim"]})
        t = float(np.quantile(score(ex["wild"]), 1 - RECALL))
        n = lambda k, items: int((score([x["text"] if isinstance(x, dict) else x for x in items]) >= t).sum())
        _FLOORS = {"t": t, "fresh": n("fresh", ex["fresh"]), "bench_pos": n("bench_pos", ex["bench_pos"]), "bench_neg": n("bench_neg", ex["bench_neg"]), "repo": n("repo", ex["repo"])}
    return _FLOORS


def evaluate(weights: dict, bias: float, features: dict, train_texts: list[str], *, train_seconds: float, t_start: float) -> dict:
    """Score the pruned candidate on the exam and print the summary. `weights`: hashed index -> rounded weight, as shipped."""
    ex, fl = exam(), floors()
    score = scorer(weights, bias, features)
    everyday_texts = [e["text"] for e in ex["everyday"]]
    fresh_texts = [c["text"] for c in ex["fresh"]]
    p = {
        "wild": score(ex["wild"]), "everyday": score(everyday_texts), "fresh": score(fresh_texts),
        "bench_pos": score(ex["bench_pos"]), "bench_neg": score(ex["bench_neg"]), "repo": score(ex["repo"]),
        "history": score(ex["history"]) if ex["history"] else None,
    }
    kth = lambda a, k: float(np.sort(a)[::-1][k - 1]) if 0 < k <= len(a) else 0.0  # the threshold that still catches k of them
    t_wild, t_fresh, t_bench = float(np.quantile(p["wild"], 1 - RECALL)), kth(p["fresh"], fl["fresh"]), kth(p["bench_pos"], fl["bench_pos"])
    t94 = min(t_wild, t_fresh, t_bench)
    bound = "wild" if t94 == t_wild else "fresh" if t94 == t_fresh else "bench"
    at = lambda k: p[k] >= t94
    fp94 = float(at("everyday").mean())
    by_kind = lambda items, hits: " | ".join(f"{k} {sum(h for i, h in zip(items, hits) if i['kind'] == k)}/{sum(1 for i in items if i['kind'] == k)}" for k in dict.fromkeys(i["kind"] for i in items))
    from sklearn.metrics import roc_auc_score
    auc = float(roc_auc_score(np.r_[np.ones(len(p["wild"])), np.zeros(len(p["everyday"]))], np.r_[p["wild"], p["everyday"]]))

    # Honesty checks: no training text may be an exam text, and texts added beyond the given data may not use exam words.
    given = {c["text"] for c in train_cases()} | set(train_negatives())
    bad = exam_texts()
    leak = sum(1 for t in set(train_texts) if t.strip() in bad)
    added = {t for t in train_texts if t not in given}
    peek = sorted({w for t in added for w in _words(t) if w in TEST_WORDS})

    # The threshold is rounded down to 4 decimals: rounding up can drop the item that sets t94.
    cand = {"version": 0, "created": date.today().isoformat(), "dim": features["dim"], "features": features, "bias": bias, "threshold": int(t94 * 10000) / 10000, "weights": {str(k): v for k, v in sorted(weights.items(), key=lambda kv: int(kv[0]))}}
    (RESEARCH / "out").mkdir(exist_ok=True)
    (RESEARCH / "out" / "candidate.json").write_text(json.dumps(cand, separators=(",", ":")))
    kb = (RESEARCH / "out" / "candidate.json").stat().st_size / 1000
    t = time.perf_counter()
    for _ in range(3):
        score(everyday_texts)
    ms = (time.perf_counter() - t) * 1000 / (3 * len(everyday_texts))
    total = time.time() - t_start
    n = lambda k: len(ex[k])
    hit = lambda k: int(at(k).sum())
    cnt = lambda k: f"{hit(k)}/{n(k)}"
    guards = [r for ok, r in [(hit("bench_neg") <= fl["bench_neg"], f"bench_neg {hit('bench_neg')} > {fl['bench_neg']}"), (hit("repo") <= fl["repo"], f"repo {hit('repo')} > {fl['repo']}")] if not ok]
    reasons = [r for ok, r in [(total <= TIME_LIMIT, f"total_seconds {total:.0f} > {TIME_LIMIT}"), (kb <= KB_LIMIT, f"kb {kb:.0f} > {KB_LIMIT}"), (ms <= MS_LIMIT, f"ms_per_text {ms:.2f} > {MS_LIMIT}"), (leak == 0, f"leak {leak}"), (not peek, f"peek {len(peek)} words"), (len(train_texts) >= 1000, "fewer than 1000 training texts passed")] if not ok]
    hist = f"{hit('history')}/{len(ex['history'])} (at 0.5: {int((p['history'] >= 0.5).sum())})" if p["history"] is not None else "n/a"
    out = {
        "fp94": f"{fp94:.6f}", "everyday_locked": cnt("everyday"), "t94": f"{t94:.4f}", "t94_from": f"{bound} (wild {t_wild:.4f}, fresh {t_fresh:.4f}, bench {t_bench:.4f})",
        "wild_recall_t": f"{float(at('wild').mean()):.4f}", "wild_recall_05": f"{float((p['wild'] >= 0.5).mean()):.4f}", "wild_n": str(n("wild")),
        "fresh94": f"{float(at('fresh').mean()):.4f} ({cnt('fresh')} gated)", "bench_pos94": f"{float(at('bench_pos').mean()):.4f} ({cnt('bench_pos')})",
        "bench_neg_fp94": f"{float(at('bench_neg').mean()):.4f} ({cnt('bench_neg')})", "repo_fp94": f"{float(at('repo').mean()):.4f} ({cnt('repo')})",
        "history94": hist, "auc": f"{auc:.4f}", "weights": str(len(weights)), "kb": f"{kb:.1f}", "train_seconds": f"{train_seconds:.1f}", "total_seconds": f"{total:.1f}",
        "ms_per_text": f"{ms:.3f}", "leak": str(leak), "peek": f"{len(peek)}" + (f" ({' '.join(peek[:5])})" if peek else ""),
        "limits_ok": "yes" if not reasons else "no (" + "; ".join(reasons) + ")", "guards_ok": "yes" if not guards else "no (" + "; ".join(guards) + ")",
        "floors": f"{SHIPPED.name} at its t94 {fl['t']:.4f}: fresh {fl['fresh']}/{n('fresh')}, bench {fl['bench_pos']}/{n('bench_pos')}; caps look-alikes {fl['bench_neg']}/{n('bench_neg')}, repo {fl['repo']}/{n('repo')}",
        "rules_first": "removed by the baseline rules: " + ", ".join(f"{k} {v}" for k, v in RULES_REMOVED.items()),
        "load_seconds": ", ".join(f"{k} {v}" for k, v in STAGE.items()),
        "everyday_by_kind": by_kind(ex["everyday"], at("everyday")), "fresh_by_kind": by_kind(ex["fresh"], at("fresh")),
    }
    print("---")
    for k, v in out.items():
        print(f"{k + ':':<18}{v}")
    return {"fp94": fp94, "t94": t94, "kb": kb, "limits_ok": not reasons, "guards_ok": not guards, **{k: v for k, v in out.items() if k not in ("fp94",)}}


TEST_WORDS = test_words()


def main() -> None:
    """One-time prep: make sure the frozen files exist, then describe the exam."""
    need = {"dataset.jsonl": ["npx", "tsx", "bench/run.ts", "export"], "train.jsonl": ["npx", "tsx", "bench/run.ts", "export-train"], "holdout-fresh.jsonl": ["uv", "run", "bench/holdout.py", "gen"]}
    for f, cmd in need.items():
        if not (OUT / f).exists():
            log(f"making bench/out/{f}: {' '.join(cmd)}")
            subprocess.run(cmd, cwd=ROOT, check=True)
    if not (OUT / "negatives.jsonl").exists():
        sys.exit("bench/out/negatives.jsonl is missing: build it with bench/negatives.py and the rules filter (README, step 2), then rerun")
    t = time.time()
    ex, fl = exam(), floors()
    log(f"exam loaded in {time.time() - t:.1f}s, after the baseline rules removed what they lock ({', '.join(f'{k} {v}' for k, v in RULES_REMOVED.items())}):")
    log(f"  wild      {len(ex['wild']):,} real passwords (every {WILD_EVERY}th gated line, streamed, nothing written)")
    log(f"  everyday  {len(ex['everyday'])} hand-written copies that must stay unlocked")
    log(f"  fresh     {len(ex['fresh'])} gated passwords from 12 unseen generators")
    log(f"  bench     {len(ex['bench_pos'])} gated passwords and keys, {len(ex['bench_neg'])} gated look-alikes")
    log(f"  repo      {len(ex['repo'])} gated repo tokens held out; {len(train_negatives()):,} repo lines stay available for training; {len(train_cases()):,} given cases")
    log(f"  history   {len(ex['history']) if ex['history'] else 'skipped'} unlocked gated items from the owner's copy history export (counts only)")
    log(f"  test words {len(TEST_WORDS)} (everyday list + fresh generators) that no new training generator may use")
    log(f"floors from {SHIPPED.name} at its 94%-wild threshold {fl['t']:.4f}: fresh {fl['fresh']}/{len(ex['fresh'])}, bench {fl['bench_pos']}/{len(ex['bench_pos'])}; caps look-alikes {fl['bench_neg']}/{len(ex['bench_neg'])}, repo {fl['repo']}/{len(ex['repo'])}")
    log(f"limits: {TIME_LIMIT}s per run, {KB_LIMIT} KB model, {MS_LIMIT} ms per text; metric fp94 at {RECALL:.0%} wild recall")
    if not (RESEARCH / "results.tsv").exists():
        log("results.tsv is missing: the agent creates it at setup with the header\n  commit\tfp94\tfresh94\tkb\tstatus\tdescription")


if __name__ == "__main__":
    main()
