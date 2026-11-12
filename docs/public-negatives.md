# Public harmless text (experiment 1, 2026-11-10)

Jewel 1 and Jewel 2 learned their ~39k harmless lines from private repos. This is the public replacement: 14 permissively licensed repositories, shallow-cloned into `bench/out/public-repos/` (gitignored), chunked by the unchanged `bench/negatives.py` and filtered through the baseline rules. Nothing from these repos is committed here; this file is what is needed to rebuild the data.

| Repository | Commit | License | What it adds | Eligible lines |
| - | - | - | - | - |
| https://github.com/excalidraw/excalidraw | 701b901a0f1ba3d0b390d9cdf63d112e25abac4b | MIT | TypeScript/React app | 152,942 |
| https://github.com/honojs/hono | 61f7c59e50244ab4d2dd83c151928cf7ea448510 | MIT | TypeScript library | 41,976 |
| https://github.com/sveltejs/svelte | 7fbb77b995c550cba9abdf7ed24edaa8ab8567d1 | MIT | TypeScript/JavaScript, docs | 41,127 |
| https://github.com/p0deje/Maccy | f0b571e32e4031d7b91ba811f50d0f33e8e5548b | MIT | Swift macOS clipboard manager | 8,799 |
| https://github.com/rxhanson/Rectangle | 875182d2690e4b8fdf485467b31a3233d630581f | MIT | Swift macOS app | 30,262 |
| https://github.com/tauri-apps/tauri | 66b29d1b03bdc08e7275f8da40cc05432a50e1f4 | Apache-2.0 OR MIT | Rust + TypeScript desktop framework | 157,768 |
| https://github.com/BurntSushi/ripgrep | 178cc027e283fd965cb72d0a7395b219eada170c | MIT OR Unlicense | Rust CLI | 54,481 |
| https://github.com/alacritty/alacritty | aa5d942f46c40184a3f214830ff5f7989f4733a1 | Apache-2.0 OR MIT | Rust app | 36,705 |
| https://github.com/pallets/flask | 49943b5a94413a530761350f04e896f76e8d620e | BSD-3-Clause | Python | 10,685 |
| https://github.com/encode/httpx | b5addb64f0161ff6bfe94c124ef76f6a1fba5254 | BSD-3-Clause | Python, Markdown docs | 14,249 |
| https://github.com/fastapi/typer | 4bca5b3847be75ef26db2a80dc4863cebf6de83e | MIT | Python, prose-heavy Markdown docs | 31,846 |
| https://github.com/rust-lang/book | 2771df165f092a4fbb9f46b5b2e7450f19010adb | Apache-2.0 OR MIT | prose (a book in Markdown) | 79,655 |
| https://github.com/airbnb/javascript | 8ed19247bef145e3cc41b24a02dd1fe6d9b5e681 | MIT | prose (style guide) | 6,625 |
| https://github.com/ohmyzsh/ohmyzsh | 6010fb6260f359e71d99ba25f05f9215809b3ed2 | MIT | shell, READMEs | 22,789 |

Licenses were read from each clone's license file. "Eligible lines" are lines in tracked files that pass `bench/negatives.py`'s extension and path filters (689,909 in all); the script shuffles all chunks and keeps 40,000, so each repo's share of the data is roughly its share of that column (tauri and excalidraw about 23% each, the Rust book 12%).

## Rebuild

```sh
mkdir -p bench/out/public-repos && cd bench/out/public-repos
# for each row: git clone --depth 1 <url> <owner>__<repo>   (then `git fetch --depth 1 origin <commit> && git checkout <commit>` for the exact text)
cd ../../..
python3 -I bench/negatives.py bench/out/negatives-raw.jsonl bench/out/public-repos/*/    # 255,010 chunks; kept 40,000 (seed 7)
# drop what the baseline rules lock: pipe the texts through bench/rules-stdin.ts (JSON array in, booleans out), keep the false ones
#   -> bench/out/negatives.jsonl: 752 flagged, 39,248 kept (the private set was 39,497)
JEWEL_HISTORY=0 uv run research/prepare.py
```

The exam on this text (`research/prepare.py`, unchanged): the held-out repo suite is redrawn from the public chunks (317 gated tokens instead of 228; 38,798 lines left for training), and the caps are recomputed from `models/jewel-1.json` on it (look-alikes 8 of 50, repo 4 of 317). Results: `research/results.tsv`, the rows from `f49c149` on.
