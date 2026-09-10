# ticket — pipeline (Steps 6–12)

Loaded after the user approves mode and criteria in `SKILL.md` Step 5. Execute in order.
Update `RUN.md` (`step:` field) as you move — a run interrupted here must be resumable.

Throughout: `<run_dir>` = `~/.claude/task-runs/<repo-name>/<task_id>/`, and criteria always
means `02-criteria.approved.md`, never the draft.

---

## probe mode — short path

`probe` answers a question; it does not change code. Skip Steps 6–8 and 11 entirely.

1. The context agent from Step 3 has already reported. If the ticket asks whether a defect
   still reproduces, spawn **one** verification agent: give it the ticket, the criteria, and
   instruct it to look for evidence *both* ways — the code path that would produce the defect
   and the code that would prevent it. Reply cap: 40 lines. Full findings to
   `<run_dir>/04-review-1.md`.
2. Run the test channel (Step 9) if one exists and a relevant test can decide it.
3. Report (Step 12) with outcome `probe`. Never push, never change status, never commit —
   there is nothing to commit. If the answer is "yes, it still reproduces", the report ends
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

Reply: at most 40 lines — one line per test with `file:line`, its criterion tag, and whether
you confirmed it currently fails.
```

Then **verify the red phase yourself** by running the test channel (Step 9). Any acceptance
test that is already green is either a satisfied criterion (record it as such in `RUN.md`) or a
tautology (send it back once; if it survives a second time, mark the criterion `NOT PROVEN` and
carry on — do not spend the run here).

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
mismatch stops the run and is reported to the tracker, so editing them does not help you.

If a criterion cannot be met as written, do not soften it: implement what you can, then state
plainly which criterion you could not meet and why. "Not done, here is why" is a valid and
useful outcome. Silently redefining the target is not.

Write what you changed and why to <run_dir>/03-changes.md.
Reply: at most 40 lines — files touched with `file:line`, decisions taken, anything you
could not do.
```

Pass project guardrails into the prompt if `.claude/task-flow-rules.md` names any (banned APIs,
forbidden directories, style guards enforced by hooks). An implementer that trips a hook without
knowing it exists burns a round rediscovering it.

---

## Step 8 — Commit, then produce the diff

Order matters. The reviewer must judge the same tree that will be pushed.

1. **Stage an explicit whitelist.** Collect the paths the implementer reported plus, in `full`,
   the acceptance test files. `git add <path> <path> …`. Never `git add -A`, never `git add -u`,
   never `git commit -am`.
2. **Commit.** Follow the repository's existing message conventions (read `git log --oneline -10`
   if unsure). If a commit hook rejects the commit, **stop the run** — do not retry with fewer
   files to get past the guard. Record the guard's message; it goes into the report verbatim and
   the outcome is `blocked`.
3. **Verify nothing was left behind:** `git status --porcelain`. If it is non-empty and contains
   anything the implementer touched, something did not make it into the commit — stop with
   outcome `blocked`. Pre-existing unrelated dirt (recorded in Step 1) is expected and fine;
   compare against that baseline rather than requiring an empty result.
4. **Verify the frozen set:** recompute `sha256` for the criteria file and every acceptance test.
   Any mismatch → stop the run, outcome `tampered`, and say exactly which file changed. Do not
   push, do not touch the task status.
5. **Produce the diff:** `git diff <base_sha>..HEAD > <run_dir>/03-diff.patch`. From the branch
   point, so it contains the acceptance tests as well as the implementation — the reviewer needs
   both to spot a test written to fit the code.
6. Record `head_sha` in `RUN.md`.

Also commit `02-criteria.approved.md` and the review verdicts (once they exist) into the branch
under a path the project uses for such notes, or `.task-runs/<task_id>/` if it has none. What the
work was judged against must travel with the work; a copy only in the run directory is seen by
nobody.

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
  three-state model: an unproven criterion is reported as unproven, to the user and to the
  tracker, and it does not become silence.

Record the per-criterion outcome table in `RUN.md`.

---

## Step 10 — Review

Spawn a **fresh** agent — one that has not seen the implementer's reasoning. That freshness is
the entire mechanism; do not also blindfold it.

