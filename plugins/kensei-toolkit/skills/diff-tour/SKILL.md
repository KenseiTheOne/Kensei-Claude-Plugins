---
name: diff-tour
description: Annotated diff for self-review before a commit — renders the uncommitted changes (untracked files included) as a local HTML page in the system browser, file by file, side by side or unified, with notes on what each change does and why it was made in this conversation, and marks every change no note explains as "Unexplained". User-invoked only.
disable-model-invocation: true
argument-hint: "[ref | a..b]"
---

# diff-tour — what changed, and why, before you commit

The user runs this before committing, to see that every change in the diff was made on purpose.
The built-in `/diff` already shows *what* changed. This page adds *why*, and its one signal is
**Unexplained**: changes that no note from this conversation accounts for — leftover debug code,
a stray edit, work from an earlier session.

The page: a headline and a plain-language paragraph, summary panels (the script's own
self-check first), a sticky bar with the file list and a side-by-side / unified switch, then one
card per file with notes placed under the lines they explain.

**Design rationale:** `docs/brainstorms/2026-09-24-diff-tour-skill.md` in the user's home docs.

## Rules

1. **Code reaches the page only through the script.** notes.json refers to units by id and
   quotes at most a piece of one line to anchor a note. Do not write or edit `index.html`,
   `patch.diff` or `hunks.json` by hand.
2. **Unexplained is a result, not a failure.** A unit is explained when at least one note is
   about it. Write a note only when the change is part of something done on purpose. Never
   write a vague note to reach full coverage — a unit you cannot account for stays
   unexplained, and that is the most useful thing the page can show. The script does not
   reward coverage: units without notes are not an error.
3. **`source: "session"` only for a reason you can point to in this conversation** — the user
   asked for it, a bug was found, a decision was agreed. Everything else, and any doubt, is
   `"inferred"`. After a compaction, the summary counts only for what it states explicitly.
4. **Look at every unit before writing about it.** A hunk you remember writing can still carry a
   line you do not remember. When part of a hunk is unexplained, anchor a note with
   `kind: "stray"` under that line.
5. **Panels state facts from this session only.** A check pill such as `6/6 tests` needs the
   run that printed it in this conversation. What was not done (commit, device check) goes in
   as a pill with `warn: true` — never leave it out to look finished.
6. **Read-only.** Nothing is staged, committed, stashed, reverted or edited in the repository.
   Only the run directory is written. What to do about unexplained units is the user's call.

## Steps

1. **Collect.** Run from the repository:

   ```
   python3 "${CLAUDE_SKILL_DIR}/difftour.py" collect $ARGUMENTS
   ```

   No argument: HEAD against the working tree, untracked included. A ref: the working tree
   against the point where HEAD's history meets that ref (the merge-base) — `main` gives the
   branch's own work plus uncommitted changes, not main's newer commits reversed. `a..b`: that
   range only, no working tree — its reasons are mostly `inferred`, which is honest.

   It prints the run directory, the base, the totals, then one line per unit:
   `id  status  path  @@ header [facts]  +added -removed  L<line in patch.diff>`.
   `hN` is one hunk, or a whole file that has no hunks (binary, pure rename, mode change).
   `nN` is a whole file matching a noise pattern: lock files, minified, source maps, and the
   repository's optional `.claude/diff-tour-noise` — one gitignore-like glob per line: without
   `/` it matches a name at any depth, with `/` (or a leading `/`) from the repository root, a
   leading `**/` lets it start in any directory, a trailing `/` means a directory and everything
   under it. Noise units need a note too: a lock file that changed for no reason is worth seeing.
   - `No changes.` → tell the user and stop.
   - Exit 2 → show the error and stop.
   - A `WARNING` about size → mention it; continue unless the user narrows the ref.

2. **Read the units.** Read `<run dir>/patch.diff` — whole if it fits, otherwise by the `L`
   offsets. Recall from this conversation why each change was made.

