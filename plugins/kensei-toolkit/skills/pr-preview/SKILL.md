---
name: pr-preview
description: Render proposed changes as a Pull Request preview in a markdown file with red/green diff highlighting, like on GitHub. Use when the user wants to review changes before applying them, or wants a PR-style summary of a set of edits.
disable-model-invocation: true
argument-hint: [task description | path to save PR.md]
---

Produce a Pull Request–style markdown document describing the changes for: $ARGUMENTS

**Do not modify any source files.** This skill is a preview — it writes only one file: the PR markdown.

## Output file

- Default path: `PR.md` in the current working directory.
- If `$ARGUMENTS` ends with `.md` and looks like a path, treat it as the output path and infer the task from conversation context.
- If the file already exists, overwrite it.

## Required structure

```markdown
# <concise PR title>

## Summary
<1–3 sentences: what changes and why>

## Changes
<bulleted list of what's being done, grouped by file or by logical change>

## Files changed
<for each file, a section with a diff block — see format below>

## Test plan
<bulleted checklist of how to verify the change>

## Notes
<optional: risks, follow-ups, open questions — omit section if empty>
```

## Diff block format

For every modified file use a fenced block with the `diff` language tag so GitHub-flavored markdown renders `-` lines in red and `+` lines in green:

````markdown
### `path/to/file.ext`

```diff
@@ <short location hint, e.g. function name or line range> @@
 unchanged context line
- removed line
+ added line
 unchanged context line
```
````

Rules for the diff blocks:
1. Show **3 lines of unchanged context** before and after each change, prefixed with a single space (` `), exactly like unified diff.
2. Removed lines start with `-` (no space after).
3. Added lines start with `+` (no space after).
4. Preserve original indentation **after** the `+`/`-`/` ` marker.
5. Use a `@@ ... @@` hunk header with a human-readable location (function name, section, or line range) — it does not need to be a real line-number header.
6. For **new files**: show the whole content as `+` lines and add `**New file.**` above the block.
7. For **deleted files**: show the whole content as `-` lines and add `**Deleted.**` above the block.
8. For **renames**: note `**Renamed from `old/path` → `new/path`.**` above the diff.
9. If a file is binary or too large (>200 changed lines), summarize in prose instead of pasting the full diff.

## Gathering the changes

- If the user has already described the changes in the conversation, use that context.
- If edits were staged in your head but not applied, derive the diff from the target file's current content (use Read) and the intended result.
- If `$ARGUMENTS` describes a new feature, work out what files need to change, read them, and produce realistic diffs — don't hand-wave with `...`.
- Never fabricate content from files you haven't read. If you don't know current content, Read it first.

## After writing

Print a one-line confirmation with the output path, and suggest the user open it in a markdown preview that supports GitHub-style syntax highlighting (e.g. VS Code preview) to see the red/green coloring.

Write in the same language the user used for $ARGUMENTS.
