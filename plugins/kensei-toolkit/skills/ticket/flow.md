# ticket — pipeline (Steps 6–12)

Loaded after the user approves mode and criteria in `SKILL.md` Step 5. Execute in order.
Update `RUN.md` (`step:` field) as you move — a run interrupted here must be resumable.

Throughout: `<run_dir>` = `~/.claude/task-runs/<repo-name>/<task_id>/`, and criteria always
means `02-criteria.approved.md`, never the draft. Run every git command from the repo root, and
take `status` only in the form Step 1 recorded it.

Nothing in Steps 6–11 commits or pushes. The only tracker writes possible there are a status or a
comment the user ordered for right away (`SKILL.md`, "Commands" — timing follows the command), a
comment always through "Task comments". Step 12 stops at the publish gate and acts only on the
user's commands.

In an unattended run (`SKILL.md`, "Unattended") every stop and question below takes the default
from that section's table, and every agent prompt below also carries the caller's instructions.

---

## probe mode — short path

`probe` answers a question; it does not change code. Skip Steps 6–8 and 11 entirely.

1. The context agent from Step 3 has already reported. If the ticket asks whether a defect
   still reproduces, spawn **one** verification agent: give it the ticket, the criteria, and
   instruct it to look for evidence *both* ways — the code path that would produce the defect
   and the code that would prevent it. It changes nothing but `04-review-1.md`: no other
   edits, no git command that writes, no tracker calls. Reply cap: 40 lines. Full findings to
   `<run_dir>/04-review-1.md`.
2. Run the test channel (Step 9) if one exists and a relevant test can decide it.
3. Run the baseline check (Step 8.2, with an empty whitelist) — the agents must have left git
   as they found it.
4. Write `REPORT.md` with outcome `probe` and stop at the publish gate (Step 12; unattended:
   its "Unattended end"). There is
   nothing to commit or push, and the skill suggests no status change (the user may still order
   one — 12.6). The answer reaches the tracker only if the user orders a comment — then through
   "Task comments" in `SKILL.md`. If the answer is "yes, it still reproduces", the report ends
   with a concrete recommendation and the suggested mode for a follow-up run.

---

## Step 6 — Acceptance tests and the red phase (`full` only)

`fix` skips this step. `full` does not.

Spawn the **test-author** agent:

```
You write acceptance tests. You do not write production code, and you do not modify it —
not to make a test pass, not to "fix an obvious bug you noticed". Report such findings
instead; someone else will act on them.

Acceptance criteria: <run_dir>/02-criteria.approved.md — read it, do not edit it.
Context: <run_dir>/01-context.md
Project conventions: <from .claude/task-flow-rules.md if present>

Write one test per criterion marked `auto`. Put the criterion tag in the test name, e.g.
`AC3_...`, so a report can be matched back to criteria mechanically.

These tests MUST fail right now, against the current implementation. A test that passes
before the work exists proves nothing. If a test passes immediately, either the criterion is
already satisfied — say so explicitly — or the test is tautological and you must rewrite it.

You run no git command that writes — no add, commit, push, stash, checkout, switch, restore,
reset, clean, rm or mv; to undo your own edit, edit the file back. You do not write to the
tracker. The orchestrator owns git and the tracker.

Reply: at most 40 lines — one line per test with `file:line`, its criterion tag, and whether
you confirmed it currently fails; then every other file you created, modified or deleted
(helpers, fixtures, asmdef, `.meta`).
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
Acceptance criteria: <run_dir>/02-criteria.approved.md  — READ ONLY.
Context: <run_dir>/01-context.md
[full] Acceptance tests: <paths> — READ ONLY.

You may edit production code only. You must not edit the criteria file or any acceptance test
file. This is verified after you finish by comparing hashes recorded before you started — a
mismatch stops the run and is reported, so editing them does not help you.

These files carry the user's own uncommitted work from before this run: <baseline dirty paths,
or "none">. Leave them alone if you can. If you must edit one, never revert what was already
there.

If a criterion cannot be met as written, do not soften it: implement what you can, then state
plainly which criterion you could not meet and why. "Not done, here is why" is a valid and
useful outcome. Silently redefining the target is not.

You run no git command that writes — no add, commit, push, stash, checkout, switch, restore,
reset, clean, rm or mv; to undo your own edit, edit the file back. You do not write to the
tracker. The orchestrator owns git and the tracker; a git write by you stops the run.

Write what you changed and why to <run_dir>/03-changes.md.
Reply: at most 40 lines — every file you touched (created, modified or deleted) with
`file:line`, decisions taken, anything you could not do.
```

