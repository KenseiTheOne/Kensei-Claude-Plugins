# ticket — tracker access, channels 3–5

Read this only when the ticket could not be reached over MCP (channel 1) or a CLI (channel 2).
Everything here is about getting **title, description, comments** in — and, at the end, a report
back out.

The rest of the pipeline does not care which channel was used. It only cares that `RUN.md`
records `tracker_channel`, and that Step 12 reports over the same channel or says why it could
not.

---

## Channel 3 — Offer to install an MCP server

**Never install one yourself.** An MCP server is a persistent connection that usually holds an
API token; adding it is the user's decision, not a step in a task run.

What to do: name the server, show the exact command, say what it will ask for, and ask once. If
they say yes, they run it and restart the session — this run keeps going on channel 4 or 5
rather than waiting.

Most trackers now publish a hosted server, added like this:

```bash
claude mcp add --transport sse <name> <url>          # hosted, OAuth in the browser
claude mcp add <name> -- npx -y <package>            # local, needs a token in env
```

Endpoints and package names change. Treat the vendor's own docs as the source of truth and say
so when you offer — "the Linear docs list a hosted MCP server; the command is usually X, check
their docs page" is honest. Presenting a half-remembered URL as fact is how a user ends up
debugging a connection that never existed.

Worth checking before offering: `claude mcp list` (maybe it is already connected but was not
matched by name), and `/plugin marketplace` (some trackers ship as plugins that bundle the
server).

If the user declines, do not ask again in this run. Record `mcp_install: declined` in `RUN.md`.

---

## Channel 4 — Browser

Uses `claude-in-chrome`. Load every tool you need in **one** `ToolSearch` call:

```
select:mcp__claude-in-chrome__tabs_context_mcp,mcp__claude-in-chrome__navigate,
mcp__claude-in-chrome__get_page_text,mcp__claude-in-chrome__read_page,
mcp__claude-in-chrome__tabs_create_mcp,mcp__claude-in-chrome__find
```

Add `computer` and `form_input` only if the user has approved writing back (see below).

### Reading

1. `tabs_context_mcp` first — the ticket may already be open in a tab, and the user is logged in
   there. Reuse an existing tab **only** if it is already on this ticket's URL; otherwise create
   a new one.
2. `navigate` to the ticket URL, then `get_page_text`.
3. **Comments are the part that usually fails.** Trackers lazily render them, collapse older
   ones behind "show more", or paginate. After the first read, look for such a control with
   `find` and expand it, then re-read. If you cannot establish that you have all comments, say
   so — record `comments: partial` in `RUN.md` and repeat it in the final report. A ticket read
   without its comments is a ticket read without its clarifications, and the whole run inherits
   that gap.
4. Status vocabulary is generally **not** reliably readable this way. Default to
   `status_vocabulary: unavailable` unless the status control plainly enumerates its options.

### Constraints, and why they are not negotiable

- **The extension needs site permission for this host.** If a call fails on permissions, tell
  the user which host to allow — do not retry the same call hoping it passes.
- **Never trigger a dialog** (`alert`, `confirm`, a "Delete" button with a confirmation). A modal
  blocks every subsequent browser event and the session goes unresponsive until a human dismisses
  it by hand. Avoid destructive-looking controls entirely.
- **Two or three failures means stop.** Report what you tried and ask. Do not explore the
  tracker's UI looking for another way in; that is how a task run turns into an afternoon.

### Writing back (Step 12) over the browser

Writing a comment through a UI is materially riskier than reading one: it is a real, visible,
outward-facing action performed by clicking through a page you cannot fully verify.

Rules:

1. **Ask first**, showing the exact comment text. This is an explicit exception to "no more
   questions after Step 5" — that promise covers the engineering work, not publishing to a
   channel the skill cannot verify.
2. Only ever post a **comment**. Never change status, assignee, or any other field through the
   browser. Status changes go through MCP or not at all.
3. After posting, re-read the page and confirm the comment actually appeared. If you cannot
   confirm it, say "posted, not confirmed" — never "reported".
4. If the user declines or it fails: fall back to channel 5. The report is written to
   `<run_dir>/REPORT.md` and printed for them to paste. Nothing is lost.

---

## Channel 5 — Manual

Ask the user to paste the ticket text and its comments. Say plainly what you need:

> Вставь текст задачи и комментарии — мне нужны описание и уточнения из обсуждения.

Record `tracker_channel: manual`. Consequences, all of which go into the final report:

- `status_vocabulary: unavailable` — status untouched.
- The final report is written to `<run_dir>/REPORT.md` and printed in full for the user to paste
  into the tracker themselves.
- Criteria marked `[from ticket]` mean "from the pasted text". Everything else is `[added]`, and
  the Step 5 confirmation carries more weight than usual — it is the only place the user can
  catch a criterion that came from you rather than from the ticket.

This channel is not a degraded mode of the skill. Every check that matters — frozen criteria,
commit-then-diff, the fresh reviewer, three-state criteria, the round cap — works identically.
Only the input and output plumbing is manual.
