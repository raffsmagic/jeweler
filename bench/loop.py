# /// script
# requires-python = ">=3.11"
# dependencies = ["scikit-learn", "numpy", "scipy"]
# ///
"""The experiment loop: train many Jewel variants, score every one on the same
frozen sets, and write one table.

    uv run bench/loop.py [--wild-every 100] [--only NAME,NAME] [--quick]
    uv run bench/loop.py --report          # rebuild out/loop.md from out/loop.json without retraining

Needs out/train.jsonl, out/negatives.jsonl, out/dataset.jsonl and
out/holdout-fresh.jsonl (README "Run it"). Writes out/loop.md, out/loop.json and
one pickle per variant in out/loop/ (ship one with `export.py <n> --pkl out/loop/<name>.pkl`).

Frozen sets (the exam is the same for every variant):
- benchmark: bench/dataset.ts, 199 to lock + 188 look-alikes (seed 20261004)
- fresh: 300 passwords from 12 generators never used in training (holdout.py, seeded)
- everyday: bench/everyday.json, 160 hand-written ordinary copies that must stay unlocked
- wild: every Nth gated line (CRC32) of the public 000webhost list, streamed in memory,
  never written; N = --wild-every (100 -> about 5,650 real human passwords)
the baseline rules are asked about every text once (bench/rules-stdin.ts) so "rules + Jewel"
can be reported next to "Jewel alone".

Variants: feature configurations (see FEATS) x regularisation C x training mix
(base = fake passwords + repo text; +everydayN = base plus N generated everyday-shaped
negatives from words disjoint from everyday.json, N = 500, 1500, 3000). Nothing here touches the owner's history.
"""
from __future__ import annotations

import itertools
import json
import pickle
import random
import subprocess
import sys
import time
import urllib.request
import zlib
from collections import Counter
from pathlib import Path

import numpy as np
from scipy.sparse import vstack
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, roc_auc_score

BENCH = Path(__file__).resolve().parent
OUT = BENCH / "out"
sys.path.insert(0, str(BENCH))
from jewel import DEFAULT_FEATURES, gated, matrix  # noqa: E402

WILD_URL = "https://raw.githubusercontent.com/danielmiessler/SecLists/master/Passwords/Leaked-Databases/000webhost.txt"
PRUNE = 0.2          # export.py --min-weight used for Jewel 1
BYTES_PER_WEIGHT = 15  # jewel-1.json: 76,734 bytes / 5,080 weights
THRESHOLD = 0.5

args = sys.argv[1:]
WILD_EVERY = int(args[args.index("--wild-every") + 1]) if "--wild-every" in args else 100
ONLY = set(args[args.index("--only") + 1].split(",")) if "--only" in args else None
QUICK = "--quick" in args

F = lambda **kw: {**DEFAULT_FEATURES, **kw}
FEATS = {
    "jewel1": DEFAULT_FEATURES,                                   # char 1-4, shape 1-6, dense, 32k buckets
    "boundary": F(boundary=True),                                 # + ^ and $ markers
    "boundary_64k": F(boundary=True, dim=65536),                  # + fewer hash collisions
    "char5_shape8": F(char_n=5, shape_n=8),                       # longer patterns
    "boundary_char5_shape8": F(boundary=True, char_n=5, shape_n=8),
    "boundary_nodense": F(boundary=True, dense=False),            # are the 5 dense features pulling weight?
    "small_16k": F(boundary=True, char_n=3, shape_n=5, dim=16384),  # can it be smaller?
}
CS = [1.0, 4.0, 16.0]
MIXES = ["base", "+everyday500", "+everyday1500", "+everyday3000"]  # dose of everyday-shaped negatives
if QUICK:
    FEATS = {k: FEATS[k] for k in ["jewel1", "boundary"]}; CS = [4.0]; MIXES = ["base", "+everyday3000"]

log = lambda *a: print(*a, file=sys.stderr, flush=True)
load = lambda name: [json.loads(l) for l in (OUT / name).read_text().splitlines() if l.strip()]


def rules(texts: list[str]) -> list[bool]:
    r = subprocess.run(["npx", "tsx", str(BENCH / "rules-stdin.ts")], input=json.dumps(texts), capture_output=True, text=True, check=True, cwd=BENCH.parent)
    return json.loads(r.stdout)


