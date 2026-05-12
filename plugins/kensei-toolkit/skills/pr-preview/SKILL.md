---
name: pr-preview
description: Render proposed changes as a standalone HTML Pull Request preview — GitHub-style split/unified view with unselectable line numbers, red/green line coloring, and a view toggle. Use when the user wants to review changes before applying them, or wants a PR-style summary of a set of edits.
disable-model-invocation: true
argument-hint: "[task description | path to save PR.html]"
---

Produce a standalone HTML Pull Request preview for: $ARGUMENTS

**Do not modify any source files.** This skill is a preview — it writes only one file: the PR HTML.

## Output file

- Always HTML. Default path: `PR.html` in the current working directory.
- If `$ARGUMENTS` ends with `.html` and looks like a path, treat it as the output path and infer the task from conversation context.
- **If the file already exists**, first peek at its first line. If it's `<!doctype html>` (a previous pr-preview output), overwrite silently. Otherwise — unfamiliar file at that path — pick a unique name like `PR-2.html` or `PR-{YYYY-MM-DD-HHMM}.html` to avoid clobbering user data, and tell the user which name you used.

## How to build the file

1. **Read the template** at `template.html` (sibling of this SKILL.md) — it contains all the CSS, the view toggle, and placeholder markers.
2. **Replace each marker** with real content (see markers list below).
3. **Write the result** to the output path. Do not modify the CSS in the template — it's tuned so line numbers render via CSS counters (unselectable) and red/green comes from classes (no `<pre>` / `<code>` diff lexer needed).

### Markers in `template.html`

| Marker | Replace with |
|---|---|
| `<!-- TITLE -->` | Concise PR title (plain text, appears in `<title>` and `<h1>`) |
| `<!-- SUMMARY -->` | 1–3 `<p>` sentences — what changes and why |
| `<!-- CHANGES -->` | `<li>` items, one per logical change |
| `<!-- STATS_TOTAL -->` | Inline stats next to "Files changed" header: `N files, <span class="add">+X</span> <span class="del">−Y</span>`. Always include, even for 1 file. |
| `<!-- FILE_INDEX -->` | A `<details class="file-index" open><summary>N files changed</summary><div class="file-index-list">…</div></details>` with one `<a href="#f-{slug}">` per file showing path + counts. Omit entirely for ≤3 files. |
| `<!-- FILES -->` | For each changed file: one `<details class="file" id="f-{slug}" open>` block with summary, then `.mode-unified` and `.mode-split` (see below) |
| `<!-- TESTS -->` | `<li>` items with `<input type="checkbox">` — how to verify |
| `<!-- NOTES_SECTION -->` | `<h2>Notes</h2>` + `<ul>` if there are risks/follow-ups; omit entirely if none |

## Row classes (this is the core)

Every code line inside a diff is a `<div class="row …">`. The class controls colour **and** line-number increment:

- `row ctx` — unchanged context line. Increments both old and new counters. No background.
- `row add` — added line. Increments only `new`. Green background. Old gutter column stays blank.
- `row del` — removed line. Increments only `old`. Red background. New gutter column stays blank.

You do **not** write the line numbers yourself — CSS counters do it. Just use the right row class and order.

## Structure for one file (both modes)

Each changed file is wrapped in `<details class="file" id="f-{slug}" open>` with a `<summary class="filename">` header that shows path + per-file counts. Inside, emit both unified and split markup back-to-back — the view toggle hides one at a time. The `id` slug is the file path with `/` and `.` replaced by `-` (e.g., `Assets/Core/Foo.cs` → `f-Assets-Core-Foo-cs`); it must be unique per file and match the `href` in the file index.

