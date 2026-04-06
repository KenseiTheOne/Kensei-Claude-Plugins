# Kensei Statusline

Claude Code statusline showing model, context usage, tokens, and estimated API cost.

## Display

```
Opus │ ▓▓▓░░░░░░░ 32% │ ↑185.4K ↓24.3K │ ~$4.40
```

- **Model** — current model name
- **Context bar** — green (<50%), yellow (50-80%), red (>80%)
- **↑ / ↓** — input / output tokens for the session
- **~$X.XX** — estimated Anthropic API cost (uses reported cost or calculates from token counts)

## Requirements

- Python 3.8+

## Installation

Add to `~/.claude/settings.json`:

```json
{
  "statusLine": {
    "type": "command",
    "command": "python \"/path/to/kensei-statusline/statusline.py\""
  }
}
```

## Pricing

Calculates cost using Anthropic API rates (per 1M tokens):

| Model  | Input  | Output | Cache Write | Cache Read |
|--------|--------|--------|-------------|------------|
| Opus   | $15.00 | $75.00 | $18.75      | $1.875     |
| Sonnet | $3.00  | $15.00 | $3.75       | $0.375     |
| Haiku  | $1.00  | $5.00  | $1.25       | $0.10      |

If Claude Code reports `cost.total_cost_usd`, that value is used directly.
Otherwise, cost is calculated from session token counts.
