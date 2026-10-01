# ticket — pipeline (Steps 6–11)

Loaded after the user approves mode and criteria in `SKILL.md` Step 5. Execute in order.
Update `RUN.md` (`step:` field) as you move — a run interrupted here must be resumable.

Throughout: `<run_dir>` is the run directory from `SKILL.md` Step 1; `<root>` is the worktree if
`RUN.md` records one, otherwise the repository root; criteria always means
`02-criteria.approved.md`, never the draft. Run every git command from `<root>`, and take
`status` only in the form Step 1 recorded it. Every agent prompt below ends with the block from
`SKILL.md`, "Agents" — shown as `<the "Agents" block>`.

Rule 7 holds here as everywhere: the only publish actions possible in Steps 6–11 are a status
or a comment the user ordered for right away (`SKILL.md`, "Commands"), a comment always through
`publish.md`, "Task comments". When Step 11 is done, read `publish.md` for Step 12.

Wherever a step below says "stop, outcome `blocked`" (or `tampered`), the pipeline ends there and
goes to Step 12: `REPORT.md` is written for every outcome.

---

## probe mode — short path

`probe` answers a question; it does not change code. It runs the steps below and then Step 12;
Steps 6, 7, 10 and 11 and the snapshot of Step 8 do not apply.

1. The context agent from Step 3 has already reported. If the ticket asks whether a defect
   still reproduces, spawn **one** verification agent:

   ```
   Find out whether this still happens. Ticket: <run_dir>/00-ticket.md. Criteria:
   <run_dir>/02-criteria.approved.md. Context: <run_dir>/01-context.md.
   Look for evidence both ways — the code path that would produce the defect and the code that
   would prevent it. Write your findings to <run_dir>/04-review-1.md; that is the only file you
   create or edit.
   <the "Agents" block>
   ```

2. Run the test channel (Step 9) if a relevant test can decide it, and capture `agent-visual`
   evidence the same way.
3. Run the baseline check (Step 8.2, with an empty whitelist) — the agents must have left git
   as they found it.
4. Write `REPORT.md` with outcome `probe` and go to Step 12 (`publish.md`). There is nothing to
   commit or push, and the skill suggests no status change. If the answer is "yes, it still
   reproduces", the report ends with a concrete recommendation and the suggested mode for a
   follow-up run.

---

## Step 6 — Acceptance tests and the red phase (`full` only)

`fix` skips this step.

Spawn the **test-author** agent:

```
You write acceptance tests. You do not write production code, and you do not modify it —
not to make a test pass, not to "fix an obvious bug you noticed". Report such findings
instead; someone else will act on them.

Acceptance criteria: <run_dir>/02-criteria.approved.md — read it, do not edit it.
Context: <run_dir>/01-context.md

Write one test per criterion marked `auto`. Put the criterion tag in the test name, e.g.
`AC3_...`, so a report can be matched back to criteria mechanically.

These tests must fail right now, against the current implementation: a test that passes
before the work exists proves nothing. If a test passes immediately, either the criterion is
already satisfied — say so explicitly — or the test is tautological and you rewrite it.

In your reply: one line per test with `file:line`, its criterion tag, and whether you
confirmed it currently fails; then every other file you created, modified or deleted
(helpers, fixtures, asmdef, `.meta`).
<the "Agents" block>
```

Then **verify the red phase yourself** by running the test channel (Step 9, including its
test-dirt rule). Any acceptance test that is already green is either a satisfied criterion
(record it as such in `RUN.md`) or a tautology (send it back once; if it survives a second time,
mark the criterion `NOT PROVEN` and carry on — do not spend the run here).

Record in `RUN.md` the `sha256` of every acceptance test file. Together with the criteria hash
these form the frozen set.

---

## Step 7 — Implementer

Spawn the **implementer** agent:

