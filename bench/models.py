# /// script
# requires-python = ">=3.11"
# dependencies = ["onnxruntime", "tokenizers", "numpy", "huggingface_hub", "laya", "credsweeper"]
# ///
"""Local models for the lock benchmark (see run.ts).

    uv run bench/models.py [credline]

Reads out/dataset.jsonl (run `run.ts export` first) and writes
out/<model>.jsonl ({id, score, ms}) plus out/<model>.meta.json with the
threshold the model's authors recommend. Models download once to the
Hugging Face cache (~/.cache/huggingface).

credline: zaindanaharper/credential-line-32m (32M, MIT, ONNX). It scores one
line at a time, so a multi-line copy gets its highest line's score.
credsweeper: Samsung CredSweeper (pip, MIT): ~200 regex rules, then a 2.9M-parameter
ONNX validator (11.5 MB) on the candidates. Score = the best candidate's ML
probability (1.0 for rules that skip ML), 0 when no rule matches.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np

OUT = Path(__file__).resolve().parent / "out"


def cases():
    return [json.loads(l) for l in (OUT / "dataset.jsonl").read_text().splitlines() if l.strip()]


def save(name, rows, threshold):
    (OUT / f"{name}.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    (OUT / f"{name}.meta.json").write_text(json.dumps({"threshold": threshold}))
    print(f"wrote out/{name}.jsonl ({len(rows)}), threshold {threshold}")


def credline():
    import onnxruntime as ort
    from huggingface_hub import snapshot_download
    from tokenizers import Tokenizer

    d = Path(snapshot_download("zaindanaharper/credential-line-32m", allow_patterns=["onnx/*", "tokenizer*", "policy.json"]))
    tok = Tokenizer.from_file(str(d / "tokenizer.json"))
    tok.enable_truncation(max_length=128)
    tok.enable_padding(pad_id=50283, pad_token="[PAD]")
    sess = ort.InferenceSession(str(d / "onnx" / "model.onnx"), providers=["CPUExecutionProvider"])
    policy = json.loads((d / "policy.json").read_text())

    def score_lines(lines):
        enc = tok.encode_batch(lines)
        ids = np.array([e.ids for e in enc], dtype=np.int64)
        mask = np.array([e.attention_mask for e in enc], dtype=np.int64)
        logits = sess.run(["logits"], {"input_ids": ids, "attention_mask": mask})[0] / policy["temperature"]
        e = np.exp(logits - logits.max(1, keepdims=True))
        return (e[:, 1] / e.sum(1)).tolist()

    score_lines(["warm up"])
    rows = []
    for c in cases():
        lines = [l for l in c["text"].splitlines() if l.strip()] or [c["text"]]
        t = time.perf_counter()
        p = max(score_lines(lines))
        rows.append({"id": c["id"], "score": round(p, 4), "ms": round((time.perf_counter() - t) * 1000, 2)})
    save("credline", rows, policy["threshold"])


def privacy_filter():
    """openai/privacy-filter (q4 ONNX, ~0.9 GB): token labels; score = the highest per-token probability of a "secret" span label."""
    import onnxruntime as ort
    from huggingface_hub import snapshot_download
    from tokenizers import Tokenizer

    # A real folder, not the hub cache: ONNX Runtime refuses external weights behind the cache's symlinks.
    d = Path(snapshot_download("openai/privacy-filter", allow_patterns=["onnx/model_q4.onnx*", "tokenizer.json", "config.json"],
                               local_dir=Path.home() / ".cache" / "jewel" / "privacy-filter"))
    tok = Tokenizer.from_file(str(d / "tokenizer.json"))
    sess = ort.InferenceSession(str(d / "onnx" / "model_q4.onnx"), providers=["CPUExecutionProvider"])
    labels = json.loads((d / "config.json").read_text())["id2label"]
    secret_ids = [int(i) for i, l in labels.items() if l.endswith("-secret")]
    names = [i.name for i in sess.get_inputs()]

    def score(text):
        e = tok.encode(text)
        feed = {"input_ids": np.array([e.ids], dtype=np.int64)}
        if "attention_mask" in names:
            feed["attention_mask"] = np.array([e.attention_mask], dtype=np.int64)
        logits = sess.run(None, feed)[0][0]
        p = np.exp(logits - logits.max(1, keepdims=True))
        p = p / p.sum(1, keepdims=True)
        return float(p[:, secret_ids].sum(1).max())

    score("warm up")
    rows = []
    for c in cases():
        t = time.perf_counter()
        rows.append({"id": c["id"], "score": round(score(c["text"]), 4), "ms": round((time.perf_counter() - t) * 1000, 2)})
    save("privacy_filter", rows, 0.5)


def laya():
    """convaiinnovations/laya (421M, Apache 2.0): Jev's question format, run locally. Same question as production Jev."""
    from laya import Router

    router = Router()
    q = {"contains_secret": {"type": "noul", "instructions": "Does `clipboard` contain a password, API key, access token, private key, or other credential?"}}
    router.predict({"clipboard": "warm up"}, q)
    rows = []
    for c in cases():
        t = time.perf_counter()
        r = router.predict({"clipboard": c["text"]}, q)
        rows.append({"id": c["id"], "score": round(float(r["answers"]["contains_secret"]["noul"]), 4), "ms": round((time.perf_counter() - t) * 1000, 2)})
    save("laya", rows, 0.5)


def credsweeper():
    """Samsung CredSweeper: regex rules first, then its ONNX validator on the candidates. A bare
    password with no `name=value` context never becomes a candidate, so it scores 0."""
    from credsweeper import CredSweeper
    from credsweeper.file_handler.string_content_provider import StringContentProvider

    cs = CredSweeper(ml_threshold=0.0, log_level="ERROR", pool_count=1)
    thresholds = json.loads((Path(cs.ml_validator.__class__.__module__ and __import__("credsweeper.ml_model", fromlist=["x"]).__file__).parent / "ml_config.json").read_text())["thresholds"]

    def score(text):
        cs.credential_manager.candidates[:] = []
        cs.scan([StringContentProvider(text.splitlines() or [text], file_path="clip.txt")], None)
        cs.post_processing(None)
        return max([c.ml_probability if c.ml_probability is not None else 1.0 for c in cs.credential_manager.get_credentials()], default=0.0)

    score("warm up")
    rows = []
    for c in cases():
        t = time.perf_counter()
        rows.append({"id": c["id"], "score": round(float(score(c["text"])), 4), "ms": round((time.perf_counter() - t) * 1000, 2)})
    save("credsweeper", rows, thresholds["medium"])


RUNNERS = {"credline": credline, "privacy_filter": privacy_filter, "laya": laya, "credsweeper": credsweeper}

if __name__ == "__main__":
    for name in sys.argv[1:] or list(RUNNERS):
        RUNNERS[name]()