Pass project guardrails into the prompt if `.claude/task-flow-rules.md` names any (banned APIs,
forbidden directories, style guards enforced by hooks). An implementer that trips a hook without
knowing it exists burns a round rediscovering it. In an unattended run, pass the caller's
instructions too, verbatim.

---

## Step 8 — Snapshot, then produce the diff

Order matters. The reviewer must judge exactly the tree a later commit will contain — and
nothing is committed here. The snapshot is a git tree built in a private index file in the
repository's git directory: it includes new files and deletions, applies `.gitattributes`
filters like any `git add`, and leaves `HEAD`, the branch and the user's own index untouched.

1. **Collect the whitelist — files only.** The union of every file reported so far by every
   implementer round and, in `full`, by the test-author, plus the acceptance test files. It only
   grows from round to round; a file a later round restored simply produces no diff. Never a
   directory (expand it into its files and check each against the Step 1 status), never a
   wildcard, never `git add -A` / `-u`, never "whatever is dirty". A path that exists neither on
   disk nor in `base_sha` (`git cat-file -e <base_sha>:<path>` fails) was created and removed
   within the run: leave it out of the snapshot's `git add` (here and in 12.3.1) but keep it in
   the whitelist — after a 12.3 commit it is a deletion the next commit must stage.
2. **Baseline check — git is as the agents found it.** `HEAD` equals `head_sha` if `RUN.md`
   records one (a 12.3 commit exists), otherwise `base_sha`. The current branch, the staged
   column of `status` (plus `staged_by_run:`), and `refs/stash` match the baseline (as re-taken
   after a Step 5 stash or a 12.3 commit). Every baseline path outside the whitelist and outside
   `test_dirt:` still has its recorded hash. Any difference means an agent committed, staged,
   stashed, switched, reverted, or edited a file it did not report — stop, outcome `blocked`,
   tell the user exactly what differs, undo nothing.
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

   `read-tree` replaces whatever the index file held, so nothing is deleted first: the guard
   refuses `rm` under `task-runs`, and permission checks refuse `rm` of a path computed by `$(…)`.

   Any error → outcome `blocked`, quote git's message, and never record a tree from a failed
   build. Never force-add an ignored path (`-f`). Once the tree is built, record the whitelist
   and `snapshot_tree` = its sha in `RUN.md` right away, before the checks below can stop the run.
5. **Nothing left out.** Compare `status` with the baseline: every path that became dirty since
   then must be in the whitelist. A dirty path outside it means an agent changed something it
   did not report (a generated `.meta`, a touched config) — stop, outcome `blocked`, list the
   paths. Do not widen or narrow the whitelist silently. Pre-existing dirt and `test_dirt:`
   (Step 9) are expected and fine — so is a path under `generated_paths` of `pipeline.config.json`
   that no agent reported: the engine or the test runner rewrites those on every run; record it
   as `test_dirt:`.
6. **Verify the frozen set:** recompute `sha256` for the criteria file and every acceptance test.
   Any mismatch → stop the run, outcome `tampered`, and say exactly which file changed.
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

1. `test_report_parts` / `commands.test_report` in `pipeline.config.json` at the repo root —
   these print a machine-readable report and are the preferred source of truth.
2. A command named in `.claude/task-flow-rules.md`.
3. The project's obvious test command from `package.json`, a solution file, or `CLAUDE.md`.

Run every part. For each acceptance criterion, resolve one of:

