---
name: todo
description: Mine the current session for actionable todos and update a TODO.md artifact — unfinished work, deferred items, identified bugs, "we should also..." callouts, open questions. Run at the end of a session to capture loose ends. User-invoked only.
disable-model-invocation: true
argument-hint: "[path/to/TODO.md]"
---

# Todo — collect session loose ends into TODO.md

Analyze the current session and propose entries for a project `TODO.md` so nothing actionable falls through the cracks. Manual, user-triggered.

**Do not modify `TODO.md` until the user has approved the items.** Approval-first; no silent writes.

## Step 1 — Locate the target file

Resolve the target path in this order:

1. If `$ARGUMENTS` looks like a file path → that path **is** the target. If the file exists, read it. If it doesn't, create it there in Step 5 — do **not** ask the user to pick a different location. Honoring the explicit argument trumps discovery.
2. Else look for `TODO.md` in the current working directory, then walk up parents until one is found or the repo root is reached.
3. If still nothing, ask the user: create one in the cwd, in the repo root, or skip.

When you found an existing file, read it in full. You **must** know its current contents — you'll be checking against it to avoid duplicate entries.

## Step 2 — Mine the session

Look through the conversation for **actionable, deferrable items** in these buckets:

- **Bugs** — defects spotted but not fixed this session ("we noticed X is broken but moved on", failing edge case left for later, error case the user said to handle later).
- **Features** — work the user mentioned wanting but didn't ask to do now ("we should also add Y", "next time let's wire up Z").
- **Refactor / tech debt** — code smells, duplication, abstraction the user agreed needs cleanup but deferred ("ugly but works", "TODO: simplify this later").
- **Open questions** — decisions the user explicitly postponed ("need to think about X", "ask the team about Y"), or unknowns that blocked a clean answer this session.
- **Follow-ups from completed work** — verification steps, missing tests, docs updates, or related cleanup that the just-finished task implies but didn't include.

**Trigger phrases to watch for:**
- English: "todo", "fix later", "later", "next time", "remind me", "we should", "we could", "would be nice", "for now", "leave it"
- Russian (with glosses): "потом" (later), "позже" (later), "напоминай" (remind me), "надо будет" (will need to), "не сейчас" (not now), "позднее" (later), "доделать" (finish up), "пока что" (for now)

**Skip aggressively:**

- Anything already done this session (it's in the diff, not the todo list).
- Anything already present in the existing `TODO.md` (check before proposing — match by intent, not exact wording).
- Items the user explicitly rejected or said don't matter.
- Vague aspirations with no concrete action ("the codebase could be better").
- Personal reminders unrelated to the project (those belong in a personal task manager, not project `TODO.md`).
- Items better suited to the project's issue tracker if the user has one — list these in Step 3 under a separate `[Issue tracker]` group **outside** the AskUserQuestion options, and note them in the Step 6 confirm. Do not add them to `TODO.md` unless the user explicitly asks.

**Quality bar:** prefer **3 concrete entries** over 15 vague ones. Each item should be specific enough that a future session can act on it without re-reading this conversation. If the session yielded nothing actionable, say so honestly and stop — don't pad.

## Step 3 — Present proposals

Print a numbered list of **all** candidates so the user can read them in full. For each candidate:

```
N. [Category] Proposed entry (one line, ready to paste as a checkbox item)
   Source: <one short sentence — where in the session this came from>
```

Group by category (Bugs / Features / Refactor / Open questions / Follow-ups). If the existing `TODO.md` already has matching section headings, use those exact headings; don't invent new ones when an existing one fits.

## Step 4 — Get approval via AskUserQuestion

After printing the list, **call `AskUserQuestion`** for the actual selection — don't ask in plain text. Build options dynamically from the proposals:

- **`Question:`** `"Which todos should I add to TODO.md?"`
- **`Header:`** `"Add"`
- **`multiSelect: true`**
- **Options:**
  - One option per proposal (label = `"N. <short name>"`, description = the category + first line). Include as many as the tool's option cap allows.
  - If there are more proposals than option slots, collapse the rest into a single `"Remaining (K items)"` option whose description lists their numbers (e.g., `"items 4, 5, 6, 7"`).
  - Always include `"All"` and `"None"` as the last two options.

**Interpreting the answer:**

- `"All"` ticked → apply every proposal (ignore other ticks).
- `"None"` ticked → write nothing (ignore other ticks).
- `"Remaining (K items)"` ticked → immediately fire a **second `AskUserQuestion`** containing only the collapsed items (same multiSelect pattern, with `"All"`/`"None"`). Merge the user's picks there with any specific items they also ticked in the first round.
- Specific items ticked → apply only those.
- "Other" / free text → parse as a comma list (`1,3,5`) or per-item wording edits.

If the user wants to tweak the wording of a specific item, accept their edit and use the edited version when applying.

## Step 5 — Apply

For each approved item:

- Format as a markdown checkbox: `- [ ] <entry text>`.
- If a matching section already exists in `TODO.md`, append the item there with a single targeted `Edit`.
- If not, add a new section at the end of the file using the category name as the heading (e.g., `## Bugs`).
- Do not reformat or rewrap unrelated content. Touch only the lines you're adding.
- Do not check off, remove, or reorder existing items — this skill only adds.

If `TODO.md` doesn't exist yet (either the user said to create it in Step 1, or `$ARGUMENTS` named a missing path), `Write` a new file with this exact scaffold and nothing more:

```markdown
# TODO

## <Category 1>

- [ ] <approved item>
- [ ] <approved item>

## <Category 2>

- [ ] <approved item>
```

Only include category sections that have at least one approved item. No description blurb under `# TODO`, no placeholder sections, no horizontal rules.

## Step 6 — Confirm

One- or two-sentence summary: how many items were added, to which file, and whether any were skipped, hand-edited, or flagged as better suited to an issue tracker. No paragraph-long retrospective.

## Language

Respond in the same language the user has been using in the session. New `TODO.md` content should match the language of the existing file; if creating the file fresh, match the user's language.