```html
<details class="file" id="f-{slug}" open>
  <summary class="filename">
    <span class="path">path/to/file.ext</span>
    <span class="counts"><span class="add">+12</span><span class="del">−3</span></span>
  </summary>

  <div class="mode-unified">
    <div class="diff" style="counter-reset: old 9 new 13;">
      <div class="row ctx"><span class="num old"></span><span class="num new"></span><span class="code">unchanged line before</span></div>
      <div class="row del"><span class="num old"></span><span class="num new"></span><span class="code">removed line</span></div>
      <div class="row add"><span class="num old"></span><span class="num new"></span><span class="code">added line</span></div>
      <div class="row ctx"><span class="num old"></span><span class="num new"></span><span class="code">unchanged line after</span></div>
    </div>
  </div>

  <div class="mode-split">
    <div class="split">
      <div class="side" style="counter-reset: n 9;">
        <div class="side-body">
          <div class="sheader">Before</div>
          <div class="srow ctx"><span class="num"></span><span class="code">unchanged line before</span></div>
          <div class="srow del"><span class="num"></span><span class="code">removed line</span></div>
          <div class="srow blank"><span class="num"></span><span class="code"> </span></div>
          <div class="srow ctx"><span class="num"></span><span class="code">unchanged line after</span></div>
        </div>
      </div>
      <div class="side" style="counter-reset: n 13;">
        <div class="side-body">
          <div class="sheader">After</div>
          <div class="srow ctx"><span class="num"></span><span class="code">unchanged line before</span></div>
          <div class="srow blank"><span class="num"></span><span class="code"> </span></div>
          <div class="srow add"><span class="num"></span><span class="code">added line</span></div>
          <div class="srow ctx"><span class="num"></span><span class="code">unchanged line after</span></div>
        </div>
      </div>
    </div>
  </div>
</details>
```

The numbers in this example (`9` for unified `old`, `13` for unified `new`, and the corresponding split-side resets) assume the hunk starts at old line 10 / new line 14. Substitute the actual values you computed.

Rules:

1. **Counter start.** The `counter-reset` value must be a **literal integer you compute** — not a placeholder, not an expression, CSS will not evaluate `N-1`. Each counter starts one below the first row's number.
   - **Unified `.diff`:** `counter-reset: old {old-start - 1} new {new-start - 1};`. For a hunk beginning at old line 10 / new line 14, write `counter-reset: old 9 new 13;`.
   - **Split sides:** each `.side` has its own single counter `n`. The two sides usually start at different numbers — Before tracks the old file, After tracks the new file. Before: `counter-reset: n {old-start - 1};`. After: `counter-reset: n {new-start - 1};`.
   - **Whole-file view starting at line 1:** use `0` for each counter (or omit `counter-reset` — defaults to 0).
2. **Context lines.** Default to hunk mode with ~3 lines of `ctx` before and after each change. Whole-file view (every line as `ctx`/`add`/`del`) is appropriate only when (a) the file is new — every line is `add`; (b) the file is deleted — every line is `del`; or (c) the file is short (≤30 lines) and the user benefits from full context. For everything else, hunk mode keeps the HTML lean.
3. **Split alignment.** Pad the shorter side with `srow blank` rows so common anchors (function signatures, closing `}`) line up visually between Before and After. Blank rows don't advance the counter.
4. **One block per file.** If a file has multiple distant changes, still emit one unified `.diff` for it (with all hunks) and one split table for it. Use multiple `<div class="row hunk">` separators inside the unified block if desired, or just include all lines.
5. **HTML-escape code content.** In the text body of `<span class="code">`: escape `<` → `&lt;`, `>` → `&gt;`, `&` → `&amp;`. Inside attribute values: additionally escape `"` → `&quot;` and `'` → `&#39;`. The optional syntax-hint wrappers (`<span class="k">`, `s`, `c`) are emitted as **raw HTML** — only the text content inside those spans is escaped, not the span tags themselves.
6. **Preserve indentation.** Whitespace is preserved via `white-space: pre` on `.row` / `.srow`. Just write the raw whitespace inside `<span class="code">`.
7. **New file.** Every line is `row add`. Add `<div class="note"><strong>New file.</strong></div>` *before* the `<details>` block (so it stays visible when collapsed).
8. **Deleted file.** Every line is `row del`. Add `<div class="note"><strong>Deleted.</strong></div>` *before* the `<details>` block.
9. **Renamed file.** Add `<div class="note"><strong>Renamed from <code>old/path</code> → <code>new/path</code>.</strong></div>` *before* the `<details>` block.
10. **Per-file stat counts.** Inside each `<summary class="filename">`, emit `<span class="counts"><span class="add">+X</span><span class="del">−Y</span></span>` where X = count of `row add` lines and Y = count of `row del` lines you emit for that file. For a pure new file, X = total lines added, Y = 0. For a pure delete, vice versa. If you sourced from `git diff --numstat`, those numbers are columns 1 and 2.
11. **Image files (`.png`, `.jpg`, `.jpeg`, `.gif`, `.webp`, `.svg`).** Render a side-by-side before/after preview instead of a diff. Inside the `<details class="file">`, replace `.mode-unified` and `.mode-split` with a single `<div class="image-diff">` block:
    ```html
    <div class="image-diff">
      <figure>
        <figcaption>Before</figcaption>
        <img src="data:image/png;base64,..." alt="path/to/image.png (old)">
      </figure>
      <figure>
        <figcaption>After</figcaption>
        <img src="data:image/png;base64,..." alt="path/to/image.png (new)">
      </figure>
    </div>
    ```
    To get both versions self-contained: run `git show HEAD:path/to/image.png | base64` for the old version, `base64 path/to/image.png` for the new. Embed each as a `data:` URI so the HTML stays standalone. For new images (no old version): omit the Before figure. For SVGs: prefer inline `<svg>` over `<img data:>` for crisper rendering. If the image is larger than ~1 MB, skip the embed and link to the file path instead (`<a href="path/to/image.png">`) — the HTML balloons fast otherwise.
