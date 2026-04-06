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
| [kensei-statusline](plugins/kensei-statusline/) | Two-line statusline: model, context, tokens, API cost, subagents, git info |

## Structure

```
.claude-plugin/       — Marketplace manifest
plugins/              — Plugin packages
skills/               — Standalone skills
```
