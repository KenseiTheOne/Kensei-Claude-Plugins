---
name: todo
description: "Collect the loose ends of the current session — unfinished work, deferred items, bugs found, \"we should also…\", open questions — as task drafts with evidence, let the user pick, then deliver them: personal items to the Todoist Inbox (or a paste-ready block), project work to a ClickUp list the user picks, or to a markdown file given as the argument. User-invoked only."
disable-model-invocation: true
argument-hint: "[path/to/notes.md | focus]"
---

# Todo — turn session loose ends into tasks

At the end of a session, things get said and left behind: a bug noticed and not fixed, "we should
also…", a question postponed. This skill finds them, drafts each as a task the user can act on
without rereading the conversation, and puts the chosen ones where the user already keeps tasks.

The user approves every task before it exists anywhere. A task is created in Todoist, ClickUp or a
file only when the user selected it, and its destination, in this run.

Destinations:

- **Personal** items go to the **Todoist Inbox** — the user's single capture funnel on every device.
- **Project work** goes to **ClickUp**, into a list the user picks in this run. The workspace and
  lists are found at run time (Step 4).
- If `$ARGUMENTS` is a path ending in `.md`, every chosen item is appended to that file instead
  (file mode, Step 6c). Any other argument text ("only bugs", "the auth work") is a focus hint for
  Step 1, and delivery follows the destinations above.

## Step 1 — Mine the session

Read through the whole conversation for actionable items that were left for later:

- **Bugs** — defects seen and not fixed: a failing edge case, an error the user said to handle
  later.
- **Unfinished work** — steps of the task that were planned and not done, or done partly.
- **Deferred ideas** — "we should also add Y", "next time let's wire up Z".
- **Tech debt** — cleanup the user agreed is needed and postponed.
- **Open questions** — decisions the user postponed ("ask the team about Y"), or unknowns that
  blocked a clean answer.
- **Follow-ups** — verification, tests, docs or release steps the finished work implies and did
  not include.