12. **Other binary or generated files.** Skip the diff blocks and emit a `<p>` prose note inside `<div class="note">` *only* for genuinely non-reviewable files: lockfiles, autogenerated code (e.g., `*.g.cs`, `*.designer.cs`), large data dumps, fonts, audio. Size alone is **not** a reason to skip — a 500-line C# refactor still gets a real diff. If the file is hand-written source, show the diff.

## Syntax hinting (optional)

The template includes tiny CSS for three classes you can use inside `<span class="code">`:

- `<span class="k">keyword</span>` — keywords (red/pink)
- `<span class="s">"string"</span>` — strings (blue)
- `<span class="c">// comment</span>` — comments (grey italic)

Use sparingly — only for the most visually important tokens. Full syntax highlighting is not a goal.

## Gathering the changes

- **Prefer `git diff` when the changes already exist on disk.** If the working directory is a git repo with modifications, source the diffs verbatim:
  - `git status --short` — see which files are touched (and which are staged vs. unstaged vs. untracked).
  - `git diff` (unstaged) and `git diff --cached` (staged) — full hunks with line numbers in `@@ -old,len +new,len @@` headers. These give you exact counter-reset values for free.
  - `git diff --numstat` — per-file additions/deletions for the stat counts.
  - `git diff --stat` — total additions/deletions for `STATS_TOTAL`.
  This is the fastest, most truthful path. No reconstruction, no fabrication risk.
- If the user has already described the changes in the conversation, use that context.
- If edits were staged in your head but not applied, derive the diff from the target file's current content (use Read) and the intended result.
- If `$ARGUMENTS` describes a new feature, work out what files need to change, read them, and produce realistic diffs.
- Never fabricate content from files you haven't read. If you don't know current content, Read it first.

## No file-list rollups — ever

The same principle applies at the file level. The preview must show every changed file as its own diff block. Forbidden patterns:

- A trailing section titled "Остальные N файлов (суммарно)", "Other N files (summary)", "Bulk changes", or anything similar that lists files with prose bullets instead of real `<div class="mode-unified">` / `<div class="mode-split">` diff blocks.
- A bulleted list inside the diff area describing "what changed in each file" instead of showing the change.
- "+ N more files…" or "etc." truncation markers.

If you cannot produce real diffs for every file in the PR — because there are too many, or because reading them all is impractical — stop and tell the user before writing the HTML. Ask whether to:

- (a) narrow the scope of `$ARGUMENTS` to a subset of files,
- (b) split the preview into multiple HTML files (`PR-1.html`, `PR-2.html`, …),
- (c) proceed with a long single HTML containing every diff (will take time).