- **proven by test** — a test tagged with that criterion ran and passed.
- **checked by eye** — no automatable test; a human or an agent inspected it. Say who.
- **NOT PROVEN** — the criterion is `auto` but its test did not run: the channel was
  unavailable, the editor was open, the device was missing, the part errored. A part that
  reports itself unavailable does **not** turn into a pass. This is the whole point of the
  three-state model: an unproven criterion is reported as unproven, to the user and in any
  comment the user orders, and it does not become silence.

Record the per-criterion outcome table in `RUN.md`.

**Tests already failing on `base_sha`.** If the caller's instructions name a file listing them
(unattended runs), a failure listed there is pre-existing: report it apart, under "failing
before the run", and never count it against the run or the reviewer's verdict. An acceptance
test is never on that list — it did not exist on `base_sha`.

**Test dirt.** Every test run — this one, the red phase in Step 6, and whatever the reviewer runs
in Step 10 — can write files. Take `status` right before and after each run and re-hash the
baseline paths outside the whitelist. A path that became dirty, or a baseline path whose hash
changed, and is not in the whitelist (in Step 6: not among the test-author's reported files) was
written by the tests: record it as `test_dirt:` in `RUN.md`. Steps 8.2 and 8.5 do not count it
against the agents, and it never enters a snapshot or a commit. If a test run overwrote a file
that held the user's uncommitted change, tell them — the pre-run content is the recorded blob.

---

## Step 10 — Review

Spawn a **fresh** agent — one that has not seen the implementer's reasoning. That freshness is
the entire mechanism; do not also blindfold it.

```
You are reviewing a change you did not write, against criteria you did not choose.

Acceptance criteria: <run_dir>/02-criteria.approved.md
Diff from the branch point: <run_dir>/03-diff.patch
Test results: <the per-criterion table from Step 9>
[if overlap] These files already carried the user's own uncommitted changes before the run,
each with its pre-run blob: <path> <baseline blob sha>, one per line. `git diff <blob> <path>`
shows only what the run changed in them; a removed pre-run line that no criterion requires is
BLOCKING.
You have Read, Grep and Bash over the working tree — open any file you need in full. The diff
is a starting point, not your only evidence. Do NOT read 03-changes.md; the implementer's own
account of the work is exactly what you are here to check independently.
Bash is for reading and running tests. You change nothing but 04-review-N.md: no other edits,
no git command that writes, no tracker calls.

For EVERY acceptance test, answer this explicitly: name a concrete change to production code
that would make this test fail. If you cannot name one, the test does not test anything —
report it as a blocking finding. A test that stays green against a hollowed-out implementation
is the specific failure this review exists to catch.

Then judge each criterion: met / not met / not proven, with `file:line` evidence.

Severity discipline — what goes back for another round versus what goes in the report:
  BLOCKING (another round): an unmet criterion, or a defect you can point at with `file:line`
    and describe as a concrete failure.
  REPORT ONLY (no round): style, naming, structure you would have done differently, ideas for
    later. Real, worth writing down, not worth a round trip.

Write the full verdict to <run_dir>/04-review-N.md.
Reply: at most 40 lines — blocking findings first, each with `file:line`.
```

When the verdict is in, record `reviewed_tree` = the `snapshot_tree` it judged. Each round
overwrites it; the last reviewed tree is what a commit must reproduce.

---

## Step 11 — The loop, capped at 2 rounds

If there are blocking findings, send them back to a **new** implementer agent (the criteria and
tests stay frozen; hashes are re-verified in Step 8 every round). Then repeat Steps 8–10.

**Hard cap: 2 rounds.** After the second review, stop regardless of state. Do not start a third.
The outcome becomes `stopped` and the report names precisely which criteria remain unmet and
what the reviewer said about each. An honest stop after two rounds is a result; an endless loop
is a bill. The cap limits the automatic loop: a round the user orders at the publish gate runs
Steps 8–10 once and does not count toward it.

If a round produces no blocking findings, proceed to Step 12 with outcome `accepted`.

---

## Step 12 — The publish gate

The engineering work is done. From here nothing happens without a command (`SKILL.md`,
"Commands"). Record each action in `RUN.md` as it completes, so an interruption is diagnosable.
Every "ask" below that leads to a commit, push, PR, merge or status change is an `AskUserQuestion`
whose proceed option carries the guard tag of that action (`SKILL.md`, "The guard") — the guard
lets nothing else through.

First re-run the Step 8.2 check and rebuild the snapshot as in 12.3.1 — the last reviewer ran
after the last check. A difference from `reviewed_tree` → outcome `blocked`, show it first, undo
nothing. (`probe`: the 8.2 check only, as in its short path.)

### 1. Write the report — locally, always

Write `<run_dir>/REPORT.md` whatever the outcome and whether or not anything will ever be posted.
It is the artifact; posting is one possible delivery. Write it in the language of the ticket.
Structure:

```
<outcome>: accepted | stopped after 2 rounds | blocked | tampered | probe

base <base_sha short> · reviewed tree <reviewed_tree short | none (stopped at 8.<n>)> · <N> round(s)
git: not committed | committed <head_sha short> on task/<id>-<slug> | pushed to origin/task/<id>-<slug>
<if any> Your changes are stashed as <stash sha short> · carried into this change: <overlap paths>

Acceptance criteria:
  AC1  proven by test      TagLoggerTests.AC1_...
  AC2  checked by eye      Client/.../TagLogger.cs:44
  AC3  NOT PROVEN          Unity editmode part unavailable — editor was open
  AC4  NOT MET             <one line from the reviewer>

Changed: <files, one line each>
Review findings not blocking: <short list, or "none">
Task status: unchanged | changed to <status> | cannot change: <reason>
Task comment: none | posted <id> | sent, not confirmed | handed to user
```

In an unattended run the `git:` line reads `not committed (unattended — the caller publishes)`,
`Task status:` and `Task comment:` read `unchanged (unattended)` and `none (unattended)`, a
`manual` criterion reads `NOT PROVEN — needs a human look`, and two blocks follow the header
lines, before the criteria: `Assumptions:` (every decision taken instead of a question — what,
the alternative, why; `none` if there were none) and, if the ticket asked for any, `Not done in
an unattended run:` (its publishing instructions).

For `probe`, leave out the reviewed-tree, `git:` and `Changed:` lines. The `git:`, `Task status:`
and `Task comment:` lines describe the state at the moment of writing; update them after every
action below. Criteria are quoted from the approved file, verbatim — re-verify its hash before
building the report from it. Never write a bare "done". The criterion table is the report.

### Unattended end — instead of 12.2–12.6

An unattended run never reaches the gate below: after `REPORT.md`, write two files for the
caller and end. Nothing of 12.2–12.6 runs.

1. `<run_dir>/commit-msg.txt` — for `accepted` and `stopped` only: a message in the repository's
   convention (`git log --oneline -10`), first line ending with ` (<task_id>)`, an optional short
   body; no trailers, the caller adds them.
2. `<run_dir>/RESULT.json`:

   ```json
   {
     "task_id": "<task_id>",
     "outcome": "accepted | stopped | blocked | tampered | probe",
     "mode": "fix | full | probe",
     "base_sha": "<base_sha>",
     "reviewed_tree": "<reviewed_tree, or null if no tree was reviewed>",
     "whitelist": ["<every whitelisted path>"],
     "rounds": 1,
     "not_proven": ["AC3"],
     "not_met": ["AC4"],
     "manual": ["AC5"],
     "notes": ["<run_dir>/02-criteria.approved.md", "<run_dir>/04-review-1.md"],
     "report": "<run_dir>/REPORT.md",
     "commit_msg": "<run_dir>/commit-msg.txt, or null",
     "blocked_reason": "<one line, or null>"
   }
   ```

   `notes` are the files 12.3.6 would carry with a commit. Paths are absolute.
3. Re-run the Step 8.2 check once more — the last agent had Bash — and end with one line: the
   absolute path of `RESULT.json`.

### 2. Stop and show what is ready

Final message to the user — short:

- If any criterion came out `NOT PROVEN`, say that first, before the successes. That is the line
  they need to see.
- The outcome and the criterion table.
- Overlap paths, if any, before the diff: these files also carry the user's own pre-run changes.
- `git diff --stat <base_sha> <reviewed_tree>` and the path to `03-diff.patch`, so the diff can be
  read before anything is committed, plus one line naming the note files a commit would add on
  top (12.3.6): `02-criteria.approved.md` and the `04-review-*.md` verdicts. If no tree was
  reviewed, show the stat of the last snapshot, labelled unreviewed.
- A stash from Step 5, if any, and that restoring it is theirs to order.
- If the run stopped, the one thing that would unblock it.
- `earlier_commands:` from a previous invocation, if any: "ordered earlier, not carried out".
- One line with what is ready, listing only what is actually possible for this outcome and
  channel, e.g.:

  > Ничего не закоммичено и не отправлено. Готово по команде: коммит в `task/<id>-<slug>` ·
  > push · комментарий в задачу (сначала покажу текст) · статус → «in review».

Unused commands in `commands:` (this invocation only) are handled in the fixed order:

1. Commit and push: if the outcome is `accepted` with no `NOT PROVEN` criterion and the command
   is in the user's latest typed message (the guard sees nothing older — re-ask an older one, the
   invocation included, with an `AskUserQuestion` whose options carry the guard tags), carry them
   out now (12.3, 12.4) and let the message show what was done instead of «Ничего не закоммичено».
   Otherwise name each one you did not carry out and why, mark it used up, and wait for the
   user's answer about them.
