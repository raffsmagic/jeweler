export const meta = {
  name: 'autoresearch',
  description: 'Jewel autoresearch: one agent per experiment edits research/train.py, runs the frozen exam, keeps or reverts; a reviewer checks the kept changes',
  whenToUse: 'Run a batch of autoresearch experiments on Jewel (research/program.md). args: { experiments: 16, tag: "oct5" }. Setup (branch, results.tsv header) must be done first.',
  phases: [
    { title: 'Experiments', detail: 'sequential; one change each; keep if fp94 improves, revert otherwise' },
    { title: 'Review', detail: 'adversarial check of the kept commits every four experiments' },
  ],
}

const N = Number(args?.experiments ?? 12)
const TAG = String(args?.tag ?? 'run')
const REPO = process.env.JEWEL_REPO ?? '.'

const EXP = {
  type: 'object',
  properties: {
    commit: { type: 'string' },
    fp94: { type: 'number' },
    fresh94: { type: 'number' },
    kb: { type: 'number' },
    status: { type: 'string', enum: ['keep', 'discard', 'crash'] },
    description: { type: 'string' },
    insight: { type: 'string', description: 'one or two sentences: what this result teaches about Jewel' },
  },
  required: ['commit', 'fp94', 'status', 'description', 'insight'],
}
const REVIEW = {
  type: 'object',
  properties: {
    ok: { type: 'boolean' },
    problems: { type: 'array', items: { type: 'string' } },
    notes: { type: 'string' },
  },
  required: ['ok', 'problems', 'notes'],
}

const experimentPrompt = (i, note) => `You are the autoresearch agent for Jewel. Repo: ${REPO}. Branch: autoresearch/${TAG}. Run exactly ONE experiment (number ${i} of this batch) by following research/program.md to the letter, then return the structured result. Never ask the human anything; never stop early.

Procedure:
1. Read research/program.md fully, then research/results.tsv, research/train.py, and \`git log --oneline -8 -- research/train.py\`. Confirm \`git branch --show-current\` prints autoresearch/${TAG}; if it does not, return status "crash" with description "wrong branch" and change nothing.
2. If results.tsv has only the header row, this experiment is the baseline: do not edit train.py; use the current HEAD hash; run and log it as "keep" with description "baseline (<what train.py is at HEAD, from its last commit message>)" plus "guards no (...)" if guards_ok is no.
3. Otherwise pick ONE idea that results.tsv shows was not tried yet (read the descriptions and statuses: build on keeps, don't repeat discards at the same dose). Use "What we already know" and "Levers" in program.md. Prefer the simplest change with the largest expected effect on fp94. ${note}
4. Edit research/train.py (the only file you may edit). Commit with \`git commit -m "<short description>" -- research/train.py\` and note \`git rev-parse --short HEAD\`.
5. Run \`cd ${REPO} && uv run research/train.py > research/run.log 2>&1\` (Bash timeout 420000 ms; still running after that: kill it, log crash with the reason, revert). Then run the grep from program.md ("Read the key numbers").
6. Empty grep = crash: \`tail -n 40 research/run.log\`; fix a dumb error with \`git commit --amend --no-edit -- research/train.py\` and rerun, at most twice; otherwise log "crash" and revert.
7. Append the row to research/results.tsv exactly as program.md specifies (tabs; no tabs or commas in the description).
8. Keep only if limits_ok is yes AND guards_ok is yes AND fp94 is strictly lower than the best kept fp94 in results.tsv. Otherwise revert with \`git reset --soft HEAD~1 && git checkout HEAD -- research/train.py\`.
9. Verify: \`git status --short research/\` shows train.py clean, and \`tail -1 research/results.tsv\` is your row.

Rules that matter most: edit only research/train.py; never git add -A, git stash, git reset --hard or switch branches (the working tree holds other people's uncommitted work); never print or look at any text from the exam suites; never use words from bench/everyday.json or bench/holdout.py in a generator; the real passwords are in memory only. Return: commit, fp94, fresh94 (first number), kb, status, description (as logged), insight.`

const reviewPrompt = () => `You are an adversarial reviewer of Jewel's autoresearch run (repo ${REPO}, branch autoresearch/${TAG}). Read research/program.md ("You cannot", "Git, safely") and research/results.tsv. List the commits on this branch that touch research/train.py after the setup commit (its message starts with "Autoresearch for Jewel"): \`git log --oneline -- research/train.py\`. For every commit still on the branch (these are the kept ones), read \`git show <hash> --stat\` and the diff. Try to prove the run is cheating or sloppy:
- any file other than research/train.py changed in an experiment commit;
- train.py reading bench/everyday.json, bench/holdout.py, bench/out/dataset.jsonl, the wild list URL, or copy history export;
- generators using words from bench/everyday.json or from WORDS in bench/holdout.py (open both and compare);
- anything writing exam text or real passwords to disk or printing it;
- results.tsv rows inconsistent with the commits (a kept row whose hash is not on the branch, or a discarded hash that is);
- a kept row whose run broke limits_ok or guards_ok (rerun nothing; judge from results.tsv descriptions and the diffs);
- complexity added without proportional fp94 gain (program.md's simplicity criterion).
Do not modify any file or run train.py. Return ok (true only if no problem), problems (each one line, with the commit hash), and notes (two or three sentences on where the run is heading and what to try next).`

phase('Experiments')
const rows = []
let note = ''
for (let i = 1; i <= N; i++) {
  const r = await agent(experimentPrompt(i, note), { label: `experiment ${i}`, phase: 'Experiments', schema: EXP })
  if (r) {
    rows.push(r)
    log(`#${i} ${r.status} fp94=${r.fp94} fresh94=${r.fresh94 ?? '?'} kb=${r.kb ?? '?'} ${r.description}`)
  } else {
    log(`#${i} returned nothing`)
  }
  if (i % 4 === 0 && i < N) {
    const rev = await agent(reviewPrompt(), { label: `review after ${i}`, phase: 'Review', schema: REVIEW })
    if (rev) {
      note = rev.ok ? '' : `A reviewer flagged problems with earlier kept commits: ${rev.problems.join('; ')}. Fix that first (one experiment may undo the offending change) before trying new ideas.`
      log(`review after ${i}: ${rev.ok ? 'ok' : rev.problems.length + ' problem(s)'}; ${rev.notes}`)
    }
  }
}
const kept = rows.filter((r) => r.status === 'keep')
return { experiments: rows.length, kept: kept.map((r) => ({ commit: r.commit, fp94: r.fp94, fresh94: r.fresh94, kb: r.kb, description: r.description })), insights: rows.map((r) => `${r.status}: ${r.description}. ${r.insight}`) }
