# ticket — pipeline (Steps 6–11)

Loaded after Step 5. Execute in order and keep `step:` in `RUN.md` current, so a run can resume.

`<run_dir>` is from `SKILL.md` Step 1; `<root>` is the recorded worktree, else the repository
root; "criteria" is always `02-criteria.approved.md`. Run git from `<root>`, `status` only in the
Step 1 form. `<the "Agents" block>` is the block from `SKILL.md`, "Agents". A mid-run status or
comment the user orders goes through `publish.md`.

Every outcome leads to Step 12 (`publish.md`), which writes `REPORT.md`: "stop, outcome
`blocked`" (or `tampered`) ends the pipeline there.

---

## probe mode — short path

`probe` answers a question and changes no code: no Steps 6, 7, 10, 11, no snapshot.

1. If the ticket asks whether a defect still reproduces, spawn **one** verification agent:

   ```
   Find out whether this still happens. Ticket: <run_dir>/00-ticket.md. Criteria:
   <run_dir>/02-criteria.approved.md. Context: <run_dir>/01-context.md.
   Look for evidence both ways — the code path that would produce the defect and the code that
   would prevent it. Write your findings to <run_dir>/04-review-1.md, the only file you create
   or edit.
   <the "Agents" block>
   ```

2. Run the test channel (Step 9) if a test can decide it; capture `agent-visual` evidence.
3. Run the Step 8.2 check with an empty whitelist.
4. Outcome `probe`, Step 12. Nothing to commit, no status suggested. "Yes, it reproduces" ends
   with a concrete recommendation and the mode for a follow-up run.

---

## Step 6 — Acceptance tests and the red phase (`full` only)

Spawn the **test-author**:

```
You write acceptance tests. You do not write or modify production code — not to make a test
pass, not to fix an obvious bug; report such findings instead.

Acceptance criteria: <run_dir>/02-criteria.approved.md — read only.
Context: <run_dir>/01-context.md

Write one test per criterion marked `auto`, the criterion tag in its name (`AC3_...`).
Each must fail now, against the current implementation. One that passes immediately is either
an already satisfied criterion (say so) or a tautology (rewrite it).

Reply: one line per test — `file:line`, criterion tag, confirmed failing or not; then every
other file you created, modified or deleted (helpers, fixtures, asmdef, `.meta`).
<the "Agents" block>
```

**Verify the red phase yourself** with the test channel (Step 9, test dirt included). An already
green test is a satisfied criterion (record it) or a tautology (send it back once; a second time,
mark the criterion `NOT PROVEN` and go on). Record each acceptance test file's `sha256` in
`RUN.md`: with the criteria hash, the frozen set.

---

## Step 7 — Implementer

```
Acceptance criteria: <run_dir>/02-criteria.approved.md — read only.
Context: <run_dir>/01-context.md
[full] Acceptance tests: <paths> — read only.

You edit production code only. The criteria and acceptance tests are checked against hashes
taken before you started; a mismatch stops the run.

These files carry the user's uncommitted work from before this run: <baseline dirty paths, or
"none">. Leave them alone if you can; if you must edit one, keep what was there.

If a criterion cannot be met as written, do not soften it: implement what you can and state
which criterion you could not meet and why.

Write what you changed and why to <run_dir>/03-changes.md.
Reply: every file you created, modified or deleted with `file:line`, decisions, what you could
not do.
<the "Agents" block>
```

The block's project rules carry the guardrails (banned APIs, forbidden directories, hook-enforced
style), so the implementer does not burn a round rediscovering them.

---

## Step 8 — Snapshot, then the diff

The reviewer judges exactly the tree a commit would hold. The snapshot is a tree built in a
private index file: new files and deletions included, `.gitattributes` applied, `HEAD`, branch
and the user's index untouched.

1. **Whitelist — files only:** every file reported by every implementer round (a gate round
   included) and, in `full`, the test-author, plus the acceptance tests. It only grows. No
   directories (expand and check each file against the baseline), no wildcards, never "whatever
   is dirty". A path neither on disk nor in `base_sha` stays in the whitelist but out of the
   snapshot's `git add` (after a commit it is a deletion to stage).
2. **Baseline check:** `HEAD` = `head_sha` if recorded, else `base_sha`; branch, the staged
   column (plus `staged_by_run:`) and `refs/stash` as baselined (re-taken after a stash, worktree,
   commit or gate switch); every baseline path outside the whitelist and `test_dirt:` still has
   its hash. Any difference → outcome `blocked`, say exactly what differs, undo nothing.
3. **Overlap:** a whitelisted path that was dirty at baseline carries the user's changes into
   the commit (a file cannot be split). Record it as `overlap:`; `git diff <baseline blob>
   <path>` shows the run's part. Shown first at the gate; a commit waits for the user's
   confirmation.
4. **Build:** record `snapshot_index` =
   `git rev-parse --path-format=absolute --git-path ticket-<task_id>.index`, then one Bash call,
   path written literally, chained with `&&` so a failure prints no tree:

   ```bash
   GIT_INDEX_FILE=<snapshot_index> git read-tree <base_sha> &&
   GIT_INDEX_FILE=<snapshot_index> git add -- <file> <file> … &&
   GIT_INDEX_FILE=<snapshot_index> git write-tree                  # the snapshot tree sha
   ```

   An error → `blocked`, quote git, record no tree. Never `-f`. Record the whitelist and
   `snapshot_tree` in `RUN.md` at once.