2. A comment: goes to "Task comments" for any outcome — but only once commit and push are settled
   (done, or answered by the user), so the draft states the final git state.
3. A status change: under the same condition as 1, after the comment was posted or declined, or
   right away if no comment was ordered.

Then end the turn and wait.

### 3. On "commit"

Not offered for `tampered`, or for a `blocked` raised in Step 8: the run stopped before any
review of that tree, so there is no `reviewed_tree` a commit could be verified against. Offer to
resolve the block or restore the frozen files and run a fresh Steps 8–10 round. If the user
insists on committing as is, say plainly that the tree is unreviewed and commit only after they
confirm with that in front of them. 12.3.1 then rebuilds the snapshot from the recorded whitelist
and that tree stands in for `reviewed_tree`; the `git:` line says `unreviewed`. A run that stopped
before 8.4 has no whitelist — nothing to commit.

1. **The tree still matches the review.** Rebuild the snapshot exactly as in Step 8.4 — same
   whitelist, fresh index file — and compare its sha with `reviewed_tree`. Different → the
   working tree changed after the review: show `git diff --stat <reviewed_tree> <new_tree>` and
   offer a review round. If the user insists on committing the changed tree, name the paths and
   commit only after they confirm; the `git:` line says `includes changes after review: <paths>`.
