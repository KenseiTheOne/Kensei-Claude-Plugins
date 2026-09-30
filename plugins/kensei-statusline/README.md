# Kensei Statusline

Multi-line Claude Code statusline with model info, tokens, cost, usage limits, subagents, and git status.

## Display

```
Opus │ ▓▓▓▓░░░░░░ 42% │ ↑380.0K ↓62.0K │ ~$10.3 │ 3 agents (Sonnetx2, Opus)
5h 24% ↻ 18:00 · 7d 41% ↻ 16.06 · Fable 11% ↻ 28.09
main │ ●2 +3 ?1 │ +310 -45 │ 12 files 1.2K loc
```

**Line 1:**
- **Model** — current model name
- **Context bar** — green (<50%), yellow (50-80%), red (>80%)
- **↑ / ↓** — current context input tokens / cumulative output tokens
- **~$X.XX** — estimated Anthropic API cost
- **N agents** — active subagents grouped by model

**Line 2 (usage limits):**
- **5h / 7d** — subscription usage windows with reset time (`↻ HH:MM` for 5-hour, `↻ DD.MM` for weekly), same color thresholds as the context bar. Shown only on Claude Pro/Max — Claude Code sends `rate_limits` after the first API response of the session
- **Per-model and other meters** (e.g. a separate weekly **Fable** limit) — every other row of the claude.ai usage endpoint that `/usage` shows, labelled and ordered as the server sends them and coloured up by its severity. Claude Code does not pass these to statuslines, so the script fetches them itself: a detached background process calls `GET https://api.anthropic.com/api/oauth/usage` with Claude Code's own OAuth access token (macOS keychain item `Claude Code-credentials`, per profile under `CLAUDE_CONFIG_DIR`, or `.credentials.json` in the config dir) at most every 3 minutes, with backoff after errors, and caches only the rows in `<config dir>/cache/kensei-statusline/usage.json`. Rendering never waits on the network. The token is never refreshed, logged or stored; an expired one is skipped until Claude Code renews it. API-key sessions make no request. Set `KENSEI_STATUSLINE_NO_USAGE_FETCH=1` to turn the fetch off

**Line 3:**
- **Branch** — current git branch (bold blue)
- **●/+/?** — staged (green) / modified (yellow) / untracked (dim)
- **⇡/⇣** — commits ahead/behind remote
- **+N -N** — lines added/removed in session
- **N files N loc** — project size

## Requirements

- Python 3.8+

## Installation

```bash
/plugin marketplace add KenseiTheOne/kensei-claude-plugins
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
