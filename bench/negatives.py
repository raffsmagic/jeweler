# Harmless real text for training negatives: tracked source and docs from our repos.
#   python3 bench/negatives.py bench/out/negatives-raw.jsonl ~/code/repo-a ~/code/repo-b ...
# then drop anything the baseline rules flag (see README). Use public text (open-source repos, Stack Exchange,
# Wikipedia) for a model you publish; private repos are fine for a model you keep to yourself.
# Skips env/key/config files, and any line our rules would lock (so no real key slips in).
import json, random, re, subprocess, sys
from pathlib import Path
random.seed(7)
repos = sys.argv[2:]
exts = {".ts", ".tsx", ".md", ".py", ".rs", ".swift", ".css", ".sh", ".yml", ".yaml", ".sql", ".html"}
bad = re.compile(r"env|secret|credential|key|token|password|fixture|test|\.lock$", re.I)
out = []
for r in repos:
    root = Path(r).expanduser()
    if not (root / ".git").exists(): continue
    files = subprocess.run(["git", "-C", str(root), "ls-files"], capture_output=True, text=True).stdout.split("\n")
    for f in files:
        p = root / f
        if p.suffix not in exts or bad.search(f) or not p.is_file() or p.stat().st_size > 400_000: continue
        try: lines = p.read_text(errors="ignore").splitlines()
        except Exception: continue
        i = 0
        while i < len(lines):
            n = random.choice([1, 1, 1, 2, 3, 6])
            chunk = "\n".join(l for l in lines[i:i+n]).strip()
            i += n
            if 3 <= len(chunk) <= 600: out.append(chunk)
random.shuffle(out)
Path(sys.argv[1]).write_text("".join(json.dumps({"text": t}) + "\n" for t in out[:40000]))
print(len(out), "chunks; kept", min(40000, len(out)))