2. **Nothing moved.** `HEAD` equals `base_sha`, or `head_sha` when re-committing on the task
   branch. Otherwise stop and ask.
3. **The user's index stays theirs.** `git diff --cached --name-only` must list nothing outside
   the whitelist and `staged_by_run:`. If the user has staged unrelated work, stop and ask — `git commit` would sweep
   it in, and unstaging it is not yours to do.
4. **Overlap confirmed.** If `overlap:` is non-empty and the user has not confirmed it yet, list
   the paths and ask.
5. **Branch.** If you are not on the branch recorded in Step 5 and it does not exist,
   `git checkout -b <branch>`. If it already exists (`git rev-parse -q --verify refs/heads/<branch>`)
   and you are not on it, stop and ask for a new name — never `checkout -B`, never switch onto an
   existing branch yourself: it may hold commits the review never saw. Tell the user their
   checkout moved from `<base branch>` to the task branch.
6. **The basis of acceptance travels with the work.** Copy `02-criteria.approved.md` and the
   `04-review-*.md` verdicts into the path the project uses for such notes, or
   `.task-runs/<task_id>/`. A copy only in the run directory is seen by nobody. From here on
   these copied files are "the note files" — always named one by one, never as a directory,
   which may hold the user's own uncommitted work.
7. **Stage, then commit — two separate Bash calls.** First `git add -- <whitelist> <note files>`;
   a non-zero exit stops here. Leave out a whitelisted file that is neither on disk nor in the
   index (`git ls-files --error-unmatch -- <path>` fails): there is nothing to stage, and
   `git add` rejects the whole call over it. Then the commit, as a call whose command begins with `git commit`
   — no `cd`, no env prefix, no `&&` chain — so project hooks that match `git commit` see the
   staged index. Follow the repository's message conventions (`git log --oneline -10`).
   One commit for the task: a repeated commit command on the unpushed task branch amends it
   (`git commit --amend`) — that command is the order to amend. Folding several commits into one
   (`git reset --soft <base_sha>` + commit) is offered as one option «Схлопнуть в один коммит
   [reset] [commit]». If the task commit was already
   pushed, do not amend: ask "new commit on top" / "leave it". If a guard or hook rejects the
   commit, stop, outcome `blocked`, its message goes into the report verbatim — never retry with
   fewer files to get past it. Tell the user the whitelist and note files are left staged and the
   checkout is on the task branch; record them in `RUN.md` as `staged_by_run:` so later checks
   (8.2, 8.5, 12.3.3) expect them. Unstaging or switching back is theirs to order. A `blocked`
   from here or from 12.3.8 keeps its `reviewed_tree`: once the cause is fixed, a commit command
   runs 12.3 as usual.
