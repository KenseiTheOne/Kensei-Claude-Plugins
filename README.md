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
| [statusline](plugins/statusline/) | Two-line statusline: model, context, tokens, API cost, subagents, git info |
| [toolkit](plugins/toolkit/) | Skill collection — Unity review, and more to come |

### toolkit

| Skill | Command | Description |
|-------|---------|-------------|
| [unity-review](plugins/toolkit/skills/unity-review/) | `/toolkit:unity-review` | Senior+ Unity code review (6 agents, 4 modes) |

## Structure

```
.claude-plugin/                 — Marketplace manifest
plugins/statusline/             — Statusline plugin (hooks)
plugins/toolkit/skills/         — Skill collection (unity-review, ...)
```
