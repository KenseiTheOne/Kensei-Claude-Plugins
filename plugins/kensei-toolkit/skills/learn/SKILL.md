---
name: learn
description: Analyze the current session and propose additions to project CLAUDE.md — new conventions, useful commands, gotchas, project-specific quirks. Run at the end of a session to capture what was learned. User-invoked only.
disable-model-invocation: true
argument-hint: "[path/to/CLAUDE.md]"
---

# Learn — capture session takeaways into CLAUDE.md

Analyze the current session and propose additions to a project `CLAUDE.md` so future Claude sessions in this codebase start better-informed. Manual, user-triggered.

**Do not modify `CLAUDE.md` until the user has approved the items.** Approval-first; no silent writes.

## Step 1 — Locate the target file

Resolve the target path in this order:

1. If `$ARGUMENTS` looks like a file path → use it.
2. Else look for `CLAUDE.md` in the current working directory, then walk up parents until one is found or the repo root is reached.
3. If none exists, ask the user: create one in the cwd, in the repo root, or skip.

Read the existing file (if any). You **must** know its current contents — you'll be checking against it to avoid duplicates.

## Step 2 — Mine the session

Look through the conversation for **durable, project-scoped facts** in these buckets:

- **Conventions** — preferences the user stated explicitly (`"we never use X"`, `"always Y in this repo"`) that should constrain future code here.
- **Commands** — non-obvious build / test / lint / run / deploy commands specific to this project (not generic `npm test`).
- **Gotchas** — surprising behavior, environment quirks, broken or wrapped tools, files that look unused but aren't, paths that need special handling.
- **Architecture pointers** — `"module X handles Y"`, `"entry point is Z"` — only when hard to discover from a quick directory listing.
- **Mistakes & corrections** — wrong assumptions Claude made that got corrected, *when the rule generalizes beyond the immediate task*.

**Skip aggressively:**

- Anything specific to the current task / bug / PR (belongs in the commit, not in `CLAUDE.md`).
- Anything already documented in the existing project `CLAUDE.md` *or* the user's global `CLAUDE.md` (visible in the loaded `claudeMd` context — check both before proposing).
- Anything trivially derivable from `git log`, `--help`, `package.json`, `README`, or 30 seconds of code reading.
- Style/git preferences that already live in user-global rules.
- Personal context that belongs in `MEMORY.md`, not project rules — facts about *the user* go to memory; facts about *the project* go here.

**Quality bar:** prefer **3 strong entries** over 15 weak ones. If the session yielded nothing durable, say so honestly and stop — don't pad.

## Step 3 — Present proposals

First print a numbered list of **all** candidates so the user can read them in full. For each candidate:

```
N. [Section] Proposed text (1–3 lines, ready to paste)
   Source: <one short sentence — where in the session this came from>
```

Group by suggested section heading. If the existing `CLAUDE.md` already has matching sections, use those exact headings; don't invent new ones when an existing one fits.

## Step 4 — Get approval via AskUserQuestion

After printing the list, **call `AskUserQuestion`** for the actual selection — don't ask in plain text. Build options dynamically from the proposals:

- **`Question:`** `"Which proposals should I add to CLAUDE.md?"`
- **`Header:`** `"Apply"`
- **`multiSelect: true`**
- **Options:**
  - One option per proposal (label = `"N. <short name>"`, description = the section + first line). Include as many as the tool's option cap allows.
  - If there are more proposals than option slots, collapse the rest into a single `"Remaining (K items)"` option whose description lists their numbers. The user can drill in via "Other".
  - Always include `"All"` (label, no number) and `"None"` as the last two options.

**Interpreting the answer:**

- `"All"` ticked → apply every proposal (ignore other ticks).
- `"None"` ticked → write nothing (ignore other ticks).
- Specific items ticked → apply only those.
- "Other" / free text → parse as a comma list (`1,3,5`) or per-item edits.

If the user wants to tweak the wording of a specific item, accept their edit and use the edited version when applying.

## Step 5 — Apply

For each approved item:

- If a matching section already exists in `CLAUDE.md`, append the entry there with a single targeted `Edit`.
- If not, add a new section at the end of the file.
- Do not reformat or rewrap unrelated content. Touch only the lines you're adding.

If `CLAUDE.md` doesn't exist yet and the user said to create it, `Write` a minimal new file containing only the approved sections — no boilerplate, no placeholder headings the user didn't ask for.

## Step 6 — Confirm

One- or two-sentence summary: how many items were added, to which file, and whether any were skipped or hand-edited. No paragraph-long retrospective.

## Language

Respond in the same language the user has been using in the session. New `CLAUDE.md` content should match the language of the existing file; if creating the file fresh, match the user's language.
