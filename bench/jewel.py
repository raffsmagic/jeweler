# /// script
# requires-python = ">=3.11"
# dependencies = ["scikit-learn", "numpy", "scipy"]
# ///
"""Jewel: logistic regression over hashed character n-grams.

    uv run bench/jewel.py [--history]

Trains on out/train.jsonl (generated with other seeds than the test set),
scores out/dataset.jsonl into out/jewel.jsonl for run.ts report, and writes the
weights to out/jewel-model.json (small enough to ship in the app and run in a
few lines of TypeScript). --history also reports how many items in the local
copy history export it would newly lock, printing only their shape (letters and
digits masked), never their text.

Features, all from the copied text alone:
- character 1-4 grams of the text, lowercased
- character 1-6 grams of its "shape" (a = lower, A = upper, 9 = digit, symbols kept)
- length, entropy, character classes, word count, and whether it has spaces
"""
from __future__ import annotations

import json
import os
import math
import re
import sqlite3
import sys
import time
import zlib
from pathlib import Path

import numpy as np
from sklearn.linear_model import LogisticRegression

OUT = Path(__file__).resolve().parent / "out"
DIM = 1 << 15
# Feature configuration. The defaults are Jewel 1 exactly; bench/loop.py tries
# others. Whatever ships is written into the model JSON and read by runtime/jewel.ts.
DEFAULT_FEATURES = {"char_n": 4, "shape_n": 6, "boundary": False, "dense": True, "dim": DIM}
# Optional "runs": the whole string's shape collapsed into runs (Thursday2026 -> Aa9, kal73mor -> a9a) as
# one more gram: the collocation a bag of short n-grams never sees. Absent in Jewel 1.


def shape(t: str) -> str:
    return re.sub(r"[0-9]", "9", re.sub(r"[A-Z]", "A", re.sub(r"[a-z]", "a", t)))


def entropy(t: str) -> float:
    if not t:
        return 0.0
    counts: dict[str, int] = {}
    for ch in t:
        counts[ch] = counts.get(ch, 0) + 1
    return -sum(n / len(t) * math.log2(n / len(t)) for n in counts.values())


def h(s: str, dim: int = DIM) -> int:
    return zlib.crc32(s.encode()) % dim


def features(text: str, cfg: dict | None = None) -> dict[int, float]:
    cfg = cfg or DEFAULT_FEATURES
    dim = cfg["dim"]
    t = text.strip()[:256]
    f: dict[int, float] = {}
    low, shp = t.lower(), shape(t)
    if cfg["boundary"]:  # so "starts with a digit" and "ends with digits" are learnable
        low, shp = "^" + low + "$", "^" + shp + "$"
    for n in range(1, cfg["char_n"] + 1):
        for i in range(len(low) - n + 1):
            k = h("c" + low[i:i + n], dim)
            f[k] = f.get(k, 0) + 1
    for n in range(1, cfg["shape_n"] + 1):
        for i in range(len(shp) - n + 1):
            k = h("s" + shp[i:i + n], dim)
            f[k] = f.get(k, 0) + 1
    if cfg.get("runs"):  # the whole shape as one gram, counted and normalised like the others (unwrapped: it is the whole string already)
        k = h("r" + run_signature(shape(t)), dim)
        f[k] = f.get(k, 0) + 1
    norm = math.sqrt(sum(v * v for v in f.values())) or 1.0
    f = {k: v / norm for k, v in f.items()}
    if cfg["dense"]:
        classes = sum(bool(re.search(p, t)) for p in (r"[a-z]", r"[A-Z]", r"[0-9]", r"[^A-Za-z0-9\s]"))
        dense = {
            "len": min(len(t), 128) / 128,
            "entropy": entropy(t) / 6,
            "classes": classes / 4,
            "words": min(len(t.split()), 20) / 20,
            "spaces": float(bool(re.search(r"\s", t))),
        }
        for name, v in dense.items():
            f[h("d" + name, dim)] = f.get(h("d" + name, dim), 0) + v
    return f