```
Acceptance criteria: <run_dir>/02-criteria.approved.md — read only.
Context: <run_dir>/01-context.md
[full] Acceptance tests: <paths> — read only.

You edit production code only. The criteria file and the acceptance test files are compared
with hashes recorded before you started; a mismatch stops the run and is reported, so editing
them does not help you.

These files carry the user's own uncommitted work from before this run: <baseline dirty paths,
or "none">. Leave them alone if you can. If you must edit one, keep what was already there.

If a criterion cannot be met as written, do not soften it: implement what you can, then state
plainly which criterion you could not meet and why. "Not done, here is why" is a valid and
useful outcome; silently redefining the target is not.

Write what you changed and why to <run_dir>/03-changes.md.
In your reply: every file you touched (created, modified or deleted) with `file:line`,
decisions taken, anything you could not do.
<the "Agents" block>
```

The block's project rules carry the guardrails `.claude/task-flow-rules.md` names (banned APIs,
forbidden directories, style guards enforced by hooks): an implementer that trips a hook without
knowing it exists burns a round rediscovering it.

---

## Step 8 — Snapshot, then produce the diff

Order matters. The reviewer must judge exactly the tree a later commit will contain — and
nothing is committed here. The snapshot is a git tree built in a private index file in the
repository's git directory: it includes new files and deletions, applies `.gitattributes`
filters like any `git add`, and leaves `HEAD`, the branch and the user's own index untouched.