def wild_sample(every: int) -> list[str]:
    picked, total = [], 0
    with urllib.request.urlopen(WILD_URL) as r:
        for raw in r:
            line = raw.decode("utf-8", "replace").rstrip("\r\n")
            total += 1
            if gated(line) and zlib.crc32(line.encode()) % every == 0:
                picked.append(line.strip())
    log(f"wild: {total:,} lines streamed, {len(picked):,} sampled (every {every}th gated line); nothing written")
    return picked


# Everyday-shaped training negatives. Words deliberately disjoint from bench/everyday.json.
EW = ["Monday", "Tuesday", "Friday", "January", "March", "July", "Winter", "Spring", "Autumn", "Holiday", "Vacation", "Project", "Review", "Planning",
      "Launch", "Release", "Memo", "Photos", "Trip", "Paris", "London", "Berlin", "Tokyo", "Austin", "Denver", "Seattle", "Boston", "Lisbon", "Surface",
      "Roomba", "Vespa", "Honda", "Toyota", "Lego", "Nikon", "Canon", "Garmin", "Peloton", "Dyson", "Nespresso", "Garden", "Kitchen", "Studio", "Office",
      "Family", "Reunion", "Concert", "Festival", "Recipe", "Workout", "Payroll", "Hiring", "Onboarding", "Pricing", "Design", "Backend", "Mobile", "Alpha"]
EL = [w.lower() for w in EW]


def everyday_train(n: int, seed: int, forbidden: set[str]) -> list[str]:
    rng = random.Random(seed)
    W, L = lambda: rng.choice(EW), lambda: rng.choice(EL)
    year = lambda: str(rng.randint(2019, 2031))
    pats = [
        lambda: W() + year(),
        lambda: W() + W() + year(),
        lambda: f"Q{rng.randint(1, 4)}{W()}{year()}",
        lambda: W() + W() + str(rng.randint(1, 99)),
        lambda: W() + str(rng.randint(2, 20)) + W(),
        lambda: W() + W() + W(),
        lambda: f"{L()}_{L()}_{L()}",
        lambda: f"{L()}-{L()}-{rng.randint(1, 60)}",
        lambda: f"{L().upper()}_{L().upper()}",
        lambda: f"{W()}{W()}Pro{rng.randint(2, 17)}",
        lambda: f"v{rng.randint(0, 9)}.{rng.randint(0, 30)}.{rng.randint(0, 99)}-{rng.choice(['beta', 'rc1', 'alpha', 'dev'])}",
        lambda: f"{rng.choice(['INV', 'ORD', 'PO', 'REF', 'CASE', 'TKT'])}-{rng.randint(2019, 2031)}-{rng.randint(10, 9999):04d}",
        lambda: f"{W()}{rng.randint(1, 31)}{rng.choice(['am', 'pm', 'th', 'st'])}",
        lambda: f"{L()}{rng.randint(1, 12)}{L()}",
        lambda: f"{W()}At{rng.randint(1, 12)}{rng.choice(['00', '30'])}",
    ]
    out: list[str] = []
    seen = set(forbidden)
    while len(out) < n:
        t = rng.choice(pats)()
        if t in seen or not gated(t):
            continue
        seen.add(t); out.append(t)
    return out


