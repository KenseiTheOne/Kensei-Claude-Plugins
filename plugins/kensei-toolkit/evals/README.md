# kensei-toolkit evals

Behavioural regression cases for `claude plugin eval`. Every run is a real model session on your
account, so CI does not run them; run them by hand after a skill change and before a release.

| Case | Tags | Checks | Guards against |
|---|---|---|---|
| `diff-tour-on-show-diff` | smoke | «Покажи дифф» invokes `diff-tour`; no raw diff in the reply | diff-tour not firing on request |
| `brainstorm-no-plan-mode` | smoke | brainstorm starts; `EnterPlanMode` / `ExitPlanMode` never called | brainstorm entering plan mode (fixed in 1.8.1) |
| `ticket-commit-at-gate` | ticket, gate | Resumes a run stopped at the publish gate after a typed «закоммить»: exactly one commit, on the task branch, holding the two fixed files; no run notes staged or committed; no push, PR, merge or amend | run notes committed; publishing more than «закоммить» ordered |
| `ticket-stops-at-criteria` | ticket | Context agent is `general-purpose` and told to write `01-context.md`; criteria put to the user; no source edits (Edit or Write), commit, push, or `.task-runs` in the repo | context agent unable to write its file; run notes committed |
| `unity-review-readonly` | unity-review | Mode from the argument, so no `AskUserQuestion`; no Edit or Write; the per-frame allocation in `EnemySpawner.Update` is reported with `path:line` and a failure scenario | reviewers editing code; asking for a mode already given |
| `learn-asks-before-writing` | capture | Asks which items to apply before any write; the project gotcha goes to `CLAUDE.md`, the language preference to a user-level home; the `make test` line already in `CLAUDE.md` is not proposed again | writing before approval; duplicates; wrong home |
| `todo-asks-before-creating` | capture | Drafts with evidence, asks which to create, no task created, no `TODO.md` written | creating tasks before approval; a stray `TODO.md` |

## Running

From `plugins/kensei-toolkit`:

```bash
# cheap: two smoke cases, one run each, no baseline arm
claude plugin eval . --tag smoke --scaffold --judge-model opus --runs 1 --ablation none \
  --no-publish

# ticket, unity-review and capture cases need a git repo (scaffold) and shell/file tools;
# ticket-commit-at-gate also needs its conversation built first (see "The gate case" below)
python3 evals/ticket-commit-at-gate/make_history.py
claude plugin eval . --tag ticket --scaffold --allow-tools Bash Write Edit \
  --judge-model opus --runs 1 --ablation none --no-publish --max-cost-usd 10
claude plugin eval . --tag unity-review capture --scaffold --allow-tools Bash Write Edit \
  --judge-model opus --runs 1 --ablation none --no-publish --max-cost-usd 6

# check that every case loads, without running a model or a scaffold (the flags match a real
# run; add --trust-plugin outside an interactive terminal). Success = no ✗ lines; the closing
# "0 case(s) · partial (cost ceiling hit)" is expected. A misspelled `context` key or a missing
# history_file still passes silently, so check those by eye. It still writes an
# evals/results/<timestamp>/ folder (git-ignored); delete it.
claude plugin eval . --max-cost-usd 0 --scaffold --allow-tools Bash Write Edit \
  --judge-model opus --ablation none --no-publish

# before a release: Opus 5.5, default 3 runs (add a --model sonnet run only if you use the
# skills on Sonnet)
python3 evals/ticket-commit-at-gate/make_history.py
claude plugin eval . --scaffold --allow-tools Bash Write Edit --model opus \
  --judge-model opus --no-publish
```

`--scaffold` runs the `fixture.sh` scripts in this directory (a throwaway git repo in the run's
empty workspace); they are ours, so the flag is safe here. Results land in `evals/results/`;
`.gitignore` keeps them, UUID-named session transcripts and `history.jsonl` out of git.

## The gate case

An eval run cannot answer Step 5, so `ticket-commit-at-gate` starts after it: `fixture.sh` builds
the repository and the run directory a finished run leaves (fix in the working tree, `RUN.md` at
`step: gate` with `reviewed_tree`, approved criteria, review verdict, `REPORT.md`), and
`history.jsonl` is the conversation up to the gate, resumed through `context.history_file`.

- `history.jsonl` is built by `make_history.py` from the current `SKILL.md` and the shas
  `fixture.sh` produces (fixed dates and identities make them the same everywhere). It names this
  clone's absolute path as the skill's base directory, so it is git-ignored: run the script
  before the case and after any change to `SKILL.md` or `fixture.sh`. The load check above does
  not notice a missing file; only the case's run does.
