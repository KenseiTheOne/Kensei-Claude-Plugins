---
name: unity-review
description: Unity-specialist code review of a change — parallel read-only reviewers look through Unity lenses (performance, memory and lifecycle, Unity architecture, platform), a fresh agent tries to refute every finding, and the confirmed ones are reported by severity with file:line and a failure scenario. Modes — quick, perf, arch, full. Scope — uncommitted work with untracked files, given paths, or a ref or range. Use when the user asks for a Unity review — "unity review", "review this for performance", «юнити-ревью», «проверь на перф», «ревью по юнити». Generic bug-hunting and code style belong to /code-review; inside a project with its own review skill (such as pw-review), that skill is the main review and this one adds the Unity lenses it lacks.
argument-hint: "[quick|perf|arch|full] [paths | ref | a..b] [focus]"
---

# unity-review — Unity lenses on a change

This review looks only at what a Unity specialist sees and a generic reviewer misses: frame cost,
object and asset lifecycle, serialization and engine semantics, platform limits. Generic
bug-hunting, naming and code style are `/code-review`'s job; run it alongside when wanted.

The whole skill is read-only. It reports; fixing anything is a separate request from the user.

Talk to the user in the user's language: the mode question, progress lines and the report. The
agent prompts may stay in English.

Files of this skill:

- this file — Steps 1–7;
- `lenses.md` — the checklist for each lens; reviewer agents read their own section of it, so
  you do not need to load it yourself.

## Step 1 — Read the arguments

`$ARGUMENTS` may hold a mode, a scope and a focus, in any order.

- **Mode** — `quick`, `perf`, `arch` or `full` (also `performance`, `architecture`). A mode
  named in words in the request counts as given, in any language: performance, frame cost,
  allocations, GC or memory («проверь на перф», «по памяти») mean `perf`; architecture or
  platform mean `arch`; a full or thorough review means `full`; a quick look means `quick`.
  Only when neither the arguments nor the request name one, ask once with `AskUserQuestion`
  (header "Mode") at the end of Step 3, when the file count is known: offer the four modes with
  the lenses each runs, from the table below, and mark `quick` as recommended for up to ~15
  files and `full` for more.
- **Scope** — file or directory paths, a ref, or a range `a..b` / `a...b`. A token that is an
  existing path is a path; otherwise it is a ref when
  `git rev-parse --verify --quiet '<token>^{commit}'` succeeds.
