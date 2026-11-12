# /// script
# requires-python = ">=3.11"
# dependencies = ["scikit-learn", "numpy", "scipy"]
# ///
"""Learning curve for Jewel: how much training data until it stops helping?

    npx tsx bench/run.ts export-train   # out/train.jsonl (12 seeds)
    uv run bench/curve.py

Trains on 1, 2, 4, 8 and 12 seeds' worth of fake positives (each seed ~199), and
on growing amounts of harmless repo text, then scores the 300 fresh passwords
(out/holdout-fresh.jsonl) and counts extra locks on the local history (counts only).
"""
import json, os, sqlite3, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from sklearn.linear_model import LogisticRegression
from jewel import gated, matrix

OUT = Path(__file__).resolve().parent / "out"
load = lambda n: [json.loads(l) for l in (OUT / n).read_text().splitlines() if l.strip()]
train, negs = load("train.jsonl"), [n["text"] for n in load("negatives.jsonl")]
fresh = [r["text"] for r in load("holdout-fresh.jsonl")]
rule_ids = set(json.loads((OUT / "holdout-rules.json").read_text())["history"])
hist = []
_h = os.environ.get("JEWEL_HISTORY_JSONL", "")
_lines = [l for l in Path(_h).read_text().splitlines() if l.strip()] if _h and Path(_h).exists() else []
for i, l in enumerate(_lines):
    r = json.loads(l)
    if r.get("text") and not r.get("sensitive") and f"h:{i}" not in rule_ids:
        hist.append(r["text"])
seeds = sorted({c["id"] for c in train} and set(range(12)))
per_seed = len(train) // 12
print("| Fake passwords (positives) | Harmless lines | Fresh caught (of 300) | Extra locks on history |")
print("| - | - | - | - |")
for n_seeds, n_negs in [(1, 39497), (2, 39497), (4, 39497), (8, 39497), (12, 39497), (12, 2000), (12, 10000), (12, 20000)]:
    t = train[: per_seed * n_seeds]
    X = [c["text"] for c in t] + negs[:n_negs]
    y = [int(c["locked"]) for c in t] + [0] * n_negs
    m = LogisticRegression(C=4.0, max_iter=3000, class_weight="balanced").fit(matrix(X), y)
    pf = m.predict_proba(matrix(fresh))[:, 1]
    ph = m.predict_proba(matrix(hist))[:, 1]
    caught = sum(1 for s, x in zip(pf, fresh) if s >= 0.5 and gated(x))
    extra = sum(1 for s, x in zip(ph, hist) if s >= 0.5 and gated(x))
    print(f"| {sum(c['locked'] for c in t)} | {n_negs} | {caught} | {extra} |")