8. **Verify:** `git diff --quiet <expected> HEAD -- ':/' ':(top,exclude)<note file>' …` (one
   exclude per note file) exits 0, where `<expected>` is `reviewed_tree` — or the snapshot the user
   explicitly confirmed in the intro above or in 12.3.1. So the commit holds exactly that tree plus
   the notes. Also, `status` shows nothing from the whitelist left behind. Both pass → record
   `head_sha` in `RUN.md` and re-take the whole Step 1 baseline (branch, status, stash ref,
   per-path hashes) for later Step 8.2 checks. Either fails → do not record `head_sha`, do not push
   even on a command already given, outcome `blocked`, show `git diff --stat <expected> HEAD`, and
   do not amend or reset without a command.

### 4. On "push"

**Precondition:** `head_sha` is recorded (12.3.8 passed) and `git rev-parse HEAD` equals it.
Pushing something the reviewer never saw defeats every check above it. Nothing committed → ask
whether to commit; do not infer it.

`git push -u origin <task branch>`. That is the default and the only push a plain "push" means.
A push to the base branch, a merge, a force-push (task branch only, `--force-with-lease`) or
opening a PR happens only when the user names that exact action — then say in one line what it
will do, and do it. The guard knows them apart: `[pr]`, `[merge]`, `[force-push]` (which also
covers the base branch); a plain «запушь» or `[push]` covers none of them.

### 5. On "comment"

Follow "Task comments" in `SKILL.md`: draft, fact-check by a fresh agent, show the full text,
post only on approval, confirm it landed. Delivery goes over `tracker_channel` from `RUN.md`:

| channel | how |
|---|---|
| MCP | the tracker's create-comment tool (update-comment for an ordered edit), text = the content of `COMMENT-<n>.md` unchanged |
| CLI | `gh issue comment <n> --repo <owner/repo> --body-file <run_dir>/COMMENT-<n>.md` |
| browser | see `trackers.md` — only the approved text, and confirm it appeared |
| manual | print the approved text in full for the user to paste |

### 6. On a status change

Two preconditions, both required: the status vocabulary was retrieved in Step 2, **and**
`tracker_channel` is `mcp` or `cli`. Never change status through the browser — a status is a
field, and fields go through an API or stay untouched. If either precondition fails, say so; the
user changes it themselves.

Map the user's words onto the vocabulary ("в ревью" → the tracker's review-ish status). No
obvious match, or more than one → ask, with the real status names as options. Guessing a status
name is how you write to the wrong task state. `status_map:` in `.claude/task-flow-rules.md` may
name the target; it may not override "guess nothing".

What to offer in the ready-line of 12.2:

| outcome | offer |
|---|---|
| `accepted` | the review-ish status (or the one from `status_map:`) |
| `stopped` / `blocked` / `tampered` / `probe` | nothing — the report says the status stays as it is |

The user may still order a status change for any outcome; the table only decides what the skill
suggests.