1. **Collect the whitelist — files only.** The union of every file reported so far by every
   implementer round (a round ordered at the gate included — `publish.md`, "Changes after the
   gate") and, in `full`, by the test-author, plus the acceptance test files. It only
   grows from round to round; a file a later round restored simply produces no diff. Never a
   directory (expand it into its files and check each against the Step 1 status), never a
   wildcard, never `git add -A` / `-u`, never "whatever is dirty". A path that exists neither on
   disk nor in `base_sha` (`git cat-file -e <base_sha>:<path>` fails) was created and removed
   within the run: leave it out of the snapshot's `git add` (here and in 12.3.1) but keep it in
   the whitelist — after a commit it is a deletion the next commit must stage.
2. **Baseline check — git is as the agents found it.** `HEAD` equals `head_sha` if `RUN.md`
   records one (a commit exists), otherwise `base_sha`. The current branch, the staged column of
   `status` (plus `staged_by_run:`), and `refs/stash` match the baseline (as re-taken after a
   Step 5 stash or worktree, after a commit, or after a gate change switched back to the task
   branch). Every baseline path outside the whitelist and
   outside `test_dirt:` still has its recorded hash. Any difference means an agent committed,
   staged, stashed, switched, reverted, or edited a file it did not report — stop, outcome
   `blocked`, tell the user exactly what differs, undo nothing.
3. **Overlap with the user's work.** A whitelisted path that was already dirty in the baseline
   carries the user's pre-run changes into the snapshot, the diff and any commit — a file cannot
   be split. Record such paths in `RUN.md` as `overlap:`; `git diff <baseline blob> <path>` shows
   what the run changed on top. They are shown first at the gate, and a commit waits for the
   user to confirm them.
4. **Build the snapshot.** Get the index path once and record it in `RUN.md` as `snapshot_index`:
   `git rev-parse --path-format=absolute --git-path ticket-<task_id>.index`. Then one Bash call
   with that path written out literally, chained with `&&` so a failed step prints no tree
   (`set -e` is not enough: it is ignored inside a subshell tested by `&&` or `||`):

   ```bash
   GIT_INDEX_FILE=<snapshot_index> git read-tree <base_sha> &&
   GIT_INDEX_FILE=<snapshot_index> git add -- <file> <file> … &&   # a file deleted from base records the deletion
   GIT_INDEX_FILE=<snapshot_index> git write-tree                  # prints the snapshot tree sha
   ```

   `read-tree` replaces whatever the index file held, so nothing needs deleting first.

   Any error → outcome `blocked`, quote git's message, and never record a tree from a failed
   build. Never force-add an ignored path (`-f`). Once the tree is built, record the whitelist
   and `snapshot_tree` = its sha in `RUN.md` right away, before the checks below can stop the run.
5. **Nothing left out.** Compare `status` with the baseline: every path that became dirty since
   then must be in the whitelist. A dirty path outside it means an agent changed something it
   did not report (a generated `.meta`, a touched config) — stop, outcome `blocked`, list the
   paths. Do not widen or narrow the whitelist silently. Pre-existing dirt and `test_dirt:`
   (Step 9) are expected and fine — so is a path the project declares as rewritten by its engine
   or test runner on every run (project rules, or a pipeline config's list such as
   `generated_paths`) that no agent reported; record it as `test_dirt:`.
6. **Verify the frozen set:** recompute `sha256` for the criteria file and every acceptance test
   and compare with the hashes in `RUN.md` (after an addendum, the hash recorded with it). Any
   mismatch → stop the run, outcome `tampered`, and say exactly which file changed.
7. **Check the commit guards now, not after the review.** Find what would guard the commit: git
   hooks (`pre-commit`, `commit-msg` under `core.hooksPath` or `.git/hooks`), Claude Code
   PreToolUse hooks in `.claude/settings*.json` whose matcher covers the Bash tool (`Bash`, `*`) —
   read each script to see whether it acts on `git commit` and what it inspects — and
   `.claude/task-flow-rules.md`. Check the snapshot against what each one enforces — e.g. a guard
   demanding a `.meta` beside every new Unity asset is checked against
   `git diff --name-status --no-renames --diff-filter=A <base_sha> <tree>`. Run a git-native hook
   against the snapshot (`GIT_INDEX_FILE=<snapshot_index> git hook run pre-commit`) only if
   you have read the whole script, it neither rewrites files nor runs a git command that writes,
   and it does not hand off to a framework (pre-commit, lint-staged/husky, lefthook) — those stash
   or check out "unstaged" changes, which under the snapshot index are the user's dirty files.
   Otherwise check what it enforces by reading it. A guard that would reject → stop, outcome
   `blocked`, quote its reason. Never trim the whitelist to get past a guard.
8. **Produce the diff:** `git diff <base_sha> <tree> > <run_dir>/03-diff.patch`. From the branch
   point, so it contains the acceptance tests as well as the implementation — the reviewer needs
   both to spot a test written to fit the code.
9. `snapshot_tree` (recorded in 8.4) becomes `reviewed_tree` only once Step 10 has judged it.

---

## Step 9 — Run the test channel

Find the test command in this order, first hit wins:

1. A test command the user's instructions for this run name (`SKILL.md`, Step 0).
2. A machine-readable test report the project declares, in `.claude/task-flow-rules.md` or its
   pipeline config — for example `test_report_parts` / `commands.test_report` in a
   `pipeline.config.json` at the repo root. It names each test and each unavailable part, which
   an exit code does not, so it wins over a plain command.
3. A test command named in `.claude/task-flow-rules.md`.
4. The project's obvious test command from `package.json`, a solution file, or `CLAUDE.md`.

Run every part. Then capture the evidence for every `agent-visual` criterion yourself, the way
the project's verification map or skill describes (01-context.md names it): a screenshot or a
log through the available tool, saved under `<run_dir>/evidence/AC<n>-<what>.<ext>`. Look at it
before you judge.

Tests and captures must come from `<root>`'s own build. An editor, an editor's MCP test runner or
a device attached to another checkout — the main checkout, when the run works in a worktree —
proves nothing about this one: a criterion it would decide is `NOT PROVEN`, with that reason.

For each acceptance criterion, resolve one of:

- **proven by test** — a test tagged with that criterion ran and passed.
- **checked by eye** — no automatable test; you looked at captured evidence (name its path) or a
  human looked (say who).
- **NOT PROVEN** — nothing decided it: the channel was unavailable, the editor was open, the
  device was missing, the part errored, the screenshot tool failed. A part that reports itself
  unavailable does not turn into a pass. An unproven criterion is reported as unproven, to the
  user and in any comment the user orders; it never becomes silence. A `manual` criterion stays
  `NOT PROVEN — needs a human look` until a human has looked.

Record the per-criterion outcome table in `RUN.md`, with evidence paths.

**Tests already failing on `base_sha`.** If the user's instructions for this run or the project
rules name them (or a file listing them), a failure listed there is pre-existing: report it
apart, under "failing before the run", and never count it against the run or the reviewer's
verdict. An acceptance test is never on that list — it did not exist on `base_sha`.

**Test dirt.** Every test run — this one, the red phase in Step 6, and whatever the reviewer runs in
Step 10 — can write files. Take `status` right before and after each run (for the reviewer: before
it starts and after it returns) and re-hash the baseline paths outside the whitelist. A path that
became dirty, or a baseline path whose hash changed, and is not in the whitelist (in Step 6: not
among the test-author's reported files) was written by the tests: record it as `test_dirt:` in
`RUN.md`. Steps 8.2 and 8.5 do not count it against the agents, and it never enters a snapshot or a
commit. If a test run overwrote a file that held the user's uncommitted change, tell them — the
pre-run content is the recorded blob.

---

## Step 10 — Review

Spawn a **fresh** agent — one that has not seen the implementer's reasoning. That freshness is
the entire mechanism; do not also blindfold it.

```
You are reviewing a change you did not write, against criteria you did not choose.

Acceptance criteria: <run_dir>/02-criteria.approved.md
Diff from the branch point: <run_dir>/03-diff.patch
Snapshot under review: tree <snapshot_tree>
Test results and evidence: <the per-criterion table from Step 9, with evidence paths>
[if overlap] These files already carried the user's own uncommitted changes before the run,
each with its pre-run blob: <path> <baseline blob sha>, one per line. `git diff <blob> <path>`
shows only what the run changed in them; a removed pre-run line that no criterion requires is
blocking.
You have Read, Grep and Bash over the working tree — open any file you need in full. The diff
is a starting point, not your only evidence. Do not read 03-changes.md: the implementer's own
account of the work is exactly what you are here to check independently. Bash is for reading
and running tests. Write the full verdict to <run_dir>/04-review-N.md; that is the only file
you create or edit.

For every acceptance test, answer explicitly: name a concrete change to production code that
would make this test fail. If you cannot name one, the test does not test anything — report it
as a blocking finding. A test that stays green against a hollowed-out implementation is the
specific failure this review exists to catch.

Then judge each criterion: met / not met / not proven, with `file:line` evidence. Open the
evidence files of `checked by eye` criteria and say whether they show what the criterion asks.

Severity — what goes back for another round versus what goes in the report:
  blocking (another round): an unmet criterion, or a defect you can point at with `file:line`
    and describe as a concrete failure.
  report only (no round): style, naming, structure you would have done differently, ideas for
    later. Real, worth writing down, not worth a round trip.

In your reply: blocking findings first, each with `file:line`.
<the "Agents" block>
```

**More than one reader at once.** When you split the review between parallel agents (or run it
as a workflow), the working tree can change under them. Each reader then takes the changed files
from the snapshot — `git show <snapshot_tree>:<path>` — and any test run that writes files (the
red phase, a test channel run) has finished before the readers start.

When the verdict is in, record `reviewed_tree` = the `snapshot_tree` it judged. Each round
overwrites it; the last reviewed tree is what a commit must reproduce.

---

## Step 11 — The loop, capped at 2 rounds

If there are blocking findings, send them back to a **new** implementer agent (the criteria and
tests stay frozen; hashes are re-verified in Step 8 every round). Then repeat Steps 8–10.

**Cap: 2 rounds.** If the second review still has blocking findings, a third round does not
start: the outcome is `stopped`, and the report names precisely which criteria remain unmet and
what the reviewer said about each. An honest stop after two rounds is a result; an endless loop
is a bill. A change the user orders at the publish gate runs one more round outside the cap
(`publish.md`, "Changes after the gate").

If a round produces no blocking findings, the outcome is `accepted`. Either way, read
`publish.md` and go to Step 12.
