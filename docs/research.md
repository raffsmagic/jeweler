# Research: off-the-shelf models vs building our own

Checked 2026-10-05. Size policy for anything bundled in an app: **aim under 25M parameters; 50M is the hard ceiling.** Security matters across copy-and-paste apps, so a bigger model is allowed only if it clearly beats the small one on all three tests.

## Everything we know of, with size

"Bare string" means it can judge a lone password or token with no `name=value` context around it, which is what a clipboard copy usually is.

| Model or tool | Parameters | On disk | License | Bare string? | Benchmarked | Verdict |
| - | - | - | - | - | - | - |
| **Jewel Jewel 1** (ours) | 5,080 weights | 77 KB | ours | yes | yes | rules + it: 95.5% on the benchmark, 90% of fresh generated passwords, 94% of 564,898 real human passwords |
| the baseline rules | 0 | ~15 KB of TypeScript | ours | yes | yes | 83.4% on the benchmark, no false alarms; 1.3% of real human passwords (they need a symbol or a known format) |
| zaindanaharper/credential-line-32m ("credline") | 32.0M | 128 MB ONNX | MIT | weakly | yes | rules + it 88.4%, 1 false alarm; catches 1.0% of real human passwords. Over the 25M target |
| Samsung CredSweeper (pip) | 2.86M (validator) + ~200 regex rules | 11.5 MB ONNX | MIT | no | yes | rules + it 84.9%, 7 false alarms; 0.8% of real human passwords. Regex finds candidates, the net only confirms them: a lone password is never a candidate |
| Brzb/KeiZen-1 | 4.4M (BERT-tiny + 29 hand features) | 4.5 MB INT8, 17.6 MB fp32 | not stated | no (`KEY=VALUE` lines) | no: its feature code (`benchmark.py`) isn't published, only the 29 feature names | Not runnable faithfully; would only help config lines, which the rules already catch |
| openai/privacy-filter | 1.5B total, 50M active | ~0.9 GB q4 ONNX | Apache 2.0 | yes (token labels) | yes | 16 false alarms (ids, paths, dates), 33 ms; too heavy |
| convaiinnovations/laya | 421M | ≥450 MB | Apache 2.0 | yes (asks a question) | yes | catches most, 43 false alarms, 32 ms; too big |
| hypn05/secrets-sentinel-xsmall | 70.8M | 283 MB | not checked | line classifier for code | no | over the ceiling |
| SAP/password-model (Credential Digger) | not listed (BERT-class) | 499 MB TF | Apache 2.0 | filters regex findings | no | over the ceiling; same "regex first, model second" design as ours |
| gneeraj/deeppass2-bert (SpecterOps DeepPass2) | 277M (xlm-roberta-base) | 1.1 GB | as base model | yes (token labels in documents) | no | over the ceiling; trained partly on real breached passwords (CrackStation) |
| joneauxedgar/pasteproof-pii-detector | 150M (ModernBERT) | 599 MB | not checked | yes (NER before pasting) | no | over the ceiling |
| Jev (hosted, TypeSafe) | – | – | hosted | yes | yes | reference; at the app's 0.8 threshold catches 47%, at 0.5 77% with no false alarms |
| Apple Foundation Models | built into macOS 26 | 0 | Apple | yes | no: Apple Intelligence off on the owner's Mac | untested |
| Jev Decision Index models: GLiNER 2.5 small, Julia 1, Verdict, OpenJev, Kev, Lev, Decider | 74M, 141M, 151M, 151M-26B, 0.8-9B, 350M-4B, 2B | – | various | yes (general decisions) | no | all over the ceiling; general decision models only score well from ~2B |
| gitleaks (~180 rules), detect-secrets (27 plugins), TruffleHog (900+ detectors) | 0 (regex) | – | MIT, Apache 2.0, AGPL | known formats and entropy only | no (same layer as our rules) | the place to copy key formats from; TruffleHog as a reference list only (AGPL) |
| GitGuardian FP Remover, Nosey Parker ML denoiser, Wiz's fine-tuned Llama 3.2 1B | transformer, transformer, 1B | hosted / 1B | proprietary / Apache 2.0 / – | no (post-filters for regex hits) | no | industry confirmation of "regex first, model second"; all far over the ceiling |
| zxcvbn / zxcvbn-ts | 0 (dictionaries) | ~400-800 KB with English lists | MIT | yes (strength, not detection) | no | not a detector, but its matchers (dictionary with rank, l33t, keyboard walks, dates, repeats) decompose the word-based passwords our model misses; candidate feature source |

## What the comparison says

1. **Nothing off the shelf judges a bare password.** The scanners (CredSweeper, credline, KeiZen, gitleaks and friends) look for `name = value` and known prefixes. On 2,836 real human passwords sampled from the 000webhost list, credline caught 1.0% and CredSweeper 0.8%; our model caught 94%. They solve "find secrets in a repo", which is not our problem.
2. **A general model can't be small; a single-question model can.** Everything that answers any question is 74M and up and only scores well from ~2B. Ours answers one question in 5,080 weights.
3. **The useful imports are formats and ideas, not weights:** gitleaks/detect-secrets for key formats, CredSweeper's hand features (entropy, length, char classes) as a sanity check of ours, DeepPass2's recipe (real human password structure) via published mask statistics rather than the passwords, zxcvbn's matchers for word-based passwords.
4. **Where ours is weak:** it is a shape detector. It catches 99.8% of `Word+digits` passwords in the wild, which also means it locks `Thursday2026`. Fixing that needs everyday negatives of the same shape and a policy decision, not a bigger model.

## Datasets for later
- CredData (Samsung): 73,842 labeled lines, 4,583 real credentials from public code. Testing only.
- SecretBench: 97,479 secrets from 818 repos, 15,084 verified. Testing only.
- Leaked password lists (000webhost via SecLists today; RockYou, LinkedIn and others exist): **testing only, streamed in memory** (`bench/leaked.ts`, `bench/leaked.py`). For training, use published mask statistics (PACK `statsgen`, Praetorian's 34M-password study) to shape the generators instead.
- Key formats: gitleaks (~180 rules, MIT), detect-secrets (27 plugins, Apache 2.0), TruffleHog (900+ detectors, AGPL: reference only).
- Word lists: EFF diceware (CC BY), BIP39 (MIT), zxcvbn's frequency lists (MIT).

## Method: autoresearch (Karpathy, March 2026)

[github.com/karpathy/autoresearch](https://github.com/karpathy/autoresearch): an agent edits one file (`train.py`), trains for a fixed budget, keeps the change if the metric improved and reverts it otherwise, logging every try to a TSV; the human edits only `program.md`, the agent's instructions. Jewel's port is `research/` (`prepare.py` frozen exam, `train.py` editable, `program.md`, `results.tsv`). Differences from the original: the fixed budget is a cap (180 s) rather than a target, because a logistic regression trains in seconds; the metric is `fp94` (everyday false alarms at 94% real-password recall) instead of bits per byte; and the exam carries honesty checks (`leak`, `peek`) because the agent can read the test files. Three runs and what they found, with a verdict on the cost: `docs/benchmark.md`, rounds 6 and 7.
