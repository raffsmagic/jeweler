# /// script
# requires-python = ">=3.11"
# dependencies = ["scikit-learn", "numpy", "scipy", "onnxruntime", "tokenizers", "huggingface_hub", "laya"]
# ///
"""Held-out tests for the lock checkers: things no model or rule was tuned on.

    uv run bench/holdout.py gen                # new fake passwords -> out/holdout-fresh.jsonl
    npx tsx bench/holdout-rules.ts   # rules' verdicts (ids only for history)
    uv run bench/holdout.py

1. fresh: passwords from generators the benchmark never used (Safari's
   strong-password format, password-manager styles, passphrases, PINs, plain
   alphanumerics, pronounceable words). Frozen: a seeded RNG (FRESH_SEED), so
   every model is tested on the same 300 passwords.
2. history: the owner's real copies in the local copy history export. Positives are
   items already locked plus unlocked ones the current rules would lock; the rest
   are negatives. Text is read in memory only; nothing is written or sent, and
   misses print as masked shapes (a = lower, A = upper, 9 = digit).

Checkers: rules (from holdout-rules.ts), Jewel (out/jewel-model.pkl),
credential-line-32m and Laya, each at its benchmark threshold.
"""
from __future__ import annotations

import json
import os
import pickle
import random
import sqlite3
import string
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from jewel import gated, matrix, shape  # noqa: E402

OUT = Path(__file__).resolve().parent / "out"
FRESH_SEED = 20261005
WORDS = ["anchor", "blossom", "canyon", "drizzle", "eclipse", "fjord", "glacier", "hazel", "indigo", "jasper", "kettle", "lagoon", "meadow", "nectar", "obsidian", "parsley", "quill", "raven", "sorrel", "thistle", "umber", "velvet", "walnut", "yonder", "zephyr"]


def fresh(seed: int = FRESH_SEED) -> list[tuple[str, str]]:
    secrets = random.Random(seed)  # same names as the stdlib module, seeded
    secrets.token_urlsafe = lambda n: __import__('base64').urlsafe_b64encode(secrets.randbytes(n)).rstrip(b'=').decode()
    secrets.token_hex = lambda n: secrets.randbytes(n).hex()
    secrets.randbelow = lambda n: secrets.randrange(n)
    a, d = string.ascii_letters, string.digits
    gens = {
        # Safari / iCloud Keychain: xxxxxx-xxxxxx-xxxxxx with one capital and one digit
        "safari": lambda: "-".join("".join(secrets.choice(string.ascii_lowercase) for _ in range(6)) for _ in range(3)).replace(secrets.choice("abcdefghij"), secrets.choice(string.ascii_uppercase), 1)[:-1] + secrets.choice(d),
        "random_alnum_12": lambda: "".join(secrets.choice(a + d) for _ in range(12)),
        "random_alnum_20": lambda: "".join(secrets.choice(a + d) for _ in range(20)),
        "random_full_10": lambda: "".join(secrets.choice(a + d + "!@#$%^&*()[]{}<>?/|~") for _ in range(10)),
        "random_full_24": lambda: "".join(secrets.choice(a + d + string.punctuation) for _ in range(24)),
        "memorable_dash": lambda: "-".join(secrets.choice(WORDS) for _ in range(3)) + str(secrets.randbelow(100)),
        "memorable_caps": lambda: "".join(secrets.choice(WORDS).capitalize() for _ in range(3)) + secrets.choice("!?#") + str(secrets.randbelow(10)),
        "passphrase_spaces": lambda: " ".join(secrets.choice(WORDS) for _ in range(4)),
        "leet_word": lambda: secrets.choice(WORDS).capitalize().replace("a", "@").replace("o", "0").replace("e", "3") + str(secrets.randbelow(10000)),
        "pin_4_6": lambda: str(secrets.randbelow(10 ** 6)).zfill(secrets.choice([4, 6])),
        "token_urlsafe": lambda: secrets.token_urlsafe(18),
        "hex_16": lambda: secrets.token_hex(8),
    }
    return [(kind, g()) for kind, g in gens.items() for _ in range(25)]


def history() -> list[tuple[str, str, bool]]:
    rule_ids = set(json.loads((OUT / "holdout-rules.json").read_text())["history"])
    rows = []
    h = os.environ.get("JEWEL_HISTORY_JSONL", "")
    lines = [l for l in Path(h).read_text().splitlines() if l.strip()] if h and Path(h).exists() else []
    for i, l in enumerate(lines):
        r = json.loads(l)
        key = f"h:{i}"
        if r.get("text"):
            rows.append((key, r["text"], bool(r.get("sensitive")) or key in rule_ids))
    return rows