5. **Nothing left out:** every path dirty since baseline is in the whitelist, in the baseline,
   in `test_dirt:`, or declared by the project as rewritten on every run (rules, or a pipeline
   config's `generated_paths`; record it as `test_dirt:`). Anything else → `blocked`, list it.
   Never adjust the whitelist silently.
6. **Frozen set:** recompute the `sha256` of the criteria (after an addendum, its new hash) and of
   every acceptance test. A mismatch → outcome `tampered`, name the file.
7. **Commit guards, now:** git hooks (`pre-commit`, `commit-msg`, under `core.hooksPath` or
   `.git/hooks`), PreToolUse hooks in `.claude/settings*.json` matching Bash (read each script
   for what it does on `git commit`), and project rules. Check the snapshot against each — e.g. a
   `.meta` beside every new Unity asset against `git diff --name-status --no-renames
   --diff-filter=A <base_sha> <tree>`. Run a hook on the snapshot
   (`GIT_INDEX_FILE=<snapshot_index> git hook run pre-commit`) only after reading all of it, if it
   rewrites nothing, runs no writing git command and hands off to no framework (pre-commit,
   husky/lint-staged, lefthook stash the user's files). One that would reject → `blocked`, quote
   it; never trim the whitelist to pass.
8. **Diff:** `git diff <base_sha> <tree> > <run_dir>/03-diff.patch` — tests and implementation
   together, so the reviewer can spot a test fitted to the code.

---

## Step 9 — Test channel

The test command, first hit wins:

1. one named in the user's instructions for this run;
2. a machine-readable report the project declares (rules, or `pipeline.config.json`
   `test_report_parts` / `commands.test_report`) — it names each test and unavailable part;
3. one named in `.claude/task-flow-rules.md`;
4. the obvious one (`package.json`, a solution file, `CLAUDE.md`).

Run every part, then capture each `agent-visual` criterion as the verification map describes, to
`<run_dir>/evidence/AC<n>-<what>.<ext>`, and look at it before judging. Tests and captures come
from `<root>`'s own build; an editor, its MCP test runner or a device attached to another checkout
proves nothing here (`NOT PROVEN`, with that reason).

Per criterion:

- **proven by test** — a test tagged with it ran and passed;
- **checked by eye** — you looked at named evidence, or a named human looked;
- **NOT PROVEN** — nothing decided it (channel unavailable, editor open, device missing, part
  errored, capture failed). An "unavailable" part is no pass. `manual` stays `NOT PROVEN — needs
  a human look` until a human looked.

Record the table with evidence paths in `RUN.md`.

**Failing on `base_sha`:** failures the user's instructions or project rules list as
pre-existing are reported apart ("failing before the run") and never count against the run. An
acceptance test is never among them.

**Test dirt:** take `status` and re-hash baseline paths outside the whitelist before and after
each test run — the red phase, this step, and the whole reviewer agent. A path that changed and
is not whitelisted (in Step 6: not reported by the test-author) is `test_dirt:`; it never enters
a snapshot or commit. If it overwrote a user's uncommitted change, tell them (the blob holds it).

---

## Step 10 — Review

A **fresh** agent, which has not seen the implementer's reasoning — that is the mechanism; do not
also blindfold it.

```
You review a change you did not write, against criteria you did not choose.

Acceptance criteria: <run_dir>/02-criteria.approved.md
Diff from the branch point: <run_dir>/03-diff.patch
Snapshot under review: tree <snapshot_tree>
Test results and evidence: <the Step 9 table, with evidence paths>
[if overlap] These files carried the user's uncommitted changes before the run: <path> <blob>,
one per line. `git diff <blob> <path>` shows the run's part; a removed pre-run line no criterion
requires is blocking.
You have Read, Grep and Bash over the tree; the diff is a starting point. Do not read
03-changes.md — the implementer's account is what you check independently. Bash is for reading
and running tests. Write the verdict to <run_dir>/04-review-N.md, the only file you create.

For every acceptance test, name a concrete production-code change that would make it fail. If
you cannot, it tests nothing — blocking.
Judge each criterion: met / not met / not proven, with `file:line`. Open the evidence of
`checked by eye` criteria and say whether it shows what the criterion asks.

blocking (another round): an unmet criterion, or a defect you can show at `file:line`.
report only: style, naming, structure, ideas for later.

Reply: blocking findings first, each with `file:line`.
<the "Agents" block>
```

Parallel readers (or a workflow) read changed files from the snapshot
(`git show <snapshot_tree>:<path>`), and start only after every file-writing test run ended.

Record `reviewed_tree` = the `snapshot_tree` judged; each round overwrites it.

---

## Step 11 — The loop, at most 2 rounds

Blocking findings → a **new** implementer (criteria and tests stay frozen), then Steps 8–10
again. If the second review still has blocking findings, the outcome is `stopped`, and the
report names each unmet criterion with the reviewer's words. A round with no blocking findings →
`accepted`. A change ordered at the gate runs one round outside the cap (`publish.md` 12.7).
Then read `publish.md`: Step 12.
