---
name: learn
description: Review the current session and propose durable takeaways, each routed to one home — project CLAUDE.md for rules every contributor and headless run needs, the auto-memory for facts about the user, ~/.claude/CLAUDE.md for preferences that hold in every project. Deduplicates against all three, writes only what the user approves. Run at the end of a session. User-invoked only.
disable-model-invocation: true
argument-hint: "[path/to/CLAUDE.md | focus]"
---

# Learn — capture session takeaways

Turn what this session taught into a few durable notes so future sessions start better informed.
Each note goes to exactly one place, nothing is written before the user approves it, and a short
honest "nothing worth keeping" is a good outcome.

Reply in the user's language. Text written into a file matches that file's existing language; a
new file takes the user's language.

## Step 1 — Read what is already recorded

Read all of these before mining, so every proposal is checked against them:

- **Project rules:** `$ARGUMENTS` when it is a file path; otherwise the `CLAUDE.md` in the working
  directory or the nearest parent up to the repo root, plus any nested `CLAUDE.md` in directories
  this session worked in, and `CLAUDE.local.md` if present.
- **Global rules:** `~/.claude/CLAUDE.md`.
- **Auto-memory:** the memory directory of this project — the one whose `MEMORY.md` is in the
  session context; if none is shown, `~/.claude/projects/<slug>/memory/`, where `<slug>` is the
  absolute repo root path (or working directory outside a repo) with every character other than a
  letter or digit replaced by `-`, e.g. `/Users/me/app` → `-Users-me-app`. Read `MEMORY.md` now;
  it is an index of one-line pointers, and the memory files behind it are opened in Step 2.

Missing files are fine; note which ones exist. If there is no project `CLAUDE.md`, the target is
`<repo root>/CLAUDE.md` (the working directory outside a repo), created on approval.

## Step 2 — Mine the session

When `$ARGUMENTS` is text other than a file path ("only the build gotchas"), it narrows the search
to that focus. Look for durable facts:

- **Conventions** the user stated ("we never use X here", "always Y").
- **Commands** for build, test, lint, run or deploy that are specific to this project.
- **Gotchas** — surprising behavior, wrapped or broken tools, paths that need special handling.
- **Architecture pointers** that a quick directory listing would not reveal.
- **Corrections** — a wrong assumption the user corrected, when the lesson outlives this task.
- **About the user** — preferences, working style, role, recurring context across their projects.

Keep a candidate only when it will still matter in a month and cannot be learned in a minute from
the code, `git log`, `--help` or the README. Task-specific details belong in the commit, not here.

Before proposing a candidate, open the memory files whose `MEMORY.md` line matches its topic.
Drop anything already recorded in Step 1 sources or those files. When a candidate refines an
existing entry, propose an update to that entry instead of a new one.

Never propose secrets, tokens, credentials, private or signed URLs, internal hostnames, or personal
data about third parties; restate the lesson without them or drop it.

Aim for a few strong items; three good ones beat fifteen weak ones. If nothing qualifies, say so in
one sentence and stop.

## Step 3 — Route each candidate

| Destination | What goes there |
|---|---|
| **Project `CLAUDE.md`** (or the `$ARGUMENTS` path) | Rules, conventions, commands and gotchas every contributor and every headless run in this repo needs. Checked into the repo, so nothing personal. |
| **Auto-memory** | Facts about the user: preferences, feedback on how to work, their role, references they use, project context that is theirs rather than the repo's. Seen only in this project. |
| **`~/.claude/CLAUDE.md`** | A preference about the user that clearly applies in every project (reply language, diff display, publishing habits). The only file every project reads. |

When a candidate fits `CLAUDE.md` and memory, choose `CLAUDE.md` if a teammate or a headless run
would need it. When a fact about the user could go to memory or the global file, choose the global
file only when it plainly holds outside this repo; otherwise memory, and say in the proposal that
it stays in this project.

## Step 4 — Show proposals and ask

Print every proposal, grouped by destination, numbered across groups:

```
### CLAUDE.md — <path>   (new file, when it does not exist yet)
1. [<section>] <text, 1–3 lines, ready to paste>   (new | updates "<existing line>")
   Source: <where in the session this came from>

### Auto-memory — <memory dir>   (this project only)
2. <file>.md (new | update) · type: feedback — <one-line description>
   <body, 1–3 lines>
   Source: <...>

### Global CLAUDE.md — ~/.claude/CLAUDE.md
3. [<section>] <text>   (new | updates "<existing line>")
   Source: <...>
```

Use the existing `CLAUDE.md` section headings when one fits.

Then ask with `AskUserQuestion`. Each question covers one destination, and its text names it
("Add to the project CLAUDE.md?", "Save to auto-memory (this project only)?", "Add to the global
~/.claude/CLAUDE.md?"; header `CLAUDE.md`, `Memory` or `Global`), so a tick is consent for that
destination; items for different destinations never share a question. A question holds 2–4
options and one call holds up to 4 questions, so:

- one `multiSelect` question per destination, one option per item: label `N. <short name>`,
  description = the first line of the text;
- a destination with more than 4 items splits into batches of up to 4 (`Memory 1/2`,
  `Memory 2/2`), balanced so no batch holds a single item;
- a destination with exactly one item gets a single-select question with options `Apply` and
  `Skip`, the item in the question text;
- all questions go in one call when they fit in 4; otherwise the rest go in a later call.

Ticked items are applied; unticked are skipped. The built-in **Other** field takes edits in plain
words — a new wording (`2: <new text>`) or a move to another destination (`2: global`); say so in
the question text, apply the edits, and show the changed lines once before writing.

When `AskUserQuestion` is unavailable, ask the same question in plain text and wait for the
answer; never skip the choice.

## Step 5 — Write the approved items

**Project or global `CLAUDE.md`:** one targeted `Edit` per item under its section, or a new
section at the end. Touch only the lines you add or update. If the file does not exist, `Write` it
at the path shown in the group header with only the approved sections.

**Auto-memory:** one fact per file, named `<kebab-name>.md`. Updating an existing file is preferred
over a new one. Mirror the frontmatter of existing memory files; at minimum:

```markdown
---
name: <kebab-name>
description: <one line — what the fact is, used to judge relevance later>
metadata:
  type: user | feedback | project | reference
---

<the fact>

**Why:** <what in the session prompted it>

**How to apply:** <when and how it should change behavior>
```

`Why` and `How to apply` are for `feedback` and `project`; `user` and `reference` can be the fact
alone. Then add or update one line in `MEMORY.md`: `- [Title](<file>.md) — <short hook>`.
`MEMORY.md` holds only these pointers, never the facts themselves; create it if it is missing.

## Step 6 — Report

One or two sentences: what was written where (file paths), what was skipped or reworded.
