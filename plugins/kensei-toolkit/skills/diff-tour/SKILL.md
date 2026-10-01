---
name: diff-tour
description: Annotated diff for self-review before a commit — renders the changes (uncommitted work with untracked files, or a ref or range) as a local HTML page in the system browser, file by file, side by side or unified, with notes on what each change does and why it was made in this conversation, and marks every change no note explains as "Unexplained". Use when the user asks to see the changes — "show the diff", "what changed", "review before commit", "diff tour", «покажи дифф», «что поменялось», «дифф-тур», «ревью перед коммитом» — or when another skill or the user's CLAUDE.md says to show changes this way. Read-only — it never stages, commits or edits the repository. Run it when showing the changes is asked for, not on your own after every edit.
argument-hint: "[ref | a..b]"
---

# diff-tour — what changed, and why, before you commit

The user runs this before committing, to see that every change in the diff was made on purpose.
The built-in `/diff` already shows *what* changed. This page adds *why*, and its one signal is
**Unexplained**: changes that no note from this conversation accounts for — leftover debug code,
a stray edit, work from an earlier session.

The page: a headline and a plain-language paragraph, summary panels (the script's own
self-check first), a sticky bar with the file list and a side-by-side / unified switch, then one
card per file with notes placed under the lines they explain. It is a local file; nothing is
uploaded.

Design rationale (the owner's notes, not shipped with the plugin):
`~/docs/brainstorms/2026-09-24-diff-tour-skill.md`.

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
   A file that a skill's procedure produced as a by-product (run notes, reports, copied
   evidence) has no reason of that kind, even though a step told you to make it: mark it
   `inferred` and say what produced it, so the user can decide whether it belongs in the commit.
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

   - No argument: HEAD against the working tree, untracked included. When nothing is
     uncommitted (the work was just committed), collect compares HEAD with its upstream
     instead — the commits not pushed yet — or, when the upstream has them all or there is
     none, with the default branch (`origin/HEAD`, `main`, `master`): the branch's own work.
     It then prints `Nothing uncommitted — showing the commits HEAD has beyond <ref> instead.`
   - A ref: the working tree against the point where HEAD's history meets that ref (the
     merge-base) — `main` gives the branch's own work plus uncommitted changes, not main's
     newer commits reversed.
   - `a..b`: that range only, no working tree. Either side may be a commit or a tree id (a
     `git write-tree` result). `a...b` starts from the merge-base of two commits. A range's
     reasons are mostly `inferred` unless the work was done in this conversation.

   It prints the run directory, the base, the totals, the length of patch.diff, then one line
   per unit:
   `id  status  path  @@ header [facts]  +added -removed  L<line in patch.diff>`.
   `hN` is one hunk, or a whole file that has no hunks (binary, pure rename, mode change).
   `nN` is a whole file matching a noise pattern: lock files, minified, source maps, and the
   repository's optional `.claude/diff-tour-noise` — one gitignore-like glob per line: without
   `/` it matches a name at any depth, with `/` (or a leading `/`) from the repository root, a
   leading `**/` lets it start in any directory, a trailing `/` means a directory and everything
   under it. Noise units need a note too: a lock file that changed for no reason is worth seeing.
   - `No changes.` → nothing uncommitted and no commits beyond the upstream or default branch
     (or the given ref/range is empty). Tell the user and stop.
   - Exit 2 → show the error and stop.
   - A size `WARNING` → mention it to the user and carry on with the tour. Collect again with a
     narrower ref only if the user asks for one.

2. **Read the units.** Read `<run dir>/patch.diff` in one pass when collect reports up to
   2000 lines; otherwise read it in pieces by the `L` offsets, so that every unit is read once.
   Recall from this conversation why each change was made.

3. **Write `<run dir>/notes.json`.** An example for a Russian-speaking user:

   ```json
   {
     "lang": "ru",
     "title": "Моб больше не агрится на корабль в безопасной зоне станции",
     "lede": "Что было не так и что делает фикс — 2–4 простых предложения, можно `code`.",
     "link": { "url": "https://app.clickup.com/t/…", "label": "ClickUp 869f6uw9t" },
     "panels": [
       { "title": "Что изменилось", "text": "1 файл игрового кода, 2 файла тестов: …" },
       { "title": "Проверки", "checks": [
         { "pill": "6/6", "text": "новые тесты зелёные; до фикса 4 были красными" },
         { "pill": "не сделано", "text": "коммит, пуш", "warn": true } ] }
     ],
     "files": [
       { "path": "src/Npc/ServerNpcAiSystem.cs", "role": "игровой код", "kind": "prod" },
       { "path": "tests/NpcSafeZoneAggroTests.cs", "role": "новые тесты", "kind": "test" }
     ],
     "notes": [
       { "unit": "h3", "after": "if (!sp.InSafeZone && d < minDist)", "source": "session",
         "text": "**Сам фикс.** Корабль в зоне больше не может стать ближайшим …" },
       { "unit": "h2", "source": "session",
         "text": "**Блок перенесён, а не удалён** — теперь он идёт после станций." },
       { "unit": "h5", "after": "Debug.Log", "side": "new", "kind": "stray", "source": "session",
         "text": "Остался после отладки цикла агро — убрать до коммита." }
     ],
     "unexplained": { "h7": "добавляет Debug.Log в Update" }
   }
   ```

   - `lang` — the user's language; it picks the page labels (`ru`, otherwise English).
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

5. **Report** in the user's language: the page path, the base when collect fell back to one,
   the counts line, and the Unexplained list as build printed it. If build printed the drift
   `WARNING`, say it first — the page no longer matches what a commit would contain. Then
   stop. No follow-up action unless the user asks for one.

## When another skill calls it

A skill that has its own snapshot to show (for example ticket's publish gate: "run the
diff-tour against `<reviewed_tree>` vs `<base_sha>` and give the page path") runs the same
steps with these differences:

- Collect the exact range: `collect <base_sha>..<reviewed_tree>`. A tree id is accepted on
  either side, so the page shows the reviewed snapshot even if the working tree moved on.
- The calling skill's agreed criteria, test runs and review findings in this conversation
  are reasons you can point to, so notes built on them are `session`; the rules above still
  apply unchanged.
- Add `--open` only when someone is at the screen. Without it, build just writes the page.
  `--out-root <dir>` puts the run directory under `<dir>/<repo>/` instead of
  `~/.cache/kensei-diff` — use a directory outside the work tree or a git-ignored one, so the
  tour never shows up as untracked files in the next diff.
- Hand back the `Page:` path and the counts line from build's output instead of the full
  report; the caller decides what to show.

Run directories are private to the user (mode 0700); collect keeps the newest 20 per
repository and deletes older ones.