def main():
    t0 = time.time()
    train = load("train.jsonl")
    negs = [n["text"] for n in load("negatives.jsonl")]
    bench = load("dataset.jsonl")
    fresh = load("holdout-fresh.jsonl")
    everyday = json.loads((BENCH / "everyday.json").read_text())["items"]
    wild = wild_sample(WILD_EVERY)
    ever_train = everyday_train(3000, 7, {e["text"] for e in everyday})
    log(f"train: {sum(c['locked'] for c in train)} fake passwords + {len(negs):,} repo lines; +everyday mix adds {len(ever_train):,}")

    suites = {"bench": [c["text"] for c in bench], "fresh": [c["text"] for c in fresh], "everyday": [e["text"] for e in everyday], "wild": wild}
    allt = list(itertools.chain.from_iterable(suites.values()))
    verdict = rules(allt)
    rv, i = {}, 0
    for k, texts in suites.items():
        rv[k] = verdict[i:i + len(texts)]; i += len(texts)
    log(f"rules: bench locks {sum(rv['bench'])}, fresh {sum(rv['fresh'])}/300, everyday {sum(rv['everyday'])}/{len(everyday)} (false alarms), wild {sum(rv['wild'])}/{len(wild)}")
    gate = {k: [gated(t) for t in texts] for k, texts in suites.items()}
    bench_y = np.array([c["locked"] for c in bench])

    (OUT / "loop").mkdir(exist_ok=True)
    rows = []
    for fname, cfg in FEATS.items():
        tf = time.time()
        texts = [c["text"] for c in train] + negs + ever_train + allt
        X = matrix(texts, cfg)
        n_tr, n_ng, n_ev = len(train), len(negs), len(ever_train)
        Xtr, Xng, Xev = X[:n_tr], X[n_tr:n_tr + n_ng], X[n_tr + n_ng:n_tr + n_ng + n_ev]
        Xs, j = {}, n_tr + n_ng + n_ev
        for k, ts in suites.items():
            Xs[k] = X[j:j + len(ts)]; j += len(ts)
        log(f"[{fname}] features for {len(texts):,} texts in {time.time() - tf:.0f}s")
        ytr = np.array([int(c["locked"]) for c in train])
        for C, mix in itertools.product(CS, MIXES):
            name = f"{fname}/C{C:g}/{mix}"
            if ONLY and name not in ONLY and fname not in ONLY:
                continue
            dose = int(mix[len("+everyday"):]) if mix.startswith("+everyday") else 0
            Xfit = vstack([Xtr, Xng] + ([Xev[:dose]] if dose else []))
            yfit = np.concatenate([ytr, np.zeros(n_ng + dose, dtype=int)])
            t1 = time.time()
            m = LogisticRegression(C=C, max_iter=3000, class_weight="balanced").fit(Xfit, yfit)
            fit_s = time.time() - t1
            m.jewel_features = cfg
            (OUT / "loop" / (name.replace("/", "__") + ".pkl")).write_bytes(pickle.dumps(m))
            w = m.coef_[0]
            kept = int((np.abs(w) >= PRUNE).sum())
            p = {k: m.predict_proba(Xs[k])[:, 1] for k in suites}
            yes = {k: (p[k] >= THRESHOLD) & np.array(gate[k]) for k in suites}
            both = {k: yes[k] | np.array(rv[k]) for k in suites}
            # benchmark
            tp, fp = int((yes["bench"] & bench_y).sum()), int((yes["bench"] & ~bench_y).sum()); fn = int(bench_y.sum()) - tp
            prec, rec = tp / max(1, tp + fp), tp / max(1, tp + fn)
            f1 = 2 * prec * rec / max(1e-9, prec + rec)
            b_tp, b_fp = int((both["bench"] & bench_y).sum()), int((both["bench"] & ~bench_y).sum())
            # everyday per kind (Jewel alone)
            kinds = Counter(); hits = Counter()
            for e, y in zip(everyday, yes["everyday"]):
                kinds[e["kind"]] += 1; hits[e["kind"]] += int(y)
            # threshold-free: wild (positives) vs everyday (negatives)
            y_we, p_we = np.r_[np.ones(len(wild)), np.zeros(len(everyday))], np.r_[p["wild"], p["everyday"]]
            ap = float(average_precision_score(y_we, p_we))
            auc = float(roc_auc_score(y_we, p_we))  # prevalence-free, unlike AP
            t94 = float(np.quantile(p["wild"], 0.06))  # threshold that keeps 94% wild recall
            fp94 = float((p["everyday"] >= t94).mean())
            row = {
                "variant": name, "features": fname, "C": C, "mix": mix, "weights": kept, "kb": round(kept * BYTES_PER_WEIGHT / 1e3), "fit_s": round(fit_s, 1),
                "bench_f1": round(f1, 3), "bench_recall": round(rec, 3), "bench_fp": fp,
                "rj_bench_recall": round(b_tp / int(bench_y.sum()), 3), "rj_bench_fp": b_fp,
                "fresh_recall": round(float(yes["fresh"].mean()), 3), "rj_fresh_recall": round(float(both["fresh"].mean()), 3),
                "everyday_fp": round(float(yes["everyday"].mean()), 3), "everyday_fp_by_kind": {k: f"{hits[k]}/{kinds[k]}" for k in kinds},
                "wild_recall": round(float(yes["wild"].mean()), 3), "rj_wild_recall": round(float(both["wild"].mean()), 3),
                "ap_wild_vs_everyday": round(ap, 4), "auc_wild_vs_everyday": round(auc, 4), "t_at_94_wild": round(t94, 3), "everyday_fp_at_94_wild": round(fp94, 3),
            }
            rows.append(row)
            log(f"  {name:38} w={kept:5d} ({row['kb']} KB) fit {fit_s:4.1f}s | bench F1 {f1:.3f} r+j {row['rj_bench_recall']:.3f}/{b_fp}fp | fresh r+j {row['rj_fresh_recall']:.3f} | everyday fp {row['everyday_fp']:.3f} | wild {row['wild_recall']:.3f} | AUC {auc:.4f} | fp@94 {fp94:.3f}")

    (OUT / "loop.json").write_text(json.dumps({"wild_every": WILD_EVERY, "wild_n": len(wild), "everyday_n": len(everyday), "rules": {k: int(sum(v)) for k, v in rv.items()}, "rows": rows}, indent=1))
    report()
    log(f"wrote out/loop.md and out/loop.json ({len(rows)} variants) in {(time.time() - t0) / 60:.1f} min")