- **Focus** — anything else is free-form instruction for the reviewers ("focus on the inventory
  UI") — pass it on.

| Mode | Reviewers (one agent per lens) |
|---|---|
| `quick` | one agent covering all four lenses, reporting only Critical and Warning |
| `perf` | Performance, Memory & lifecycle |
| `arch` | Unity architecture, Platform |
| `full` | Performance, Memory & lifecycle, Unity architecture, Platform |

## Step 2 — Respect a project review skill

Look for a project-local review skill: `.claude/skills/*review*/SKILL.md` at the repository root
(PerfectWar, for example, has `pw-review`, which checks code against the project's architecture
decisions, specs and contracts, and has no performance check). When one exists, read its
description and categories to see which of the four Unity lenses it already covers. A lens
counts as covered only when the project skill checks that Unity concern itself: categories about
the project's own domain or architecture lifecycles (pw-review's "lifecycle NFE", "lifecycle
Meta") do not cover Memory & lifecycle, which is about Unity object and asset lifetime, GC, and
event and handle leaks. Then:

- if the user typed `/unity-review` themselves, run the requested mode as usual;
- if you picked this skill on your own and the request names Performance, Memory & lifecycle or
  Platform and the project skill lacks it («проверь на перф» in PerfectWar), run only the named
  lenses the project skill lacks — a request about performance may take both Performance and
  Memory & lifecycle, but never adds Unity architecture — and say in one line that `<name>` is
  the project's main review and this run adds only those lenses (name them);
- if you picked this skill on your own for a general review, for architecture alone when the
  project skill has an architecture category, or every named lens is one the project skill
  covers, use the project skill instead and stop here.

## Step 3 — Collect the scope

All git here is read-only. Run it from the repository root (`git rev-parse --show-toplevel`),
so every path — the file list here and `path:line` in findings later — is relative to the
repository root, whatever the session's working directory.

- **No scope argument:** `git diff HEAD --name-only` plus
  `git ls-files --others --exclude-standard` (new files are part of the change). When both are
  empty, the tree is clean: find the default branch (`git symbolic-ref --short
  refs/remotes/origin/HEAD`, else `main`, else `master`) and take
  `git diff --name-only $(git merge-base HEAD <default>)..HEAD`, and say that you did. If that
  diff is empty too, there is nothing to review — say so and stop.
- **Paths:** those files; a directory means the matching files under it.
- **A ref:** `git diff --name-only $(git merge-base HEAD <ref>)` (the branch's own work plus
  uncommitted changes), plus untracked files.
- **A range:** `git diff --name-only a..b` (or `a...b`), no working tree.

Keep these files (deleted files drop out, but note deleted `.cs` files for Step 5):

- `.cs`, `.asmdef`, `.asmref`;
- `.uxml`, `.uss`, `.tss`;
- `.shader`, `.hlsl`, `.cginc`, `.compute`;
- `.asset`, `.prefab`, `.unity`, `.meta` — these are reviewed only for serialized references
  (renamed fields, missing scripts, changed GUIDs), never read in full.

Serialized references are checked against the whole project, not only the scope: renaming a
field or deleting a script breaks prefabs and scenes that the change never touched, so reviewers
grep all of `Assets/` (and embedded packages) for the affected GUIDs and field names.

Find the Unity project root: the directory that holds both `Assets/` and `ProjectSettings/` —
the repository root or a subdirectory (PerfectWar's is `Client/PerfectWar`). When there are
several, take the one containing the scope files. No Unity project or no kept files: say this
skill has nothing to review here, suggest `/code-review`, and stop.

When more than ~60 files remain, tell the user the count and the largest directories and ask
whether to review all of them or narrow the scope — in the same `AskUserQuestion` call as the
mode question when that one is due.

## Step 4 — Detect the project context

Read the project's facts once and give them to every agent, so reviewers check what the project
actually uses instead of guessing. Write "Unknown" for anything you cannot find; never fail on a
missing file. Paths are under the Unity project root.

- **Unity version** — `ProjectSettings/ProjectVersion.txt`.
- **Render pipeline** — `com.unity.render-pipelines.universal` / `.high-definition` in
  `Packages/manifest.json`, else Built-in.
- **Target platforms** — build profiles (`*.asset` files under a `Build Profiles` folder in
  `Assets/`), and the platform keys of the per-platform maps in
  `ProjectSettings/ProjectSettings.asset` (`scriptingBackend`, `il2cppCompilerConfiguration`),
  which list only platforms someone configured. Platform-named fields that every
  `ProjectSettings.asset` carries by default (`AndroidMinSdkVersion`, `iPhoneTargetOSVersion`,
  `m_BuildTarget` entries in icon tables) say nothing about targets. `EditorBuildSettings.asset`
  lists only scenes. When the signals disagree or are absent, write the candidates with
  "(unconfirmed)".
- **Scripting backend** — the per-platform `scriptingBackend` map in `ProjectSettings.asset`
  (1 = IL2CPP, 0 = Mono), for the target platforms.
- **Domain reload** — `m_EnterPlayModeOptions` in `ProjectSettings/EditorSettings.asset`:
  reload is off when the value has the DisableDomainReload flag (value 1, so the value is odd).
  On Unity versions before 6 also require `m_EnterPlayModeOptionsEnabled: 1`; Unity 6 no longer
  reads that field, so its value there means nothing.
- **Packages in use** — from `Packages/manifest.json`, `Packages/packages-lock.json` and
  embedded packages: Entities, Burst, Collections, Jobs, Netcode, Addressables, Input System,
  UI Toolkit, uGUI, UniTask, a DI container (VContainer, Zenject). Burst and Jobs count as used
  when any project `.asmdef` references `Unity.Burst` / `Unity.Jobs` / `Unity.Collections`, or
  project code has `[BurstCompile]` or `IJob*` — a package in the manifest alone is not use.
  Note which assemblies use them: a scope file inherits Burst/Jobs relevance from the `.asmdef`
  that owns it (the nearest one up the tree), even when the file itself has no Burst code.

Format as one line, e.g.
`Unity 6000.3.13f1 | URP | Android (IL2CPP), Standalone (Mono) | domain reload off | Entities, Burst, Addressables, UI Toolkit`.

## Step 5 — Run the reviewers

Spawn the mode's agents in parallel (only the lenses Step 2 kept), `subagent_type:
general-purpose`, model inherited from the session. That agent type can write, so the read-only
rule lives in the prompt below as a list of the tools it may use; keep it there verbatim. Each
prompt carries: the repository root (where to run git) and the Unity project root, the file list
from Step 3 (with deleted `.cs` files marked), how to get the diff (`git diff HEAD -- <file>` for
uncommitted work, or the ref or range command; untracked files are read whole), the context line
from Step 4, the focus if any, the agent's lens names, and this frame:

```
You are a senior Unity engineer reviewing one change through the lens(es): <lenses>.
Read your lens section(s) in <skill dir>/lenses.md first.

You are read-only. The tools you may call are exactly these:
- Read, Grep, Glob, and ToolSearch only to load the Unity MCP tools below;
- Bash for read-only commands only: git diff (without --output), git log, git show,
  git ls-files, git rev-parse, git merge-base, git grep, git blame, git status, git cat-file,
  and grep, find (without -delete or -exec), ls, cat, head, tail, wc, sed -n;
- Unity MCP tools (mcp__<server>__<name>) whose <name> starts with get_, find_, list_ or
  read_, plus ping and status.
Every other tool is outside this review, whatever it does (opening a scene, running a menu
item or a method, saving, compiling, entering play mode). If you need what only such a tool
would show, say so in your report instead of calling it.

Review the changed lines, and read whatever else you need to judge them: callers, overrides,
the systems that schedule this code, related prefabs and UXML. A finding must be about code
the change adds or modifies, or about existing code whose behaviour the change breaks.

Check what the project actually uses (context line, asmdefs, usings) before any finding that
depends on it; never suggest adopting a technology the project does not use.

Report at most 15 findings, most severe first. For each:
- severity: Critical | Warning | Suggestion (definitions in lenses.md);
- lens;
- location: path:line (path relative to the repository root, as in the file list);
- problem: one or two sentences;
- failure scenario: the concrete situation in which it goes wrong and what the player or
  developer sees (for example "each enemy spawn allocates a 1 KB closure in Update; with
  200 enemies on Android this is ~200 KB/frame of GC");
- fix: the smallest change that removes it.
A finding without a location and a concrete failure scenario is not a finding — drop it.
If nothing qualifies, say "No findings" and list what you checked.
```

In `quick` mode the single agent gets all four lens names and reports Critical and Warning only.

## Step 6 — Verify the findings

Merge the reviewers' findings and remove duplicates (same location and cause; keep the more
specific scenario and note both lenses). Then spawn one fresh `general-purpose` agent with the
context line, the file list, every finding, and this task prefixed with the read-only paragraph
of the Step 5 frame ("You are read-only. …" through "… instead of calling it."), verbatim:

```
Try to refute each finding. Open the code at the cited location and around it, follow callers
and the project facts it relies on. A finding is refuted when the cited line does not do what
it claims, the failure scenario cannot happen (the path is not hot, the event is unsubscribed
elsewhere, the platform is not a target, the package is not used), or the issue predates the
change and the change does not make it worse. For each finding answer: confirmed | refuted |
uncertain, with one line of evidence (path:line). Adjust severity if the scenario is real but
smaller or larger than claimed.
```

Keep confirmed findings, list uncertain ones separately, and drop refuted ones (count them).

## Step 7 — Report

In the user's language, in the chat:

1. Header: mode, scope (what was diffed against what, number of files), the context line.
2. Findings grouped **Critical**, **Warning**, **Suggestion** (localise the headings); each
   with `path:line`, lens, problem, failure scenario, fix. Omit empty groups.
3. **Unconfirmed** — the uncertain findings, with the verifier's doubt in one line.
4. One closing line: how many findings the verifier refuted, which lenses ran, and that generic
   bugs and style were not reviewed here (`/code-review` covers them).

No overall score. When nothing survived, say the change looks clean through these lenses and
name what was checked. Offer to fix specific findings; change nothing until the user asks.
