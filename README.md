# Kensei Claude Plugins

Claude Code plugin marketplace.

## Installation

```bash
/plugin marketplace add KenseiTheOne/Kensei-Claude-Plugins
```

Then install any plugin:

```bash
/plugin install <plugin-name>@kensei-claude-plugins
```

## Plugins

| Plugin | Description |
|--------|-------------|
| [kensei-statusline](plugins/kensei-statusline/) | Multi-line statusline: model, context, tokens, API cost, usage limits, subagents, git info, project stats |
| [kensei-toolkit](plugins/kensei-toolkit/) | Skill collection — Unity review, session learn, todo capture, brainstorm, and more to come |

### kensei-statusline

| Skill | Command | Description |
|-------|---------|-------------|
| [setup](plugins/kensei-statusline/skills/setup/) | `/kensei-statusline:setup` | Configure the statusline in `~/.claude/settings.json` |

A `SessionStart` hook auto-runs setup once when the plugin is first installed.

### kensei-toolkit

| Skill | Command | Description |
|-------|---------|-------------|
| [unity-review](plugins/kensei-toolkit/skills/unity-review/) | `/kensei-toolkit:unity-review` | Senior+ Unity code review (6 agents, 4 modes) |
| [learn](plugins/kensei-toolkit/skills/learn/) | `/kensei-toolkit:learn` | Mine the current session and propose additions to project `CLAUDE.md` |
| [todo](plugins/kensei-toolkit/skills/todo/) | `/kensei-toolkit:todo` | Capture session loose ends into `TODO.md` (bugs, follow-ups, open questions) |
| [brainstorm](plugins/kensei-toolkit/skills/brainstorm/) | `/kensei-toolkit:brainstorm` | Collaborative design dialogue before implementation — questions, challenge, approach exploration |

## Structure

```
.claude-plugin/                          — Marketplace manifest
plugins/kensei-statusline/               — Statusline plugin (hook + setup skill)
plugins/kensei-toolkit/skills/           — Skill collection (unity-review, ...)
```
