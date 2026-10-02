# codex-img — maintainer notes

Not loaded by the skill; `SKILL.md` is what the model reads.

## Why a skill with a script, not an MCP server

The images come from the user's ChatGPT subscription, and the only dependable way to reach the
subscription's image tool is `codex exec`. Given that, the shape follows from three facts:

- **Calls are long.** One image takes ~50–90 s, a series tens of minutes. An MCP tool call blocks
  Claude for all of that and cannot run in the background. A script run through Bash can: a
  series goes out with `run_in_background`, Claude keeps working and is notified when it ends.
- **The client is Claude Code only.** An MCP server's main advantage — working in any client,
  Claude Desktop included — was not needed, and Codex's own `codex mcp-server` is gone as of
  0.159.3, so an MCP would only add a server layer around the same `codex exec` call. The skill
  ships with the plugin and updates with `claude plugin update`; nothing to install or configure.
- **The work splits into code and judgement.** Everything deterministic is in `codex_img.py`:
  building the command, finding the image by `thread_id`, copying it without overwriting,
  checking alpha, detecting limits, killing the process tree, Windows quirks. Everything that
  needs judgement is in `SKILL.md`: writing the prompt, looking at every result, when to retry,
  confirming the cost of a series, not generating an image nobody asked for. A skill without
  the script would trip over the deterministic parts on every call; a script without the skill
  would not know how to be used. The skill is also loaded only when images come up, while an MCP
  server's tools sit in the context all the time.

Rejected on the way: an MCP on the OpenAI Images API (the only route to GPT Image 2.5
Flare/Sunburst by name, masks and quality, but it needs API billing on top of the
subscription), driving ChatGPT in a browser (fragile), and calling Codex's private endpoints with
its OAuth tokens (a ToS grey zone). If the API route is ever wanted, it is a separate tool, not
an extension of this one.

## Files

- `codex_img.py` — `gen` (one image) and `batch` (a manifest). Stdlib only, Python 3.9+. Prints
  one JSON object; exit codes are in the module docstring.
- `codex_img_test.py` — run `python3 codex_img_test.py` (~25 s). A fake `codex` (a Python script,
  wrapped in a `.cmd` on Windows) prints canned `--json` events and drops PNGs into a temporary
  `CODEX_HOME`; the real Codex is never called, so the tests spend no quota. `FAKE_MODE` picks
  the scenario (refusal, limit, hang, half-written image, …).

## Things that are easy to break

- The prompt goes to `codex exec` on **stdin**: a positional prompt after `-i` is swallowed, and
  on Windows `codex.cmd` routes arguments through cmd.exe.
- `--skip-git-repo-check`, `-s read-only`, `-c approval_policy=never` and `--ephemeral` are all
  needed; the tests assert them because the fake would not notice them missing.
- Codex runs in its own process group so a timeout can kill the whole tree — which also means
  signals to the script do not reach it; `run_process` passes them on.
- `--resume` trusts only `<manifest>.codex-img-state.json`, never a file that merely exists at
  `out`: that file may be the user's own.
- After a Codex update, check live that the image still lands in
  `$CODEX_HOME/generated_images/<thread_id>/` and that `thread.started` is still the first event.
