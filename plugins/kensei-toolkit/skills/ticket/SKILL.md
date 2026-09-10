---
name: ticket
description: Run a tracker task end-to-end — read the ticket, gather context with a subagent, agree acceptance criteria with the user, implement, run tests, review with a fresh agent, commit, push and report back to the tracker. Works with any tracker (ClickUp, Jira, Linear, GitHub Issues, YouTrack, Asana, Notion) via MCP, CLI or browser. Modes — probe (investigate only), fix (defect), full (feature with acceptance tests). Use when handed a task link or task id, or when asked to "do this ticket".
argument-hint: "<task-url|task-id> [probe|fix|full]"
---

# ticket — run one tracker task end-to-end

Replaces the hand-written orchestration prompt ("read the task, one agent gathers context,
another implements, a third reviews, you orchestrate"). Same flow, but the parts that can be
checked are checked instead of promised.

**Design rationale:** `docs/brainstorms/2026-09-10-ticket-skill.md` in the user's home docs.
Read it before changing anything here — several rules below look removable and are not.

## Non-negotiables

These exist because their absence was measured, not imagined. Do not "simplify" them away.

1. **The diff is produced by you, after the commit — never by the implementer.** A new file
   under an asset directory does not appear in `git diff`, and commit guards can reject a
   commit *after* a review has already passed. Reviewing an uncommitted tree means reviewing
   something other than what gets pushed.
2. **Acceptance criteria are approved by the human, then frozen by hash.** Agents add criteria
   the user never chose, and added criteria are indistinguishable from original ones at review
   time. Freeze after approval; re-verify before review and before reporting.
3. **The reviewer is a fresh agent but NOT a blindfolded one.** It gets Read/Grep over the
   working tree and the full diff from the branch point. Restricting a reviewer's input has
   already been tried in the user's other tooling and was reverted for cause.
4. **Never `git add -A` / `-u`.** Commit an explicit path whitelist. The user's tree routinely
   carries unrelated work in progress, and `git add` is pre-approved in settings — nothing will
   stop a wide add.
5. **A criterion nobody proved is `NOT PROVEN`, never green.** If the test channel is
   unavailable, say so per criterion. Silence reads as confirmation to whoever gets the report.
6. **The run directory lives outside the repository.** Do not rely on `.gitignore` covering it.

## Step 0 — Parse the argument, identify the tracker

`$ARGUMENTS` holds `<url|id> [mode]`.

A trailing `probe` / `fix` / `full` is a mode hint — it pre-selects the option in Step 5 but
does not skip the confirmation.

**From a URL, identify the tracker by host and extract the task reference:**

| host | tracker | task ref |
|---|---|---|
| `app.clickup.com/t/<team>/<id>` | ClickUp | last segment |
| `*.atlassian.net/browse/<KEY-123>` | Jira | the `KEY-123` key |
| `linear.app/<org>/issue/<KEY-123>/…` | Linear | the `KEY-123` key |
| `github.com/<owner>/<repo>/issues/<n>` | GitHub Issues | `owner/repo#n` |
| `*.youtrack.cloud/issue/<KEY-123>` | YouTrack | the issue key |
| `app.asana.com/…/<gid>` | Asana | the numeric gid |
| `notion.so/…-<hash>` | Notion | the page id |

Unknown host → still record host and URL; the browser path in Step 2 does not need to know the
product.

**Bare id, no URL** → resolve the tracker in this order: `tracker:` in
`.claude/task-flow-rules.md` → the only tracker with a connected MCP server → ask.

Nothing recognizable → ask for the task link, then stop and wait.

Record `tracker` and `task_ref` in `RUN.md`.

## Step 1 — Baseline the working tree

Run these and record the results — you will need them at commit time and they are the only
protection against committing someone else's work in progress:

```bash
git rev-parse --abbrev-ref HEAD     # current branch
git rev-parse HEAD                  # base_sha
git status --porcelain              # dirty?
git rev-parse --show-toplevel       # repo root -> repo name for the run dir
```

Create the run directory **outside the repo**:

```
~/.claude/task-runs/<repo-name>/<task_id>/
```

If it already exists with a `RUN.md`, this is a re-run — read it and offer resumption as one of
the options in Step 5 rather than silently starting over.

Write `RUN.md` with: task id, base branch, `base_sha`, the porcelain output, and step = `intake`.

If a project rules file exists at `.claude/task-flow-rules.md`, read it now. It may define test
commands, branch conventions, status names, and paths that must never be touched. Project rules
win over defaults in this skill; they never remove the six non-negotiables.

## Step 2 — Read the ticket yourself

Do this with your own tool calls, not a subagent — routing depends on the ticket content, and
spawning an agent for two reads buys nothing.

You need three things: **title + description**, **comments** (required — clarifications usually
live there, not in the description), and the **status vocabulary** for Step 12.

Pick the access channel by this cascade, first one that works wins. Record the chosen channel in
`RUN.md` as `tracker_channel` — Step 12 uses the same one to report back.

1. **MCP** — a connected server for this tracker. Search for it before concluding it is absent:
   `ToolSearch` with `"<tracker> task issue get"`. Tools may be deferred rather than missing.
2. **CLI** — for GitHub Issues, `gh` is better than any browser path: check `gh auth status`,
   then `gh issue view <n> --repo <owner/repo> --comments --json title,body,state,comments`.
   Other trackers: use a CLI only if `.claude/task-flow-rules.md` names one.
3. **Offer to install an MCP server** — do not install anything yourself. Show the exact command
   and what it will need (usually an API token), and ask. If they accept, they run it and
   restart the session; this run continues on the next channel meanwhile.
4. **Browser** — `claude-in-chrome`. Read-only by default; see `trackers.md`.
5. **Ask the user to paste the ticket text.** Not a failure — an honest last resort that still
   lets the run proceed.

Channels 3–5 and the browser mechanics are documented in `trackers.md` — read it only when
channels 1 and 2 both come up empty.

**Status vocabulary is optional, and its absence has a fixed consequence.** If you cannot
retrieve the list of valid statuses (no MCP, browser can't see them reliably), record
`status_vocabulary: unavailable` in `RUN.md`. Then the task status is not touched at the end and
the final report says so. Never guess a status name.

## Step 3 — Context agent

Spawn one Explore-style agent. Give it the ticket text, the comments, and this return contract
verbatim:

```
Write your full findings to <run_dir>/01-context.md.

In your REPLY return at most 40 lines: conclusions only, `file:line` instead of code quotes,
no retelling of what you read. The reply is consumed by an orchestrator with a finite context
window; the file is where detail belongs.

Cover: where this behaviour lives now, the entry points, the invariants a change must not
break, existing tests that touch this area, and anything in the ticket that the code
contradicts.
```

The 40-line cap applies to the agent's **reply**, never to what it is allowed to read.

## Step 4 — Draft acceptance criteria

Write `<run_dir>/02-criteria.md`. Number them `AC1…ACn`. Mark every line with its origin:

```
AC1  [from ticket]  Killing a zonal NPC does not resurrect it before the Meta flush.
AC2  [from ticket]  ...
AC3  [added]        Existing despawn tests still pass.
```

`[from ticket]` means the requirement is stated in the ticket or its comments. Anything you
inferred, generalized, or thought was obviously implied is `[added]`. When unsure, mark
`[added]` — the point of the mark is to let the user see what they did not ask for.

For each criterion also record how it would be proven: `auto` (a test can decide it), `manual`
(a human looks), or `none`. Be honest — `auto` on something no test can decide produces a false
green later.

## Step 5 — The single confirmation (BLOCKING)

This is the **only** interactive stop. Everything after it runs to completion without questions.

Print the criteria in full first, so the user reads them as text and not as option labels. Then
call `AskUserQuestion` with all applicable questions **in one call** (it accepts up to four, so
they appear on one screen):

1. **Mode** — `probe` / `fix` / `full`, with your recommendation first and a one-line reason
   drawn from the ticket. `probe` = the ticket asks a question ("does this still reproduce?");
   `fix` = a defect with an obvious shape; `full` = new behaviour with machine-checkable criteria.
2. **Criteria** — "approve as written" / "drop the `[added]` ones" / "let me edit first".
3. **Dirty tree** (only if Step 1 found one) — "stash it" / "leave it, commit only my paths" /
   "cancel".
4. **Resume** (only if this is a re-run) — "continue from step N" / "start over".

After approval:

- Copy the approved text to `<run_dir>/02-criteria.approved.md`.
- Record its `sha256` in `RUN.md`. This copy is what every later step reads.
- Create the branch: `git checkout -b task/<task_id>-<slug>` from the branch recorded in Step 1,
  unless project rules say otherwise. Record the branch in `RUN.md`.

If the user picked "let me edit first", stop and wait. That is not a violation of "no more
questions" — they asked for the wheel.

## Step 6 — Load the pipeline

Read `flow.md` from this skill's directory and follow it. It carries the rest: test-author and
the red phase, implementer isolation, the commit-then-diff sequence, running the test channel,
the review loop, and publishing. `probe` mode has its own short path documented there.