def checkers():
    jewel = pickle.loads((OUT / "jewel-model.pkl").read_bytes())

    def jewel_score(texts):
        p = jewel.predict_proba(matrix(texts))[:, 1]
        return [float(s) if gated(t) else 0.0 for t, s in zip(texts, p)]

    import numpy as np
    import onnxruntime as ort
    from huggingface_hub import snapshot_download
    from tokenizers import Tokenizer

    d = Path(snapshot_download("zaindanaharper/credential-line-32m", allow_patterns=["onnx/*", "tokenizer*", "policy.json"]))
    tok = Tokenizer.from_file(str(d / "tokenizer.json"))
    tok.enable_truncation(max_length=128)
    tok.enable_padding(pad_id=50283, pad_token="[PAD]")
    sess = ort.InferenceSession(str(d / "onnx" / "model.onnx"), providers=["CPUExecutionProvider"])
    policy = json.loads((d / "policy.json").read_text())

    def cred_score(texts):
        out = []
        for t in texts:
            lines = [l for l in t.splitlines() if l.strip()][:20] or [t]
            enc = tok.encode_batch(lines)
            logits = sess.run(["logits"], {"input_ids": np.array([e.ids for e in enc], dtype=np.int64), "attention_mask": np.array([e.attention_mask for e in enc], dtype=np.int64)})[0] / policy["temperature"]
            e = np.exp(logits - logits.max(1, keepdims=True))
            out.append(float((e[:, 1] / e.sum(1)).max()))
        return out

    from laya import Router

    router = Router()
    q = {"contains_secret": {"type": "noul", "instructions": "Does `clipboard` contain a password, API key, access token, private key, or other credential?"}}

    def laya_score(texts):
        return [float(router.predict({"clipboard": t[:2000]}, q)["answers"]["contains_secret"]["noul"]) for t in texts]

    return {"jewel": (jewel_score, 0.5), "credline": (cred_score, policy["threshold"]), "laya": (laya_score, 0.5)}


def main():
    rules = json.loads((OUT / "holdout-rules.json").read_text())
    models = checkers()

    print("## 1. Fresh passwords (never seen by any checker): caught out of 25\n")
    f = [(r["kind"], r["text"]) for r in map(json.loads, (OUT / "holdout-fresh.jsonl").read_text().splitlines())]
    texts = [t for _, t in f]
    scores = {name: [s >= th for s in fn(texts)] for name, (fn, th) in models.items()}
    scores["rules"] = rules["fresh"]
    kinds = list(dict.fromkeys(k for k, _ in f))
    names = ["rules", "jewel", "credline", "laya"]
    print("| Generator | Example shape | " + " | ".join(names) + " | rules+jewel |")
    print("| - | - | " + " | ".join("-" for _ in names) + " | - |")
    tot = {n: 0 for n in names + ["rules+jewel"]}
    for k in kinds:
        idx = [i for i, (kk, _) in enumerate(f) if kk == k]
        cells = []
        for n in names:
            c = sum(scores[n][i] for i in idx)
            tot[n] += c
            cells.append(str(c))
        both = sum(scores["rules"][i] or scores["jewel"][i] for i in idx)
        tot["rules+jewel"] += both
        print(f"| {k} | `{shape(f[idx[0]][1])[:24]}` | " + " | ".join(cells) + f" | {both} |")
    print("| **total of %d** | | " % len(f) + " | ".join(str(tot[n]) for n in names) + f" | {tot['rules+jewel']} |\n")

    print("## 2. The owner's real history (local only)\n")
    h = history()
    texts = [t for _, t, _ in h]
    labels = [lab for _, _, lab in h]
    pos = sum(labels)
    print(f"{len(h)} items: {pos} the rules lock (counted as passwords and keys), {len(h) - pos} others.\n")
    print("| Checker | Of the rules' locks, also caught | Others it would lock |")
    print("| - | - | - |")
    for name, (fn, th) in models.items():
        s = [x >= th for x in fn(texts)]
        caught = sum(1 for x, l in zip(s, labels) if x and l)
        extra = [t for t, x, l in zip(texts, s, labels) if x and not l]
        print(f"| {name} | {caught} of {pos} | {len(extra)} |")
        for t in extra[:12]:
            print(f"|   | | `{shape(t.strip())[:40]}` ({len(t.strip())}) |")


if __name__ == "__main__":
    if sys.argv[1:] == ["gen"]:
        (OUT / "holdout-fresh.jsonl").write_text("".join(json.dumps({"kind": k, "text": t}) + "\n" for k, t in fresh()))
        print("wrote out/holdout-fresh.jsonl")
    else:
        main()
