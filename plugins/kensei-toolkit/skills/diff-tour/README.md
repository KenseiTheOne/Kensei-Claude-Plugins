# diff-tour — maintainer notes

Not loaded by the skill; `SKILL.md` is what the model reads.

## Files

- `difftour.py` — `collect` (snapshot and unit index) and `build` (checks notes.json, renders
  the page).
- `assets/` — the page itself: `page.html` (document shell with `$lang`, `$title`, `$style`,
  `$body`, `$highlight`, `$script`), `page.css` (light theme; `%DARK%` marks where the tokens of
  `dark.css` go), `page.js` (view switch, unit links, per-line highlighting).
- `difftour_test.py` — run `python3 difftour_test.py`. `testdata/golden-*.html` pins the page
  for a fixed input byte for byte; after an intended change to the page, regenerate them with
  `DIFFTOUR_REGEN_GOLDEN=1 python3 difftour_test.py` and review the change in the goldens.

## Noise patterns

A repository can list its own generated files in `.claude/diff-tour-noise`, one pattern per
line; blank lines and lines starting with `#` are skipped. Each file that matches becomes one
`nN` unit, folded on the page. The patterns are gitignore-like globs:

- without `/` — matches a file name at any depth (`*.g.cs`);
- with `/`, or a leading `/` — matches from the repository root (`/Generated/Proto.cs`);
- a leading `**/` — lets a pattern with `/` start in any directory (`**/obj/cache.bin`);
- a trailing `/` — a directory and everything under it (`generated/`).

The built-in list covers lock files, minified files and source maps (`DEFAULT_NOISE`).

## Run directories

`collect` writes to `~/.cache/kensei-diff/<repo>/<timestamp>/` (mode 0700) and keeps the newest
20 runs per repository there. A caller that links to the page from its own record passes
`--out-root <its run dir>`: rotation then counts only the runs under that root. That root must be
outside the work tree or git-ignored, or the tour shows up as untracked files in the next `collect`.
