# /// script
# requires-python = ">=3.11"
# dependencies = ["scikit-learn", "numpy", "scipy", "onnxruntime", "tokenizers", "huggingface_hub", "credsweeper"]
# ///
"""Passwords in the wild, Python side: the same public leaked-password list as
bench/leaked.ts, streamed in memory, but only every 200th line (by CRC32, the same
rule as leaked.ts) so the slower Python-only checkers finish in seconds.

    npx tsx bench/leaked.ts      # rules and the shipped model over the whole list
    uv run bench/leaked.py       # Jewel (pkl), credline, CredSweeper over the sample

Nothing is written to disk and no password is printed: counts only.
"""
from __future__ import annotations

import json
import pickle
import sys
import time
import urllib.request
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from jewel import gated, matrix  # noqa: E402

OUT = Path(__file__).resolve().parent / "out"
URL = sys.argv[1] if len(sys.argv) > 1 else "https://raw.githubusercontent.com/danielmiessler/SecLists/master/Passwords/Leaked-Databases/000webhost.txt"
SAMPLE_EVERY = 200


def sample():
    total = judged = 0
    picked = []
    with urllib.request.urlopen(URL) as r:
        for raw in r:
            line = raw.decode("utf-8", "replace").rstrip("\r\n")
            total += 1
            if not gated(line):
                continue
            judged += 1
            if zlib.crc32(line.encode()) % SAMPLE_EVERY == 0:
                picked.append(line.strip())
    return total, judged, picked


def main():
    total, judged, texts = sample()
    print(f"{total:,} lines, {judged:,} pass the gate; sample of {len(texts)} (every {SAMPLE_EVERY}th by CRC32).\n")
    results = {}

    jewel = pickle.loads((OUT / "jewel-model.pkl").read_bytes())
    t0 = time.perf_counter()
    p = jewel.predict_proba(matrix(texts))[:, 1]
    results["Jewel (pkl, same as jewel-1 before pruning)"] = (sum(p >= 0.5), (time.perf_counter() - t0) * 1000 / len(texts))

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
    t0 = time.perf_counter()
    caught = 0
    for i in range(0, len(texts), 64):
        enc = tok.encode_batch(texts[i:i + 64])
        logits = sess.run(["logits"], {"input_ids": np.array([e.ids for e in enc], dtype=np.int64), "attention_mask": np.array([e.attention_mask for e in enc], dtype=np.int64)})[0] / policy["temperature"]
        e = np.exp(logits - logits.max(1, keepdims=True))
        caught += int(((e[:, 1] / e.sum(1)) >= policy["threshold"]).sum())
    results[f"credline @ {policy['threshold']}"] = (caught, (time.perf_counter() - t0) * 1000 / len(texts))

    from credsweeper import CredSweeper
    from credsweeper.file_handler.string_content_provider import StringContentProvider

    cs = CredSweeper(ml_threshold=0.0, log_level="ERROR", pool_count=1)
    t0 = time.perf_counter()
    caught = 0
    for t in texts:
        cs.credential_manager.candidates[:] = []
        cs.scan([StringContentProvider([t], file_path="clip.txt")], None)
        cs.post_processing(None)
        caught += any((c.ml_probability if c.ml_probability is not None else 1.0) >= 0.62204 for c in cs.credential_manager.get_credentials())
    results["CredSweeper @ medium"] = (caught, (time.perf_counter() - t0) * 1000 / len(texts))

    print(f"| Checker | Caught of {len(texts)} | Share | ms per item |\n| - | - | - | - |")
    for name, (c, ms) in results.items():
        print(f"| {name} | {c} | {100 * c / len(texts):.1f}% | {ms:.2f} |")


if __name__ == "__main__":
    main()
