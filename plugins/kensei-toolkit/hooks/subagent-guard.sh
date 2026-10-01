#!/bin/sh
# ticket guard for subagents (plugin PreToolUse hook).
#
# In a session where /kensei-toolkit:ticket is active, subagents may not commit, push or write to
# the tracker. skills/ticket/guard.py decides; this wrapper only keeps Python from starting for
# the calls it can never concern, because the hook fires on every matched tool call of every
# session:
#   - a main-session call (no "agent_id" in the payload) — the skill's own hook covers those;
#   - a session that never ran /ticket (no marker in <runs root>/.guard/<session_id>; the runs
#     root is $KENSEI_TASK_RUNS_DIR or ~/.claude/task-runs, resolved as guard.py's TASK_RUNS;
#     a ~user/… root is left to guard.py);
#   - a plugin copy without guard.py.
# Everything else goes to guard.py --subagent, whose JSON answer is passed through unchanged.

input=$(cat)
case "$input" in
  *'"agent_id"'*) ;;
  *) exit 0 ;;
esac
guard="$(dirname "$0")/../skills/ticket/guard.py"
[ -f "$guard" ] || exit 0
# the first "session_id" is the payload's own; a later one may sit in tool_input
session=$(printf '%s' "$input" |
  grep -o '"session_id"[[:space:]]*:[[:space:]]*"[A-Za-z0-9_-]*"' | head -n 1 |
  sed 's/.*"\([A-Za-z0-9_-]*\)"$/\1/')
runs=${KENSEI_TASK_RUNS_DIR:-$HOME/.claude/task-runs}
case $runs in
  "~" | "~/"*) runs="$HOME${runs#"~"}" ;;
  "~"*) runs= ;;
esac
[ -z "$runs" ] || { [ -n "$session" ] && [ -f "$runs/.guard/$session" ]; } || exit 0
printf '%s' "$input" | python3 "$guard" --subagent