- **Personal** — non-project reminders that came up ("надо продлить подписку", "read that
  article").

Phrases that often mark them: "later", "next time", "remind me", "we should", "would be nice",
"for now", "leave it"; «потом», «позже», «надо будет», «не сейчас», «доделать», «пока что»,
«напомни».

Leave out:

- anything finished in this session;
- items the user rejected or said do not matter;
- vague wishes with no concrete action ("the code could be cleaner").

Each draft is a self-contained task title — a verb, the object, and enough context to act on it a
week later (repo, file, feature) — plus a one-line **evidence** note: where in the session it came
from, with a short quote or the fact behind it, e.g. `user: «кэш прикрутим потом»` or
`guard_test.py: test_bundle_flags fails on -fn, left for later`.

Three concrete tasks beat fifteen vague ones. If the session left nothing actionable, say so in one
sentence and stop.

## Step 2 — Deduplicate and classify

Merge drafts that describe the same action, keeping the clearest wording and both evidence lines.
In file mode, read the target file in full and drop drafts already present there (match by intent,
not wording).

Mark each draft with its destination:

- **ClickUp** — work on a project tracked in ClickUp: the repo's project rules, the session or the
  ticket being worked on point to a ClickUp task, list or space.
- **Todoist** — everything else: personal errands, learning, the user's own machine and tools, and
  project work on something not tracked in ClickUp.

When a draft could go either way, pick the likelier one and add `(?)` to its destination so the
user sees it is a guess. In file mode the destination is the file for every draft; skip this mark.

## Step 3 — Show the drafts

Print every draft as a numbered list, grouped by destination:

```
ClickUp
1. Handle -fn bundled flag in guard push detection
   evidence: guard_test.py: test_bundle_flags fails on -fn, left for later

Todoist
2. Renew the Apple developer membership (?)
   evidence: user: «надо продлить подписку, истекает в ноябре»
```

## Step 4 — Find ClickUp lists

Run this step when a draft is marked ClickUp and this is not file mode. Looking the lists up now
lets Step 5 ask for the items and the list in one call.

1. **Tools.** The ClickUp tools come from whichever MCP server the user connected; their names end
   in `clickup_search`, `clickup_get_workspace_hierarchy`, `clickup_create_task`. They are often
   deferred: load them with `ToolSearch` (query `clickup`). If there are none, say in one line
   that ClickUp is not reachable; those drafts get no question in Step 5 and are
   printed as a paste-ready block in Step 6b.
2. **Workspace.** Take the workspace, space or list named in the project rules (`CLAUDE.md`,
   `.claude/*rules*.md`) or in `~/.claude/CLAUDE.md`, or the one the session's ClickUp task
   belongs to. Otherwise read `clickup_get_workspace_hierarchy`: with one workspace, use it; with
   several, ask which in a single-select `AskUserQuestion` first (up to 4 workspaces as options;
   with more, the 3 likeliest and the rest through Other).
3. **Lists.** With read-only calls (`clickup_search`, `clickup_get_workspace_hierarchy`) pick up
   to 3 lists that fit the project, repo or ClickUp task the session was about.

## Step 5 — Let the user choose

Ask with `AskUserQuestion`. Each question covers one destination, and its text names it ("Add to
the Todoist Inbox?", "Create in ClickUp?", "Append to notes.md?"), so a tick is consent for that
destination; drafts for different destinations never share a question. A question holds 2–4
options and one call holds up to 4 questions, so:

- one `multiSelect` question per destination, one option per draft: label `N. <short title>`,
  description = the evidence line;
- a destination with more than 4 drafts splits into batches of up to 4 (`ClickUp 1/2`,
  `ClickUp 2/2`), balanced so no batch holds a single draft;
- a destination with exactly one draft gets a single-select question with options `Add` and
  `Skip`, the draft and its evidence in the question text;
- ClickUp adds one single-select question, "Create the chosen ClickUp tasks in which list?":
  options = up to 3 lists — the Step 4 lists, or when none fit, those of the likeliest space —
  label = list name, description = space / folder, plus `Don't create — print them`;
- all questions go in one call when they fit in 4; otherwise the rest go in a later call, and the
  list question rides in the same call as the first ClickUp batch and covers every ClickUp batch.

Each list option and `Create here` (below) end with ` [create-task]` (`Backlog [create-task]`),
since picking a list is what commits to the create; draft options, `Add`, `Skip` and
`Don't create` carry no tag. When `/ticket` ran earlier in the session, its guard allows a task
create only after the user picked an option with that tag.

No option slot is filler. Leaving a question unticked means none from that batch; the built-in
**Other** field takes edits in plain words — a new wording ("2: продлить до 15 ноября"), a
destination switch ("3 → Todoist"), an extra task, or a list name. Apply edits before Step 6 and
show the changed lines once; an edit the user typed is their consent for Todoist or the file it
names, while a ClickUp create still needs a picked `[create-task]` option.

When `AskUserQuestion` is unavailable, ask the same question in plain text and wait for the
answer; never skip the choice. With no option to pick, a ClickUp create needs the user to type
the command and the list («создай задачи в Backlog»).

A ClickUp create that no picked option covers — a list typed into Other, a draft moved to ClickUp
by an edit — gets one confirm question first: resolve the list by name (read-only, Step 4 lookup
if none ran), then ask single-select "Create N tasks in <list> (<space / folder>)?" with options
`Create here [create-task]` and `Don't create — print them`.

If nothing is chosen, say so in one line and stop.

## Step 6 — Deliver

### 6a. Todoist items

1. **Todoist MCP or CLI connected.** Look for Todoist tools among the callable and the deferred
   tools (load deferred ones with `ToolSearch`, query `todoist`), and for a CLI
   (`command -v todoist td`). A CLI counts only when its `--help` or version output names Todoist:
   Homebrew's `td`, for one, is an unrelated local todo list. If one is available, create each
   chosen item as a task in the Inbox with the title as content and the evidence line as its
   description. Set no project, labels, priority or due date unless the user asked for them in
   this run. If the tool can list Inbox tasks, skip items already there and say which.
2. **Otherwise**, print a paste-ready block. Todoist turns a multi-line paste into one task per
   line after a single confirmation in its own app:

   ````
   ```text
   Renew the Apple developer membership
   Read the Unity 6.3 ECS migration notes
   ```
   ````

   One task per line, plain text: no bullets, checkboxes or numbering. Todoist parses `#word`,
   `@word`, `p1`–`p4` and date words ("tomorrow", "15 Nov") on paste; keep them out of titles
   unless the user wants that project, label, priority or date. Add one line under the block:
   "Paste into the Todoist Inbox; it offers to add N tasks." Evidence lines stay in this reply.

### 6b. ClickUp items

When ClickUp was not reachable in Step 4, or the user picked `Don't create — print them`, print
these items as a paste-ready block like 6a. Otherwise, in the list chosen in Step 5:

1. **Check for duplicates.** Search the chosen list read-only (`clickup_search` or
   `clickup_filter_tasks`) for open tasks with the same intent. Leave matches out, and name each
   one with its link in the report.
2. **Create**, only after the list is chosen in this run. Each task gets `name` and `list_id`, and
   a `markdown_description` holding the evidence line plus where it came from (repo, branch,
   related ClickUp task link if the session had one). Leave `status`, `assignees`, `priority`,
   `tags`, dates and custom fields at the list defaults unless the user asked for them in this run.
   One task: `clickup_create_task`. Two or more: call `clickup_get_operators` first and run a bulk
   create through `clickup_execute_operator` when one exists; otherwise one `clickup_create_task`
   per task.
3. If a create fails, report it with the error, stop creating, and print the remaining tasks as a
   block; the user can pick another list in a new run.

### 6c. File mode (`$ARGUMENTS` is a path)

- The path is the target. If the file exists, it was read in Step 2; if not, it is created there.
- Each chosen item becomes `- [ ] <title>`. Append it under an existing heading that fits its
  category with a targeted `Edit`; otherwise add a `## <Category>` section at the end.
- A new file starts with `# TODO`, then one `## <Category>` section per category that has items,
  and nothing else.
- Touch only the lines you add: existing items keep their text, order and check state.
- Write items in the language of the existing file; for a new file, in the user's language.

## Step 7 — Report

One or two sentences: how many tasks went where, ClickUp tasks as markdown links with the task name
as the anchor text (`[Handle -fn bundled flag](https://app.clickup.com/t/…)`), and anything skipped,
edited, or left as a paste block.

## Language

Talk to the user in the language of the session. Write task titles in that language too, unless
the destination already uses another one (an English file, an English ClickUp list) — then match
the destination. Quotes in evidence lines stay in their original language.