def report():
    d = json.loads((OUT / "loop.json").read_text())
    rows, rv, n_wild, n_every, every_n = d["rows"], d["rules"], d["wild_n"], d.get("everyday_n", 160), d["wild_every"]
    rows.sort(key=lambda r: (r["everyday_fp_at_94_wild"], -r["wild_recall"]))
    kinds_order = ["word_year", "report_tag", "product", "camel_phrase", "identifier", "place_name", "version_platform", "code_or_id", "plain_word"]
    md = [f"# Jewel experiment loop ({time.strftime('%Y-%m-%d')})", "",
          f"{len(rows)} variants, each scored on the same frozen sets: benchmark 387 (199 to lock), fresh 300, everyday {n_every} (must stay unlocked), wild {n_wild:,} real passwords (every {every_n}th gated line of the 000webhost list, streamed). Threshold {THRESHOLD}. Rules alone: everyday false alarms {rv['everyday']}, wild {rv['wild'] / n_wild:.1%}, fresh {rv['fresh']}/300.",
          "", "Sorted by \"fp@94\": the everyday false-alarm rate at whatever threshold keeps 94% wild recall, so variants are compared at equal recall (lower is better). AUC = wild passwords vs everyday copies, threshold-free and prevalence-free. \"r+j\" = rules, then Jewel. Everything else is at threshold 0.5.", "",
          "| Variant | Weights | ~KB | Bench F1 (Jewel) | Bench r+j recall / FP | Fresh r+j | Everyday FP | Wild recall | Wild r+j | AUC | fp@94 |", "| - | - | - | - | - | - | - | - | - | - | - |"]
    for r in rows:
        md.append(f"| {r['variant']} | {r['weights']:,} | {r['kb']} | {r['bench_f1']:.3f} | {r['rj_bench_recall']:.1%} / {r['rj_bench_fp']} | {r['rj_fresh_recall']:.1%} | {r['everyday_fp']:.1%} | {r['wild_recall']:.1%} | {r['rj_wild_recall']:.1%} | {r.get('auc_wild_vs_everyday', float('nan')):.4f} | {r['everyday_fp_at_94_wild']:.1%} |")
    md += ["", "## Everyday false alarms by kind (Jewel alone, caught/total)", "", "| Variant | " + " | ".join(kinds_order) + " |", "| - | " + " | ".join("-" for _ in kinds_order) + " |"]
    for r in rows:
        md.append(f"| {r['variant']} | " + " | ".join(r["everyday_fp_by_kind"].get(k, "0/0") for k in kinds_order) + " |")
    (OUT / "loop.md").write_text("\n".join(md) + "\n")


if __name__ == "__main__":
    report() if "--report" in args else main()
