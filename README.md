# Kensei Claude Plugins

Claude Code plugin marketplace: a statusline and a skill toolkit for tracker tasks, diff review,
design brainstorms, Unity review and end-of-session capture. Release notes are in [CHANGELOG.md](CHANGELOG.md).

## Installation

```bash
claude plugin marketplace add KenseiTheOne/kensei-claude-plugins
claude plugin install kensei-toolkit@kensei-claude-plugins
claude plugin install kensei-statusline@kensei-claude-plugins
```

Inside a session the same works as `/plugin marketplace add …` and `/plugin install …`.

**Requirements:** `python3` (3.9 or newer) on `PATH`. The ticket guard, diff-tour and the
statusline are Python scripts; without `python3` the guard cannot run and does not block anything.

## Plugins

| Plugin | Description |
|--------|-------------|
| [kensei-toolkit](plugins/kensei-toolkit/) | Tracker task runner with a publish guard, annotated diff tour, design brainstorm, Unity code review, session learnings and loose ends |
| [kensei-statusline](plugins/kensei-statusline/) | Multi-line statusline: model, context, tokens, cost, usage limits (incl. per-model ones like Fable), subagents, git, project stats |

Versions live in each plugin's `.claude-plugin/plugin.json`; the CHANGELOG lists what each one changed.

**Invocation** says who can start a skill: *manual* — only you, by typing the command; *model* —
Claude also picks it on its own when your request matches the skill's description. Every skill
answers in the language you write in.

### kensei-toolkit

| Skill | Command | Invocation | Example | What it does |
|-------|---------|------------|---------|--------------|
| [ticket](plugins/kensei-toolkit/skills/ticket/) | `/kensei-toolkit:ticket <url\|id> [probe\|fix\|full]` | manual, model | «возьми тикет CU-86c1234, режим fix» | Runs one tracker task end to end: context agent, acceptance criteria you approve, implementation, tests, fresh-agent review, then a publish gate. Commit, merge into main, push, PR, task comment, status, task creation, releases and repository settings happen only on your command (typed, or an answer tagged such as `[merge-local]`, `[create-task]`, `[publish]`, `[repo-admin]`), enforced by a guard hook that also covers subagents; a comment is fact-checked and shown in full before posting. Any tracker via MCP, CLI or browser |
| [diff-tour](plugins/kensei-toolkit/skills/diff-tour/) | `/kensei-toolkit:diff-tour [ref\|a..b]` | manual, model | «покажи дифф» | Self-review before a commit: the changes (untracked files included) as a local HTML page, side by side or unified, with notes on what and why placed under the lines they explain; every change no note explains is marked "Unexplained". Read-only: the git index and the repository are never touched |
| [brainstorm](plugins/kensei-toolkit/skills/brainstorm/) | `/kensei-toolkit:brainstorm [topic]` | manual, model (on an explicit ask) | «давай побрейнштормим, как устроить офлайн-кэш» | Design dialogue before implementation: focused questions, honest challenge, approaches, incremental validation. Ends with a design doc and a standalone plan, saved outside the project (`~/docs/brainstorms` unless the project names a place); implementation starts only when you say so |
| [unity-review](plugins/kensei-toolkit/skills/unity-review/) | `/kensei-toolkit:unity-review [quick\|perf\|arch\|full] [paths\|ref\|a..b] [focus]` | manual, model | «проверь на перф» | Unity-specialist review of a change through four lenses (performance, memory and lifecycle, Unity architecture, platform), checked against the project's real platforms and packages. Read-only reviewers; a fresh agent tries to refute every finding; the report lists confirmed findings by severity with `path:line` and a failure scenario. Generic bugs and style are left to `/code-review`. In a project with its own review skill, a general review goes to that skill; a lens you name that it lacks (such as performance) runs here |
| [learn](plugins/kensei-toolkit/skills/learn/) | `/kensei-toolkit:learn [path/to/CLAUDE.md\|focus]` | manual | — | End of session: proposes durable takeaways, deduplicated against the project and global `CLAUDE.md` and the auto-memory, each routed to one of them; writes only what you tick |
| [todo](plugins/kensei-toolkit/skills/todo/) | `/kensei-toolkit:todo [path/to/notes.md\|focus]` | manual | — | End of session: collects loose ends with evidence and, for the ones you tick, adds personal items to the Todoist Inbox (or prints a paste block) and project work to the ClickUp list you pick (the workspace comes from your project rules or `CLAUDE.md`, otherwise it asks); with a `.md` path, appends to that file instead |