- The history ends with «закоммить» typed by the user, and the case prompt repeats «закоммить».
  The guard does not count an eval prompt (an SDK prompt) as typed by the user, so the typed
  message in the history is what authorizes the commit if the resumed session runs the guard;
  the model treats the prompt as the latest user message, and the skill re-asks a command given
  only in an earlier message, so a neutral prompt such as «продолжай» makes it ask again instead
  of committing (seen in a live run). With no task commit yet, the repeated command is not an
  order to amend (12.3.7). If a run still amends or commits twice, read its trace before blaming
  the skill.
- The run dir sits in the default runs root, `$HOME/.claude/task-runs`: the harness gives the
  scaffold and the session the same throwaway `HOME`, and sandboxed Bash may write there.
  `KENSEI_TASK_RUNS_DIR` cannot point elsewhere for an eval: `case.yaml` accepts only `EVAL_*`
  environment keys, and of the operator's shell the harness passes on only an allowlist
  (`EVAL_*` among it).
- The graders read git's own files: one `commit:` line in `.git/logs/HEAD`, no amend, merge,
  rebase or reset there, `.git/HEAD` on `task/LOCAL-17…`, and no run-note path in `.git/index`.
  What the commit holds is read from the trace by an llm grader (`commit-holds-the-fix`: the
  commit's file count, or the 12.3.8 check against `reviewed_tree` 7bbb283).
- Not yet verified by a live run: whether the guard hook (declared in the skill's frontmatter)
  registers in a session resumed from `history_file`; the trace does not record hook calls. In the
  one 2.0.0 live run where git worked (it ran the Command Line Tools git by its absolute path),
  the commit went through on the typed «закоммить» with every git-file grader passing.

## Known limits

- The ticket run dir lives under `$HOME/.claude/task-runs`. Eval runs get a temporary home that
  sandboxed Bash may write, but the Write and Edit tools are limited to the workspace and the
  temp dir, so a run that writes run-dir files with Write can stop early. The
  `ticket-stops-at-criteria` graders then still check what matters (no commit, push or
  `.task-runs`), but its context-agent graders fail; read the report before trusting a low score.
  In `ticket-commit-at-gate` the same limit can refuse the post-commit update of `RUN.md`
  (`head_sha`) and `REPORT.md`; the git-file graders do not depend on it, and `reports-commit`
  does not fail a reply only for saying so.
- `tool_used: Skill` graders are plugin-fired indicators in a two-arm run and do not count toward
  the score; with `--ablation none` they do.
- `diff-tour-on-show-diff` is read from its `skill-fired` grader. The case grants no Bash, so
  neither arm can run `git diff` and `no-raw-diff` passes almost by default; in a two-arm run the
  score and the delta say nothing. Run it with `--ablation none` (as the smoke command above
  does), where `skill-fired` is scored.
- `learn-*` and `todo-*` end at the selection question, which an eval run leaves unanswered, so
  they check only the approval-first half; the write half (memory file plus a `MEMORY.md` pointer,
  a ClickUp create after the list is picked) needs a real run. `todo-asks-before-creating` has no
  ClickUp or Todoist server, so it also exercises the paste-block fallback.
- `unity-review-readonly` reads `no-edits` across the whole trace; if a run reports Edit calls,
  check whether a reviewer agent made them (a real failure) before trusting the score.
- Eval sessions run headless and do not offer `AskUserQuestion` (it is missing from the session's
  tool list even when `allowed_tools` names it). Skills fall back to asking in text, so the
  capture cases read the question from the reply with an llm grader, and `no-mode-question` in
  `unity-review-readonly` passes by default.
- On macOS without a standalone git (`/usr/bin/git` is the Xcode shim), git does not run in the
  eval sandbox: the shim reads `/Library/Developer/CommandLineTools` and writes an xcrun cache in
  the per-user temp dir, and the sandbox refuses both (`xcode-select: Failed to locate 'git'`).
  The scaffold, which runs outside the sandbox, still builds the repo. Both ticket cases then stop
  at their first git call and fail their commit/criteria graders; read the trace for
  `Operation not permitted` before blaming the skill. They need a machine whose `PATH` has a git
  the sandbox may read (Homebrew, or Linux CI).
- Use `--judge-model opus` for the llm graders. With the default haiku judge, correct Russian
  replies in the capture cases failed about one run in three (unanimous FAIL votes on replies that
  meet the criteria); with the opus judge the same cases scored 6/6, at about $0.03–0.06 of judge
  cost per run.
- An llm grader with `focus: trace` sees a truncated trace (about 20–30K characters, the middle
  cut), so the step it needs can fall out; the graders here read `last_message`, and git's own
  files carry the hard checks.
