---
type: llm
focus: last_message
---

PASS if the proposals in the reply route the `PYTHONPATH=src` gotcha to the project `CLAUDE.md`
and the "reply in Russian" preference to a user-level destination (the global `CLAUDE.md` — under
`~/.claude/` or `$CLAUDE_CONFIG_DIR` — or the auto-memory), not to the project `CLAUDE.md`; and
`make test` is not proposed as a new, separate item. Amending the existing `make test` line with
the PYTHONPATH gotcha counts as routing the gotcha to the project `CLAUDE.md`, not as a duplicate.
FAIL if the language preference is routed to the project `CLAUDE.md`, the gotcha is missing, or
`make test` is proposed as a new line next to the one already there.
The language of the reply does not matter. Writes are checked by the no-writes and no-edits graders.