3. **Write `<run dir>/notes.json`:**

   ```json
   {
     "lang": "ru",
     "title": "The mob no longer aggroes on a ship inside the station safe zone",
     "lede": "What was wrong and what the fix does, 2–4 plain sentences, `code` allowed.",
     "link": { "url": "https://app.clickup.com/t/…", "label": "ClickUp 869f6uw9t" },
     "panels": [
       { "title": "What changed", "text": "1 game code file, 2 test files: …" },
       { "title": "Checks", "checks": [
         { "pill": "6/6", "text": "new tests green; 4 were red before the fix" },
         { "pill": "not done", "text": "commit, push", "warn": true } ] }
     ],
     "files": [
       { "path": "src/Npc/ServerNpcAiSystem.cs", "role": "game code", "kind": "prod" },
       { "path": "tests/NpcSafeZoneAggroTests.cs", "role": "new tests", "kind": "test" }
     ],
     "notes": [
       { "unit": "h3", "after": "if (!sp.InSafeZone && d < minDist)", "source": "session",
         "text": "**The fix itself.** A ship in the zone cannot become the nearest one …" },
       { "unit": "h2", "source": "session",
         "text": "**This block is moved, not deleted** — it now follows the stations." },
       { "unit": "h5", "after": "Debug.Log", "side": "new", "kind": "stray", "source": "session",
         "text": "Left over from debugging the aggro loop — remove before the commit." }
     ],
     "unexplained": { "h7": "adds Debug.Log to Update" }
   }
   ```

   - `lang` — the session's language; it picks the page labels (`ru`, otherwise English).
     Write every text field in that language.
   - `title` — the change in terms of behaviour, one sentence. `lede` — the problem and the fix
     for someone who has not read the code.
   - `link` — optional, http(s) only: the task, if there is one.
   - `panels` — optional, up to three; each has `text` or `checks` (`pill`, `text`, `warn`).
     The script adds its own Self-check panel (unexplained, flags, inferred notes, staleness) —
     do not repeat those counts.
   - `files` — optional: the order of the file cards (most important first; files you leave
     out follow in diff order), a short `role` badge, and `kind` — `prod` (highlighted badge),
     `test`, `docs`, `config`, `meta`; `kind` without `role` shows a default badge.
   - `notes` — the heart of the page. Each note is about one unit and says what the change
     does and why. Lead with a **bold phrase**. With `after`, the note sits under the line
     whose text contains that string; it must match exactly one line of the unit — quote more
     of the line, or narrow it with `"side": "old"` (removed lines only) or `"new"` (added lines
     only); context lines are matched only without `side`. That is how a duplicated line next
     to its original is anchored. Without `after`, it sits at the top of the unit. A unit can have
     several notes; say what a reviewer would otherwise have to work out, not what the line
     already says.
   - `kind` on a note — only when there is something to check: `untested` (not run or not
     covered by a test), `decision` (a debatable choice with a real alternative), `temporary`
     (temporary or debug code), `stray` (part of the hunk nothing explains).
   - `unexplained` — optional; *what* changed in a unit that has no notes, never *why*.
   - Markup — in `title`, `lede`, panel `text`, check `text`, note `text` and `unexplained`
     only: `backticks` for code, `**bold**` (may contain code), line breaks. Nothing else; HTML
     is shown as text. Panel titles, pills, roles and the link label are plain text.

4. **Build:**

   ```
   python3 "${CLAUDE_SKILL_DIR}/difftour.py" build "<run dir>" --open
   ```

   Exit 1 lists every problem in notes.json — fix all of them and run build again. Never rerun
   collect to get past a notes problem: it takes a new snapshot with new ids.
   `--open` shows the page in the system browser. Never open it with a bare `open`: terminals
   such as cmux shadow `open` on PATH and put the page in a side pane instead.

5. **Report** in the session's language: the page path, the counts line, and the Unexplained
   list as build printed it. If build printed the drift `WARNING`, say it first — the page no
   longer matches what a commit would contain. Then stop. No follow-up action unless the user
   asks for one.