Never silently rollup. The reviewer opened the preview to see code, not prose.

## No placeholders in diff lines — ever

The preview is shown to a human reviewer who reads the green/red lines as the **actual code that will be written**. Anything that summarises or abbreviates code instead of being that code is a bug.

Forbidden inside `<span class="code">`:

- Ellipses standing in for code: `(...)`, `Foo(...)`, `{ ... }`, `// ...`, `/* ... */`.
- Symmetry / "same as" handwaves: `/* симметрично X */`, `/* same as Foo */`, `// mirror of X`, `// analogous to Y`, `// see Foo above`.
- Resume-style fake comments that replace omitted code: `// GroupByConfigId / TryDequeueMatch — private helpers`, `// helpers below`, `// other methods unchanged`, `// rest of class`, `// + 5 more fields`.
- Stub method bodies that hide the real body: `public T Foo() { /* body */ }`, `=> /* impl */`.
- Any phrase like "above", "below", "elsewhere", "as before", "similarly", "etc." used to skip code.

Rule of thumb: if a real reviewer copy-pasted your diff into the file, the file must compile and behave exactly as intended. If your line contains `...` or a comment describing what code *would* go there, you're hand-waving — go back and write the actual code.

How to handle scope honestly:

- **Method too long to fully show?** Show the parts that changed plus the standard ~3 lines of `row ctx` around each hunk, exactly like a real diff. Don't insert a "rest of method unchanged" comment — just stop emitting rows; the gutter line numbers already convey the gap.
- **Many similar methods?** If the user truly wants all of them, write them all out in full. If they're noise, omit them from the diff entirely (don't list them as a fake comment). The `<!-- SUMMARY -->` or `<!-- CHANGES -->` sections are where you describe scope in prose — not the diff body.
- **A symmetric counterpart method?** Write its full body. "Symmetric to X" is not code; the reviewer needs to see the actual symmetric implementation to verify it's correct.

The only comments that may appear inside a diff line are comments that are **literally part of the source code being added or removed** in that file.

## Self-check before announcing success

After writing the HTML, **grep your own output** for forbidden patterns. If any match, fix the file and write again. Do **not** print a success message until the check passes.

- `grep -nE '\.\.\.' PR.html` — three dots. Inspect each: legitimate spread/rest operators in source (`params object[] args` is fine) vs. lazy abbreviation in a diff line (`Foo(...)` is not).
- `grep -niE '(симметрично|same as|mirror of|analogous|see (Foo|above|below)|rest of|other [0-9]+ files|N more|etc\.)' PR.html` — every match is almost certainly a placeholder you snuck in.
- `grep -cE '<div class="row' PR.html` vs. expected total row count — if your diff blocks are empty (`<div class="diff">` with no row children), you wrote a summary instead of code.

These three checks catch the recurring bugs (placeholders inside code, rollup blocks, empty diffs) without you having to re-read the whole file.

## After writing

1. **Open the file in the user's default browser.** Run the OS-appropriate command (best-effort — if it fails, ignore and continue):
   - **Windows:** `cmd /c start "" "PR.html"` (the empty `""` is the title arg required by `start`).
   - **macOS:** `open PR.html`.
   - **Linux / WSL:** `xdg-open PR.html` (or `wslview PR.html` under WSL).

   Quote the path. If the path contains spaces or non-ASCII characters, double-quote it. Don't block waiting for the browser — fire and forget.

2. **Print a one-line confirmation** with the absolute output path so the user can re-open later. If the auto-open command failed (non-zero exit), say so and suggest double-clicking the file.

3. **Mention the toggles** at the top — Unified/Split switches the diff layout, "Soft-wrap long lines" wraps long rows instead of horizontal-scrolling. Line numbers are CSS-generated, so dragging across the code and copying will paste only the code, not the numbers. Printing the page auto-expands all collapsed files.

See `PR-example.html` in the skill directory for a working, filled-in reference.

Write in the same language the user used for $ARGUMENTS.
