# ticket — Step 12, the publish gate, and task comments

Read when Step 11 (or the probe short path) is done, and earlier whenever the user orders a
comment or a status change mid-run.

Placeholders (`<run_dir>`, `<root>`) are as in `flow.md`. Commands and the guard tags are defined
once, in `SKILL.md` — "Commands" and "The guard". Every question below that leads to a commit,
push, PR, merge (of a PR or local), rebase or status change is an `AskUserQuestion` whose
proceeding option ends with the tag of that action; the guard lets nothing else through.

## Step 12 — The publish gate

The engineering work is done. From here each action waits for its command (rule 7). Record each
action in `RUN.md` as it completes, so an interruption is diagnosable.

First re-run the Step 8.2 check and rebuild the snapshot as in 12.3.1 — the last reviewer ran
after the last check. A difference from `reviewed_tree` → outcome `blocked`, show it first, undo
nothing. (`probe`: the 8.2 check only.)

### 1. Write the report — locally, always

Write `<run_dir>/REPORT.md` whatever the outcome and whether or not anything will ever be posted.
It is the artifact; posting is one possible delivery. Write it in the language of the ticket.
Structure:

```
<outcome>: accepted | stopped after 2 rounds | blocked | tampered | probe

base <base_branch> @ <base_sha short> · reviewed tree <reviewed_tree short | none (stopped at 8.<n>)> · <N> round(s)
git: not committed | committed <head_sha short> on task/<id>-<slug> | pushed to origin/<branch>
<if any> Your changes are stashed as <stash sha short> · carried into this change: <overlap paths> · worktree: <path>

Acceptance criteria:
  AC1  proven by test      TagLoggerTests.AC1_...
  AC2  checked by eye      evidence/AC2-cargo-panel.png
  AC3  NOT PROVEN          Unity editmode part unavailable — editor was open
  AC4  NOT MET             <one line from the reviewer>

Changed: <files, one line each>
Review findings not blocking: <short list, or "none">
Evidence: <criteria, review verdicts, captures — absolute paths in the run dir> · notes <not committed | committed to <notes_path>/<task_id>/ | not committed: <notes_path> is ignored>
Diff tour: <path to the page | not built: <reason>>
Task status: unchanged | changed to <status> | cannot change: <reason>
Task comment: none | posted <id> | sent, not confirmed | handed to user
```

For `probe`, leave out the reviewed-tree, `git:`, `Changed:` and `Diff tour:` lines. The `git:`,
`Evidence:` (its notes part), `Task status:` and `Task comment:` lines describe the state at the
moment of writing; update them after every action below. Criteria are quoted from the approved
file, verbatim — re-verify its hash before building the report from it. Never write a bare
"done": the criterion table is the report.

### 2. Show what is ready, then stop