def run_signature(shp: str) -> str:
    """The shape collapsed into runs, at most 16: Aaaaaaaa9999 -> Aa9, aaa99aaa -> a9a."""
    out: list[str] = []
    for ch in shp:
        if not out or out[-1] != ch:
            out.append(ch)
    return "".join(out[:16])


def matrix(texts, cfg: dict | None = None):
    from scipy.sparse import csr_matrix
    cfg = cfg or DEFAULT_FEATURES
    rows, cols, vals = [], [], []
    for i, t in enumerate(texts):
        for k, v in features(t, cfg).items():
            rows.append(i); cols.append(k); vals.append(v)
    return csr_matrix((vals, (rows, cols)), shape=(len(texts), cfg["dim"]), dtype=np.float32)


def gated(text: str) -> bool:
    """The model only judges what could be a typed or generated password: one token, 8-64 characters, not a link or path."""
    t = text.strip()
    if not (8 <= len(t) <= 64) or re.search(r"\s", t) or re.match(r"^(https?://|www\.|/|~/)", t, re.I) or "://" in t:
        return False
    # Emails and plain numbers are the rules' job (cards, codes); a password has letters.
    if re.fullmatch(r"[\w.+-]+@[\w-]+\.[\w.]+", t) or not re.search(r"[A-Za-z]", t):
        return False
    return not re.search(r"\.[A-Za-z][A-Za-z0-9]{1,4}$", t)  # file names: name.mp4, report.json


def load(name):
    return [json.loads(l) for l in (OUT / name).read_text().splitlines() if l.strip()]


def main():
    train, test = load("train.jsonl"), load("dataset.jsonl")
    # Real harmless text (tracked source and docs from our repos, filtered by our rules) teaches what normal copies look like.
    negs = [{"text": n["text"], "locked": False} for n in load("negatives.jsonl")] if (OUT / "negatives.jsonl").exists() else []
    train = train + negs
    model = LogisticRegression(C=4.0, max_iter=3000, class_weight="balanced")
    model.fit(matrix([c["text"] for c in train]), [int(c["locked"]) for c in train])

    rows = []
    for c in test:
        t = time.perf_counter()
        p = float(model.predict_proba(matrix([c["text"]]))[0, 1]) if gated(c["text"]) else 0.0
        rows.append({"id": c["id"], "score": round(p, 4), "ms": round((time.perf_counter() - t) * 1000, 3)})
    (OUT / "jewel.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    (OUT / "jewel.meta.json").write_text(json.dumps({"threshold": 0.5}))

    import pickle
    (OUT / "jewel-model.pkl").write_bytes(pickle.dumps(model))

    # Weights: only non-zero hashed features matter; keep them sparse.
    w = model.coef_[0]
    nz = {int(i): round(float(w[i]), 5) for i in np.nonzero(np.abs(w) > 1e-4)[0]}
    (OUT / "jewel-model.json").write_text(json.dumps({"dim": DIM, "features": DEFAULT_FEATURES, "bias": float(model.intercept_[0]), "weights": nz}))
    size = (OUT / "jewel-model.json").stat().st_size
    print(f"wrote out/jewel.jsonl ({len(rows)}); model {len(nz)} weights, {size / 1e3:.0f} KB as JSON")

    if "--history" in sys.argv:
        h = os.environ.get("JEWEL_HISTORY_JSONL", "")
        rows = [json.loads(l) for l in Path(h).read_text().splitlines() if l.strip()] if h and Path(h).exists() else []
        texts = [r["text"] for r in rows if r.get("text") and not r.get("sensitive")]
        p = model.predict_proba(matrix(texts))[:, 1]
        flagged = [t for t, s in zip(texts, p) if s >= 0.5 and gated(t)]
        print(f"history: {len(texts)} unlocked items, {len(flagged)} would lock")
        for t in flagged[:40]:
            print("  ", json.dumps(shape(t.strip())[:48]), len(t.strip()))


if __name__ == "__main__":
    main()