```
You are reviewing a change you did not write, against criteria you did not choose.

Acceptance criteria: <run_dir>/02-criteria.approved.md
Diff from the branch point: <run_dir>/03-diff.patch
Test results: <the per-criterion table from Step 9>
You have Read, Grep and Bash over the working tree — open any file you need in full. The diff
is a starting point, not your only evidence. Do NOT read 03-changes.md; the implementer's own
account of the work is exactly what you are here to check independently.

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

---

## Step 11 — The loop, capped at 2 rounds

If there are blocking findings, send them back to a **new** implementer agent (the criteria and
tests stay frozen; hashes are re-verified in Step 8 every round). Then repeat Steps 8–10.

**Hard cap: 2 rounds.** After the second review, stop regardless of state. Do not start a third.
The outcome becomes `stopped` and the report names precisely which criteria remain unmet and
what the reviewer said about each. An honest stop after two rounds is a result; an endless loop
is a bill.

If a round produces no blocking findings, proceed to Step 12 with outcome `accepted`.

---

## Step 12 — Publish

Fixed order, each step recorded in `RUN.md` as it completes, so an interruption is diagnosable.

**Precondition:** `git rev-parse HEAD` must equal the `head_sha` that was reviewed. If the tree
moved after the review, do not push — re-run Steps 8–10 or stop. Publishing something the
reviewer never saw defeats every check above it.

### 1. Push

`git push -u origin task/<task_id>-<slug>`. Never push to the base branch, never merge, never
open a PR unless project rules say to.

Outcomes `blocked` and `tampered` still push nothing. Outcome `stopped` **does** push — the
branch is useful and the report says what is unfinished.

### 2. Comment on the task

Use the channel recorded in `RUN.md` as `tracker_channel`:

| channel | how |
|---|---|
| MCP | the tracker's create-comment tool |
| CLI | `gh issue comment <n> --repo <owner/repo> --body-file <run_dir>/REPORT.md` |
| browser | only with explicit approval of the exact text — see `trackers.md`, and confirm it appeared |
| manual | write `<run_dir>/REPORT.md` and print it in full for the user to paste |

Always write `<run_dir>/REPORT.md` first, whatever the channel. It is the artifact; posting is
delivery. Write it in the language of the ticket. Structure:

```
<outcome>: accepted | stopped after 2 rounds | blocked | probe

branch task/<id>-<slug> · base <base_sha short> · head <head_sha short> · <N> round(s)

Acceptance criteria:
  AC1  proven by test      TagLoggerTests.AC1_...
  AC2  checked by eye      Client/.../TagLogger.cs:44
  AC3  NOT PROVEN          Unity editmode part unavailable — editor was open
  AC4  NOT MET             <one line from the reviewer>

Changed: <files, one line each>
Review findings not blocking: <short list, or "none">
<if applicable> Task status not changed: <reason>
```

Criteria are quoted from the approved file, verbatim. Re-verify its hash before writing this
comment — the report must be built from the text that was approved.

Never write a bare "done". The criterion table is the report.

### 3. Task status

Two preconditions, both required: the status vocabulary was retrieved in Step 2, **and**
`tracker_channel` is `mcp` or `cli`. Never change status through the browser or by asking the
user to do it — a status is a field, and fields go through an API or stay untouched.

| outcome | status |
|---|---|
| `accepted` | the tracker's review-ish status (e.g. "in review"); no obvious match in the vocabulary — **leave it** |
| `stopped` | leave unchanged |
| `blocked` | leave unchanged |
| `tampered` | leave unchanged |
| `probe` | leave unchanged |

`status_vocabulary: unavailable` → leave unchanged and say so in the report. Guessing a status
name is how you write to the wrong task state; the fallback is always to leave it and report.

Project rules may override the target status name — read `status_map:` in
`.claude/task-flow-rules.md` if present. They may not override "guess nothing".

---

## Final message to the user

Short. The outcome, the branch, the criterion table, and — if the run stopped — the one thing
that would unblock it. Everything else is already in `<run_dir>` and in the task comment.

If any criterion came out `NOT PROVEN`, say that first, before the successes. That is the line
they need to see.