**Diff tour.** When a tree was reviewed (or, labelled unreviewed, the last snapshot), build an
annotated diff page of exactly that tree: invoke the `kensei-toolkit:diff-tour` skill with the
argument `<base_sha>..<reviewed_tree>`. Write its notes from the approved criteria (which
criterion a change serves — `source: "session"`, since the user approved them in this
conversation), the review verdicts (non-blocking findings as notes with a `kind`), and
`03-changes.md` (`source: "inferred"` — it is the implementer's own account). Its checks panel
carries the criterion table, every `NOT PROVEN` as a warning, and "not committed" as a warning.
Put the page path into `REPORT.md`. If the skill cannot be invoked, say so in one line and point
to `03-diff.patch`.

Final message to the user — short, in their language:

- If any criterion came out `NOT PROVEN`, say that first, before the successes. That is the line
  they need to see.
- The outcome and the criterion table, with evidence paths for `checked by eye`.
- Overlap paths, if any, before the diff: these files also carry the user's own pre-run changes.
- `base: <base_branch> @ <base_sha short>`, `git diff --stat <base_sha> <reviewed_tree>`, the
  diff tour path and `03-diff.patch`. If no tree was reviewed, the stat of the last snapshot,
  labelled unreviewed.
- One line naming the evidence files in the run directory (approved criteria, review verdicts,
  captures). They stay there; a commit adds note files only when project rules set
  `notes_path:` (12.3.6).
- A stash or worktree from Step 5, if any, and that restoring or removing it is theirs to order.
- If the run stopped, the one thing that would unblock it.
- `earlier_commands:` from a previous invocation, if any: "ordered earlier, not carried out".
- One line with what is ready, listing only what is possible for this outcome and channel —
  push to the default branch only when the user asked for it or project rules say work lands
  there:

  > Ничего не закоммичено и не отправлено. Готово по команде: коммит в `task/<id>-<slug>` ·
  > push · PR · комментарий в задачу (сначала покажу текст) · статус → «in review».

Unused commands in `commands:` (this invocation only) are handled in the fixed order, under the
conditions in `SKILL.md`, "Commands":

1. Commit, a local merge, push and PR («залей в мейн» — see `SKILL.md`, "Commands"): if they may run for this outcome and the guard can see
   them, carry them out now, in that order (12.3, 12.4) without asking again — unless a check there
   stops — and let the message show what was done instead of «Ничего не закоммичено». Otherwise name
   each one you did not carry out and why, mark it used up, and wait.
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
   branch. Otherwise stop and ask; if the base moved under the run, offer "When the base moved"
   (12.4).
3. **The user's index stays theirs.** `git diff --cached --name-only` must list nothing outside
   the whitelist and `staged_by_run:`. If the user has staged unrelated work, stop and ask —
   `git commit` would sweep it in, and unstaging it is not yours to do.
4. **Overlap confirmed.** If `overlap:` is non-empty and the user has not confirmed it yet, list
   the paths and ask.
5. **Branch.** If you are not on the branch recorded in Step 5 and it does not exist,
   `git checkout -b <branch>`. If it already exists (`git rev-parse -q --verify refs/heads/<branch>`)
   and you are not on it, stop and ask for a new name — never `checkout -B`, never switch onto an
   existing branch yourself: it may hold commits the review never saw. Outside a worktree, tell
   the user their checkout moved from `<base_branch>` to the task branch.
6. **Notes stay in the run directory by default.** The approved criteria and the review verdicts
   are evidence for the user, named at the gate; they do not go into the repository. Only when
   `.claude/task-flow-rules.md` sets `notes_path: <dir>`, copy `02-criteria.approved.md` and the
   `04-review-*.md` verdicts to `<notes_path>/<task_id>/` — these copies are "the note files",
   always named one by one, never as a directory. If `git check-ignore -q` matches a note file's
   path, copy nothing and stage nothing for notes; the report's `Evidence:` line says
   `notes not committed: <notes_path> is ignored`. (Why notes left the repository: CHANGELOG,
   2.0.0, "Run notes stay out of the repository".)
7. **Stage, then commit — two separate Bash calls.** First `git add -- <whitelist> [<note
   files>]`; a non-zero exit stops here. Leave out a whitelisted file that is neither on disk nor
   in the index (`git ls-files --error-unmatch -- <path>` fails): there is nothing to stage, and
   `git add` rejects the whole call over it. Then the commit, as a call whose command begins with
   `git commit` — no `cd`, no env prefix, no `&&` chain — so project hooks that match `git commit`
   see the staged index. Follow the repository's message conventions (`git log --oneline -10`).
   One commit for the task: a repeated commit command on the unpushed task branch amends it
   (`git commit --amend`) — that command is the order to amend. Folding several commits into one
   (`git reset --soft <base_sha>` + commit) is offered as one option «Схлопнуть в один коммит
   [reset] [commit]». If the task commit was already pushed, do not amend: ask "new commit on
   top" / "leave it". If a guard or hook rejects the commit, stop, outcome `blocked`, its message
   goes into the report verbatim — never retry with fewer files to get past it. Tell the user the
   staged files are left staged and the checkout is on the task branch; record them in `RUN.md`
   as `staged_by_run:` so later checks (8.2, 8.5, 12.3.3) expect them. Unstaging or switching
   back is theirs to order. A `blocked` from here or from 12.3.8 keeps its `reviewed_tree`: once
   the cause is fixed, a commit command runs 12.3 as usual.
8. **Verify:** `git diff --quiet <expected> HEAD` exits 0 — with note files,
   `git diff --quiet <expected> HEAD -- ':/' ':(top,exclude)<note file>' …` (one exclude per note
   file) — where `<expected>` is `reviewed_tree`, or the snapshot the user explicitly confirmed
   above or in 12.3.1. So the commit holds exactly that tree (plus the notes, if any). Also,
   `status` shows nothing from the whitelist left behind. Both pass → record `head_sha` in
   `RUN.md` and re-take the whole Step 1 baseline (branch, status, stash ref, per-path hashes)
   for later Step 8.2 checks. Either fails → do not record `head_sha`, do not push even on a
   command already given, outcome `blocked`, show `git diff --stat <expected> HEAD`, and do not
   amend or reset without a command.

### 4. On "push" and its relatives

**Precondition for every push:** `head_sha` is recorded (12.3.8 passed) and `git rev-parse HEAD`
equals it — or, after "Merge into the base branch", equals the recorded merge commit. Pushing
something the reviewer never saw defeats every check above it. Nothing committed → ask whether
to commit; do not infer it.

- **Push** (the only thing a plain "push" means): `git push -u origin <task branch>`.
- **Open a PR**, on its own command, once the task branch is on origin (no push yet → ask
  whether to push). A command that names a branch uses the target branch below. Otherwise the PR
  goes against `<base_branch>` when it differs from the default branch
  — the work is stacked on that branch, and the body says so in its first line («Stacked on
  `<base_branch>`», with that branch's PR number if `gh pr list --head <base_branch>` finds one)
  — otherwise against the default branch:
  `gh pr create --base <base_branch|default_branch> --head <task branch>`. Before creating it,
  **name everything the PR carries towards the default branch:**
  `git log --oneline origin/<default>..<task branch>`, shown to the user in the same message as
  the body. Title from the
  commit, body from `<run_dir>/PR-BODY.md`. A PR body is as public as a task comment, so it goes
  through the same check: draft it from `REPORT.md` (it says nothing the report does not), then
  run steps 2–4 of "Task comments" on it with these options — "create as is [pr]" / "I will edit
  the file — wait" / "don't create". Create it with `--body-file` pointing at that file, exactly
  as approved.
- **Merge the PR**, on its own command («смержи PR»): `gh pr merge` of this task's PR, in the
  repository's usual merge style.
- **Force-push**, on its own command: the task branch only, `--force-with-lease`.
- **Merge into the base branch** («мердж в мейн») and **push to the base branch** («запушь в
  main», «залей в мейн») — below.

Before each, say in one line what it will do.

**The target branch** of a local merge, a push to the base branch, or a PR whose command names a
branch («открой PR в мейн»). «Мейн» / "main" in a command resolves to the default branch. When
that is `<base_branch>`, it is the target. When they differ (the run was based on another task's
branch), ask once which branch to merge into, push to or open the PR against —
`<default_branch>` or `<base_branch>` — with each option ending in the action's tag. Only a
branch the user named by its own name, other than «мейн» / "main", is the target without asking.
Record it in `RUN.md` as `target:`; the steps below use it.

#### The clean-tree precondition

Switching branches, merging and rebasing move the checkout, and git refuses them over modified
tracked files (`cannot rebase: You have unstaged changes`). In a worktree from Step 5 the tree is
clean. In the user's checkout it often is not — their unrelated files are why non-negotiable 4
exists. So before any of the three, `git status --porcelain --untracked-files=no` must list
nothing. Otherwise stop, name the files, and offer as separate options: "do it in a separate
worktree" (a worktree at the task commit, as in Step 5, which leaves the user's files where they
are) and "stash my changes first" (as in Step 5; restoring them stays theirs to order). Never
`--autostash`, never stash without that answer.

#### Merge into the base branch

On «мердж в мейн» (or a bare «смерджи» the user resolved to it), with the task commit recorded
(12.3.8) and the clean-tree precondition met. An option that asks for it ends with
`[merge-local]`; `[merge]` is a PR merge only.

1. `git fetch origin <target>`. If the local `<target>` lacks commits of `origin/<target>`
   (`git log --oneline <target>..origin/<target>` lists any), name them and ask before merging:
   a merge onto a stale branch would be rejected at the push, and bringing the local branch up to
   date is a history write that needs its own command (`[reset]`, «подтяни»).
2. `git switch <target>` — part of the merge command. If the target is checked out in another
   worktree (`git switch` says so), stop and tell the user where; doing it there is theirs to
   order.
3. **Name everything the merge brings in:** `git log --oneline <target>..<task branch>`. If it
   lists anything besides the task commit — the run was based on another task's branch, whose
   unreviewed commits would land with it — name those commits and ask. If `<target>` gained
   commits since the run started (`git log --oneline <base_sha>..<target>`), name them too — the
   tests in step 5 will run with them.
4. `git merge --no-ff <task branch>` — the repository's usual merge style if `git log` shows
   another. A conflict → stop, list the files, ask; aborting or resolving is theirs to order.
5. **Re-run the test channel** (`flow.md`, Step 9) on the merge result. A criterion that no
   longer holds becomes `NOT MET` or `NOT PROVEN`, and nothing is pushed on an earlier command.
6. Record `merged: <task branch> -> <target> @ <merge sha>` and the test result in `RUN.md`; the
   report's `git:` line says `merged into <target> <sha short>, not pushed`.

Nothing is pushed — that is the next command.

#### Push to the base branch

On its own command, as an option tagged `[force-push]` — the guard's tag for any push to a base
branch. `<target>` is as above:

1. `git fetch origin <target>`. If `origin/<target>` is not an ancestor of `HEAD`
   (`git merge-base --is-ancestor`), the base moved: follow "When the base moved" first.
2. **Name everything the push publishes:** `git log --oneline origin/<target>..HEAD`. If it lists
   anything besides the task commit and its merge commit — for example, the run was based on
   another task's branch, whose unreviewed commits would reach `<target>` with this push — name
   those commits and ask.
3. `git push origin HEAD:<target>` — never forced.

#### When the base moved

The base branch gained commits after `base_sha` (a push is rejected as non-fast-forward,
`origin/<base_branch>` is ahead, or the user asks to bring the work up to date). Offer, as one
tagged option, «Перенести на <new base> и перепроверить [commit]» — the guard counts a rebase as a
history write. On that command:

1. The work must be committed (12.3) — the rebase moves the task commit, nothing else — and the
   clean-tree precondition above must hold.
2. `git fetch origin <base_branch>`, then on the task branch
   `git rebase --onto <new_base> <base_sha>`, where `<new_base>` is `origin/<base_branch>`. A
   conflict → stop, list the conflicting files and ask; aborting (`git rebase --abort`) or
   resolving is theirs to order, and a resolved conflict makes a review round (Steps 8–10)
   mandatory before any push.
3. **Compare the change set with what was reviewed:**
   `git diff -U0 <base_sha> <reviewed_tree> | git patch-id --stable` against
   `git diff -U0 <new_base> HEAD -- ':/' <excludes> | git patch-id --stable`, where `<excludes>`
   are the note files' `':(top,exclude)<note file>'` from 12.3.8, if any — the reviewed tree never
   held them. `-U0` ignores context lines that moved upstream. Equal → the same change sits on
   the new base. Different → show `git diff --stat`, and offer a review round against the new
   base.
4. **Re-run the test channel** (`flow.md`, Step 9) on the rebased tree, always — the code around
   the change is new. A criterion that no longer holds becomes `NOT MET` or `NOT PROVEN`, and
   nothing is pushed on an earlier command.
5. Record in `RUN.md`: `rebased: <base_sha> -> <new_base>`, `change set: same | differs`, the test
   result, and the new `head_sha`; then `base_sha` = `<new_base>` and, when the change set is the
   same, `reviewed_tree` = the rebased tree without the note files (rebuild the snapshot as in
   12.3.1). Re-take the Step 1 baseline, keeping `base_branch`. The report's `git:` line says
   `rebased onto <new_base short>`.

### 5. On "comment"

Follow "Task comments" below: draft, fact-check by a fresh agent, show the full text, post only on
approval, confirm it landed. Delivery goes over `tracker_channel` from `RUN.md`:

| channel | how |
|---|---|
| MCP | the tracker's create-comment tool (update-comment for an ordered edit), text = the content of `COMMENT-<n>.md` unchanged |
| CLI | `gh issue comment <n> --repo <owner/repo> --body-file <run_dir>/COMMENT-<n>.md` |
| browser | see `trackers.md` — only the approved text, and confirm it appeared |
| manual | print the approved text in full for the user to paste |

### 6. On a status change

Two preconditions, both required: the status vocabulary was retrieved in Step 2, **and**
`tracker_channel` is `mcp` or `cli`. A status is a field, and fields go through an API or stay
untouched — never through the browser. If either precondition fails, say so; the user changes it
themselves. Change the status field only: one update call whose only field is the status.

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

### 7. Changes after the gate

The user often answers the gate with a change instead of a command — «сделай побольше», «почини
прозрачность, потом закоммить». Such a change goes through the pipeline, not through your own
edits: an edit of yours is in no agent's report, so Step 8.5 flags it, and no fresh eye reviews
it.

1. **A new requirement becomes an addendum.** If the change asks for something the approved
   criteria do not cover, append it to `02-criteria.approved.md` under
   `## Addendum <n> — ordered at the gate`, as `AC<next>  [from user]  <the user's words, made
   testable>  <how proven>`. Existing criteria stay as they are. In `RUN.md`, replace
   `criteria_sha256:` with the full new hash and add a line `criteria_addendum: <n>, <old hash
   short> -> <new hash short>, "<the user's words>"` — Step 8.6 then checks against the new hash. Show the added lines in one short
   message and go on; ask only when the user's words leave the requirement unclear. A change that
   only fixes what an existing criterion already asks needs no addendum. In `full`, a new `auto`
   criterion first gets its test from a fresh test-author (flow.md, Step 6, red phase included),
   and that test's `sha256` goes into the same `RUN.md` list as the Step 6 tests.
2. **A fresh implementer makes the change** — the Step 7 prompt, plus the user's words verbatim
   and, after a commit, the note that the task commit exists. Its reported files join the
   whitelist (flow.md, Step 8.1).
3. **Steps 8–10 run once** (flow.md); this round does not count toward the cap of Step 11.
   Blocking findings after it → show them and ask; the round does not repeat by itself.
4. Rewrite `REPORT.md` and show the gate again (12.2). A command given together with the change
   («…, потом закоммить») applies to the result of this round, under the conditions in `SKILL.md`,
   "Commands"; after a commit, a new commit command on the unpushed task branch amends it. After
   a push or a local merge, the change becomes a new commit on the task branch: before the
   implementer starts, switch back to the task branch (part of the change command, under the
   clean-tree precondition) and re-take the Step 1 baseline there.

---

## Task comments — always reviewed before posting

Applies to every comment text this run would put on the tracker — a new comment or new text for
one already posted: the final report, a `probe` answer, an ad-hoc "write in the task what needs
to be done" at any point of the run.

1. **Draft** it to `<run_dir>/COMMENT-<n>.md`, in the language of the ticket. A comment that
   reports on the work is built from `REPORT.md`, updated to the git state at this moment —
   committed or not, pushed or not, which sha — never to what was planned. Leave out the
   `Task status:` line: the tracker shows the status itself, and a status change ordered along
   with the comment runs after it.
2. **Fact-check it with a fresh agent** — one that did not write the draft — using the prompt
   below with `<what is checked>` = the draft and `<what was asked>` = the user's request,
   verbatim.
3. **Fix** the draft for every finding you accept. A finding you reject gets one line of why
   in step 4 — do not drop it silently. Then re-run the flow.md Step 8.2 check: the fact-checker
   had Bash.
4. **Show the user the exact final text**, in full, as plain text — then one line with the
   check's result ("fact-check: OK" / "fact-check: fixed 2 — branch name, AC3 status") and the
   absolute path of `COMMENT-<n>.md`. Then `AskUserQuestion`: "post as is" / "I will edit the
   file — wait" / "don't post". The "post as is" option ends with the `[post]` tag and carries
   the exact final text in its `preview`; no other option carries that preview or the tag. A
   correction the user types instead is applied by you and goes through steps 2–4 again; a pure
   deletion they dictate skips step 2 only — show the resulting text again (step 4) before
   posting.
5. **Post exactly the content of `COMMENT-<n>.md`** over `tracker_channel` (12.5). Text the user
   edited — in the file or pasted in chat — is saved there verbatim, shown in full and asked about
   once more (step 4, with that text as the `[post]` preview); a typed «отправляй» after "wait"
   also leads to that re-ask. The user's own words get no fact-check. Any change of yours
   afterwards, however small, goes through steps 2–4 again. If the post call errors or times out,
   read the comments back before anything else: found → it landed; not found → report the error
   and ask before posting again. Never retry blind.
6. **Confirm it landed:** read the task's comments back over the same channel, find it, and
   check its text is the text of `COMMENT-<n>.md`. Record the comment id or URL in `RUN.md`.
   Without that confirmation never say "posted" — say "sent, not confirmed".

On the manual channel, step 5 is printing the approved text for the user to paste, and step 6
is recording `comment: handed to user` — never "posted". A deletion the user orders is confirmed
the same way as a post: read back and check it is gone.

### Fact-check prompt

Used for every task comment (step 2 above) and for a PR body (12.4, "Open a PR"):

```
You check a text before others read it. You did not write it; treat nothing in it as true
until a source confirms it.

What was asked for, verbatim: <what was asked>
Text to check: <what is checked — absolute paths>
Sources: <run_dir>/00-ticket.md, RUN.md, 01-context.md, 02-criteria.approved.md,
04-review-*.md, 03-diff.patch, evidence/, REPORT.md (whichever exist yet), and the repository
itself (files, git log, git status, git branch -vv).

Check:
1. The text does what was asked: the right task, the content wanted, nothing nobody asked to
   say.
2. Every factual claim against a source — criterion wording (verbatim from the approved file)
   and status, file and test names, numbers, claims about how the code behaves (open the code),
   and above all what was committed, pushed or changed: git must confirm it.
3. No NOT PROVEN or NOT MET turned into something greener.
4. The language matches the ticket's.

Reply: `OK`, or `quote -> problem -> what the source says`, one per line.
<the "Agents" block from SKILL.md, reply cap 20 lines>
```
