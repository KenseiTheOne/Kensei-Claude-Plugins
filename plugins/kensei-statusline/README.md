# Kensei Statusline

Two-line Claude Code statusline with model info, tokens, cost, subagents, and git status.

## Display

```
Opus │ ▓▓▓▓░░░░░░ 42% │ ↑380.0K ↓62.0K │ ~$10.3 │ 3 agents (Sonnetx2, Opus)
main │ ●2 +3 ?1 │ +310 -45 │ 12 files 1.2K loc
```

**Line 1:**
- **Model** — current model name
- **Context bar** — green (<50%), yellow (50-80%), red (>80%)
- **↑ / ↓** — current context input tokens / cumulative output tokens
- **~$X.XX** — estimated Anthropic API cost
- **N agents** — active subagents grouped by model

**Line 2:**
- **Branch** — current git branch (bold blue)
- **●/+/?** — staged (green) / modified (yellow) / untracked (dim)
- **⇡/⇣** — commits ahead/behind remote
- **+N -N** — lines added/removed in session
- **N files N loc** — project size

## Requirements

- Python 3.8+

## Installation

```bash
/plugin marketplace add KenseiTheOne/Kensei-Claude-Plugins
/plugin install kensei-statusline@kensei-claude-plugins
```

On first session after install, a `SessionStart` hook runs `/kensei-statusline:setup` automatically — it writes a wrapper to `~/.claude/scripts/kensei-statusline.py` and patches `~/.claude/settings.json`. Restart Claude Code (`/exit`) for the statusline to take effect.

To re-run setup manually (e.g. after editing `settings.json`):

```bash
/kensei-statusline:setup
```

### Why a wrapper?

The plugin cache path includes a version (`~/.claude/plugins/cache/kensei-claude-plugins/kensei-statusline/<version>/...`), so a hardcoded path would break on every update. The wrapper resolves the latest cached version dynamically.

## API Pricing

Estimates cost using Anthropic API rates (per 1M tokens):

| Model  | Input  | Output | Cache Write | Cache Read |
|--------|--------|--------|-------------|------------|
| Opus   | $15.00 | $75.00 | $18.75      | $1.875     |
| Sonnet | $3.00  | $15.00 | $3.75       | $0.375     |
| Haiku  | $1.00  | $5.00  | $1.25       | $0.10      |

If Claude Code reports `cost.total_cost_usd`, that value is used directly.
