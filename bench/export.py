# /// script
# requires-python = ">=3.11"
# dependencies = ["scikit-learn", "numpy", "scipy"]
# ///
"""Export the trained Jewel model for apps: prune tiny weights, write models/jeweler-v<n>.json,
and write bench/out/parity.jsonl (texts + Python scores) for runtime/parity.ts.

    uv run bench/export.py 1 [--min-weight 0.01] [--pkl out/loop/<variant>.pkl]   # the model number
    uv run bench/export.py 2 --from-json research/out/candidate.json              # ship what autoresearch kept
"""
import json, math, pickle, sys
from datetime import date
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from jewel import DEFAULT_FEATURES, features

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "bench" / "out"
version = int(sys.argv[1]) if len(sys.argv) > 1 and not sys.argv[1].startswith("--") else 1
min_w = float(sys.argv[sys.argv.index("--min-weight") + 1]) if "--min-weight" in sys.argv else 0.01
pkl = Path(sys.argv[sys.argv.index("--pkl") + 1]) if "--pkl" in sys.argv else OUT / "jewel-model.pkl"  # e.g. out/loop/<variant>.pkl
if "--from-json" in sys.argv:  # a research/out/candidate.json the autoresearch loop kept: already pruned, threshold = t94
    cand = json.loads(Path(sys.argv[sys.argv.index("--from-json") + 1]).read_text())
    cfg, weights, bias, threshold = cand["features"], cand["weights"], cand["bias"], cand["threshold"]
else:
    m = pickle.loads(pkl.read_bytes())
    w = m.coef_[0]
    weights = {str(i): round(float(w[i]), 4) for i in range(len(w)) if abs(w[i]) >= min_w}
    cfg = getattr(m, "jewel_features", None) or DEFAULT_FEATURES  # bench/loop.py tags variants it exports
    bias, threshold = round(float(m.intercept_[0]), 6), 0.5
model = {"version": version, "created": date.today().isoformat(), "dim": cfg["dim"], "features": cfg, "bias": bias, "threshold": threshold, "weights": weights}
path = ROOT / "models" / f"jeweler-v{version}.json"
path.write_text(json.dumps(model, separators=(",", ":")))
print(f"wrote {path.relative_to(ROOT)}: {len(weights)} weights, {path.stat().st_size / 1e3:.0f} KB")

def score(text):
    z = model["bias"] + sum(weights.get(str(k), 0.0) * v for k, v in features(text, cfg).items())
    return 1 / (1 + math.exp(-z))

texts = [json.loads(l)["text"] for f in ["dataset.jsonl", "holdout-fresh.jsonl"] if (OUT / f).exists() for l in (OUT / f).read_text().splitlines() if l.strip()]
texts += ["Summer2026!", "nbB-Pdv-v3v-WUc", "héllo wörld 😀", "  padded  ", "ПАРОЛЬ123!", "a" * 300]
(OUT / "parity.jsonl").write_text("".join(json.dumps({"text": t, "score": score(t)}) + "\n" for t in texts))
print(f"wrote bench/out/parity.jsonl ({len(texts)})")