The toolkit also ships a `PreToolUse` hook ([hooks/hooks.json](plugins/kensei-toolkit/hooks/hooks.json))
that applies the ticket guard to subagents while `/kensei-toolkit:ticket` is active.

### kensei-statusline

| Skill | Command | Invocation | Example | What it does |
|-------|---------|------------|---------|--------------|
| [setup](plugins/kensei-statusline/skills/setup/) | `/kensei-statusline:setup` | manual, model | «настрой статуслайн» | Installs the statusline wrapper and sets `statusLine` in `settings.json`, keeping your other settings and backing the file up first |

A `SessionStart` hook ([hooks/hooks.json](plugins/kensei-statusline/hooks/hooks.json)) asks Claude
to *offer* setup when no statusline is configured yet; nothing changes until you agree. See the
[statusline README](plugins/kensei-statusline/README.md) for the display and the usage-limit fetch.

## Structure

```
.claude-plugin/marketplace.json            — marketplace manifest (plugin list, no versions)
.github/workflows/ci.yml                   — script tests + claude plugin validate
CHANGELOG.md                               — release notes for both plugins
plugins/kensei-toolkit/
  .claude-plugin/plugin.json               — manifest, version
  hooks/hooks.json                         — subagent guard while a ticket run is active
  skills/ticket/                           — SKILL.md, flow.md, publish.md, trackers.md,
                                             guard.py + guard_test.py
  skills/diff-tour/                        — SKILL.md, difftour.py + difftour_test.py
  skills/brainstorm/                       — SKILL.md
  skills/unity-review/                     — SKILL.md, lenses.md (read by the reviewer agents)
  skills/learn/, skills/todo/              — SKILL.md
  evals/                                   — behavioural cases for claude plugin eval
plugins/kensei-statusline/
  .claude-plugin/plugin.json               — manifest, version
  hooks/hooks.json                         — SessionStart: offer setup once
  scripts/                                 — statusline.py, wrapper, setup-check.py, statusline_test.py
  skills/setup/                            — SKILL.md, setup.py
```

## Development

This clone (`~/Projects/IT/kensei-claude-plugins`) is the source of truth. The copies under
`~/.claude/plugins/` belong to Claude Code: edits there are overwritten on the next update and leave
the installed version number lying about its contents, so they are never edited by hand.

**Edit and try.** Change files here and load the plugin straight from the clone:

```bash
claude --plugin-dir ~/Projects/IT/kensei-claude-plugins/plugins/kensei-toolkit
```

A `/kensei-toolkit:ticket` session started this way treats the clone's `skills/ticket/` and
`hooks/` as its own guard and refuses to edit them. To change the guard through `/ticket`, start
that session on the installed plugin instead.

**Release.**

1. Tests and validation pass:
   ```bash
   python3 plugins/kensei-toolkit/skills/ticket/guard_test.py
   python3 plugins/kensei-toolkit/skills/diff-tour/difftour_test.py
   python3 plugins/kensei-statusline/scripts/statusline_test.py
   claude plugin validate --strict . && claude plugin validate --strict plugins/kensei-toolkit \
     && claude plugin validate --strict plugins/kensei-statusline
   ```
   CI also parses every skill and eval frontmatter as strict YAML, which `validate` does not.
2. After a skill change, run the evals on Opus (they cost real model calls, see
   [evals/README.md](plugins/kensei-toolkit/evals/README.md)).
3. Bump `version` in the plugin's `plugin.json` (semver; removing a skill is a major bump) and add a
   `CHANGELOG.md` entry.
4. Commit, push, then tag: `claude plugin tag plugins/<plugin> --push` creates
   `<plugin>--v<version>` and checks that the manifests agree.

**Install the release.** Only through Claude Code:

```bash
claude plugin marketplace update kensei-claude-plugins
claude plugin update kensei-toolkit@kensei-claude-plugins
claude plugin update kensei-statusline@kensei-claude-plugins
```

Then restart long-lived sessions: a running session keeps the plugin copy it started with. When a
skill behaves oddly, first check which copy that session actually loaded: look for the `.in_use`
marker under `~/.claude/plugins/cache/kensei-claude-plugins/<plugin>/<version>/` (look, never edit),
or the plugin path the session itself reports. `claude plugin list` shows only the installed
version, not what a running session holds.

CI ([ci.yml](.github/workflows/ci.yml)) runs the three test scripts on Linux and macOS and
`claude plugin validate --strict` on pushes to `main`, on tags and on pull requests; evals are not
run in CI.
