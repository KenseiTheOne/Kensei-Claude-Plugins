# Kensei Claude Plugins

Claude Code plugin marketplace.

## Installation

```bash
/plugin marketplace add KenseiTheOne/kensei-claude-plugins
```

Then install any plugin:

```bash
/plugin install <plugin-name>@kensei-claude-plugins
```

## Plugins

| Plugin | Description |
|--------|-------------|
| [kensei-statusline](plugins/kensei-statusline/) | Multi-line statusline: model, context, tokens, API cost, usage limits (incl. per-model ones like Fable), subagents, git info, project stats |
| [kensei-toolkit](plugins/kensei-toolkit/) | Skill collection — tracker task runner, Unity review, annotated diff tour, session learn, todo capture, brainstorm |

### kensei-statusline

| Skill | Command | Description |
|-------|---------|-------------|
| [setup](plugins/kensei-statusline/skills/setup/) | `/kensei-statusline:setup` | Configure the statusline in `~/.claude/settings.json` |

A `SessionStart` hook auto-runs setup once when the plugin is first installed.

### kensei-toolkit

| Skill | Command | Description |
|-------|---------|-------------|
| [ticket](plugins/kensei-toolkit/skills/ticket/) | `/kensei-toolkit:ticket <url\|id>` | Run one tracker task end-to-end — context, criteria, implement, test, review. Commit, push, comment and status only on your command — enforced by a hook; comments are fact-checked and approved word for word before posting. Any tracker via MCP, CLI or browser. `--unattended` runs it headless for an external runner that publishes the result |
| [diff-tour](plugins/kensei-toolkit/skills/diff-tour/) | `/kensei-toolkit:diff-tour [ref\|a..b]` | Self-review before a commit — the uncommitted diff (untracked included) as a local HTML page, file by file, side by side or unified, with notes on what and why from the conversation placed under the lines they explain; every change no note explains is marked "Unexplained". Code reaches the page only through a script, the git index is never touched |
| [unity-review](plugins/kensei-toolkit/skills/unity-review/) | `/kensei-toolkit:unity-review` | Senior+ Unity code review (6 agents, 4 modes) |
| [learn](plugins/kensei-toolkit/skills/learn/) | `/kensei-toolkit:learn` | Mine the current session and propose additions to project `CLAUDE.md` |
| [todo](plugins/kensei-toolkit/skills/todo/) | `/kensei-toolkit:todo` | Capture session loose ends into `TODO.md` (bugs, follow-ups, open questions) |
| [brainstorm](plugins/kensei-toolkit/skills/brainstorm/) | `/kensei-toolkit:brainstorm` | Collaborative design dialogue before implementation — questions, challenge, approach exploration |

## Structure

```
.claude-plugin/                          — Marketplace manifest
plugins/kensei-statusline/               — Statusline plugin (hook + setup skill)
plugins/kensei-toolkit/skills/           — Skill collection (ticket, unity-review, ...)
```
