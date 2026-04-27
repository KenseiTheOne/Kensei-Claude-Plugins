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
- If the file already exists, overwrite it.

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
| `<!-- FILES -->` | For each changed file: one `.mode-unified` block and one `.mode-split` block (see below) |
| `<!-- TESTS -->` | `<li>` items with `<input type="checkbox">` — how to verify |
| `<!-- NOTES_SECTION -->` | `<h2>Notes</h2>` + `<ul>` if there are risks/follow-ups; omit entirely if none |

## Row classes (this is the core)

Every code line inside a diff is a `<div class="row …">`. The class controls colour **and** line-number increment:

- `row ctx` — unchanged context line. Increments both old and new counters. No background.
- `row add` — added line. Increments only `new`. Green background. Old gutter column stays blank.
- `row del` — removed line. Increments only `old`. Red background. New gutter column stays blank.

You do **not** write the line numbers yourself — CSS counters do it. Just use the right row class and order.

## Structure for one file (both modes)

For each changed file, emit both unified and split markup back-to-back. The toggle hides one at a time.

```html
<div class="mode-unified">
  <div class="filename">path/to/file.ext</div>
  <div class="diff" style="counter-reset: old N new M;">
    <div class="row ctx"><span class="num old"></span><span class="num new"></span><span class="code">unchanged line before</span></div>
    <div class="row del"><span class="num old"></span><span class="num new"></span><span class="code">removed line</span></div>
    <div class="row add"><span class="num old"></span><span class="num new"></span><span class="code">added line</span></div>
    <div class="row ctx"><span class="num old"></span><span class="num new"></span><span class="code">unchanged line after</span></div>
  </div>
</div>

<div class="mode-split">
  <div class="filename">path/to/file.ext</div>
  <div class="split">
    <div class="side" style="counter-reset: n N-1;">
      <div class="side-body">
        <div class="sheader">Before</div>
        <div class="srow ctx"><span class="num"></span><span class="code">unchanged line before</span></div>
        <div class="srow del"><span class="num"></span><span class="code">removed line</span></div>
        <div class="srow blank"><span class="num"></span><span class="code"> </span></div>
        <div class="srow ctx"><span class="num"></span><span class="code">unchanged line after</span></div>
      </div>
    </div>
    <div class="side" style="counter-reset: n N-1;">
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
```

Rules:

1. **Counter start.** `counter-reset: old N new M` on `.diff` sets line numbers so the first row displays (N+1, M+1). For a hunk that begins at line 4 of both files, use `old 3 new 3`. For whole-file view starting at line 1, use `old 0 new 0` (or omit).
2. **Context lines.** Show ~3 lines of `ctx` before and after each change. For whole-file view, include everything.
3. **Split alignment.** Pad the shorter side with `srow blank` rows so common anchors (function signatures, closing `}`) line up visually between Before and After. Blank rows don't advance the counter.
4. **One block per file.** If a file has multiple distant changes, still emit one unified `.diff` for it (with all hunks) and one split table for it. Use multiple `<div class="row hunk">` separators inside the unified block if desired, or just include all lines.
5. **HTML-escape** code content: `<` → `&lt;`, `>` → `&gt;`, `&` → `&amp;`, `"` → `&quot;` when inside attributes.
6. **Preserve indentation.** Whitespace is preserved via `white-space: pre` on `.row` / `.srow`. Just write the raw whitespace inside `<span class="code">`.
7. **New file.** Every line is `row add`. Add `<div class="note"><strong>New file.</strong></div>` above the filename.
8. **Deleted file.** Every line is `row del`. Add `<div class="note"><strong>Deleted.</strong></div>` above the filename.
9. **Renamed file.** Add `<div class="note"><strong>Renamed from <code>old/path</code> → <code>new/path</code>.</strong></div>` above the filename.
10. **Binary / huge files (>200 changed lines).** Skip the diff blocks entirely; emit a single `<p>` prose summary inside a plain `<div class="note">`.

## Syntax hinting (optional)

The template includes tiny CSS for three classes you can use inside `<span class="code">`:

- `<span class="k">keyword</span>` — keywords (red/pink)
- `<span class="s">"string"</span>` — strings (blue)
- `<span class="c">// comment</span>` — comments (grey italic)

Use sparingly — only for the most visually important tokens. Full syntax highlighting is not a goal.

## Gathering the changes

- If the user has already described the changes in the conversation, use that context.
- If edits were staged in your head but not applied, derive the diff from the target file's current content (use Read) and the intended result.
- If `$ARGUMENTS` describes a new feature, work out what files need to change, read them, and produce realistic diffs — don't hand-wave with `...`.
- Never fabricate content from files you haven't read. If you don't know current content, Read it first.

## After writing

Print a one-line confirmation with the output path, and suggest the user open the file in a browser (double-click). The `<style>` block is embedded, so no extra files are needed — the HTML is fully self-contained.

Also mention: the view toggle at the top switches all diffs between **Unified** and **Split** with one click. Line numbers are CSS-generated — dragging across the code and copying will paste only the code, not the numbers.

See `PR-example.html` in the skill directory for a working, filled-in reference.

Write in the same language the user used for $ARGUMENTS.
