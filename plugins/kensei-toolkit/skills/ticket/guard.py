#!/usr/bin/env python3
"""ticket guard — PreToolUse hook registered by the /kensei-toolkit:ticket skill.

Blocks, in code, what the skill may only do on the user's explicit command:

  commit       git commit / merge / rebase / cherry-pick / revert / am (history-writing)
  push         git push to a non-base branch, gh release, GitHub/GitLab MCP file/branch pushes
  pr           opening a PR / MR (gh pr create, create_pull_request, api POST …/pulls)
  merge        merging a PR / MR (gh pr merge, merge_pull_request, api …/merge)
  force        a push that rewrites or targets the base branch: --force*, --delete, --mirror,
               +refspec, main/master (named, or the current branch when none is named)
  history      git pull, reset --hard/--soft or to a commit, update-ref, branch -D/-f, stash drop
  tracker      a status change or any other write to a tracker (MCP tool, gh issue/api, curl)
  destructive  deleting a task / issue / page, merging tasks
  delete       deleting a tracker comment
  comment      posting or editing a tracker comment — only text the user approved word for word
  tamper       touching this session's transcript or the guard's markers — never allowed

A command comes from the session transcript, read back to the latest message the user typed
(origin.kind == "human"; a message queued while the model was busy counts too):

  typed text     conservative: imperatives such as «закоммить», «запушь», «переведи в ревью»,
                 negation scoped to its list item, conditional or cancelled sentences dropped
  AskUserQuestion answers after that message: an option the user picked grants exactly the tags
                 in its label — [commit] [push] [pr] [merge] [force-push] [reset] [status]
                 [delete-task] [delete-comment]; [post] approves the option's `preview` as the
                 comment text, if the preview was shown in full

A command is used up by the call it authorized: one commit, one push, one status write — and one
call may not carry the same action twice. A comment text that was
posted cannot be posted again. When the model invoked /ticket itself, what the user typed before
that does not count.

Two registrations, because a skill's frontmatter hooks do not reach its subagents (measured):

  guard.py --main      SKILL.md frontmatter; the main session once /ticket is invoked. Marks the
                       session as a ticket session, then checks the command.
  guard.py --subagent  plugin hooks/hooks.json; its sh wrapper runs this only for subagent calls
                       (`agent_id` set) in a marked session. Subagents are refused every gated
                       action — only the orchestrator commits, pushes or writes to the tracker.

Output: nothing when the call is not gated or is authorized — the normal permission flow
continues, the hook never grants anything. A JSON "deny" with the reason otherwise. Internal
errors fail closed for calls that look gated.
"""

import json
import os
import re
import shlex
import subprocess
import sys

# --- classification tables ----------------------------------------------------------------

TRACKER_SERVER = re.compile(
    r"clickup|jira|atlassian|confluence|linear|github|gitlab|youtrack|asana|notion|trello|"
    r"monday|shortcut|taiga|plane", re.I)
GIT_SERVER = re.compile(r"^git$|git[-_]?mcp|^mcp[-_]?git$", re.I)
READ_WORDS = {
    "get", "list", "search", "find", "filter", "read", "fetch", "view", "query", "download",
    "export", "describe", "show", "lookup", "check", "count", "schema", "operators", "hierarchy",
    "members", "authenticate", "authentication", "whoami", "me", "info", "diff", "log",
}
WRITE_WORDS = {
    "create", "update", "delete", "add", "remove", "move", "merge", "set", "attach", "upload",
    "start", "stop", "assign", "unassign", "close", "reopen", "edit", "post", "send",
    "transition", "link", "unlink", "archive", "request", "execute", "mark", "tag", "untag",
    "push", "fork", "star", "dismiss", "approve", "submit", "rerun", "cancel", "trigger",
    "reply", "resolve", "write", "rename", "transfer", "lock", "unlock", "pin", "unpin",
}
COMMENT_WORDS = {"comment", "comments", "message", "messages", "chat", "reply", "note", "notes",
                 "story"}
TEXT_KEYS = re.compile(r"comment|body|text|content|message|markdown", re.I)

GIT_HISTORY = {"commit", "merge", "rebase", "cherry-pick", "revert", "am", "commit-tree"}
NON_WRITING = {"--abort", "--quit", "--dry-run", "--no-commit", "--show-current-patch",
               "--edit-todo"}
BASE_BRANCHES = {"main", "master", "develop", "dev", "trunk", "release"}
GIT_BUILTINS = {
    "add", "am", "apply", "archive", "bisect", "blame", "branch", "bundle", "cat-file",
    "check-ignore", "checkout", "cherry", "cherry-pick", "clean", "clone", "commit",
    "commit-tree", "config", "count-objects", "describe", "diff", "diff-files", "diff-index",
    "diff-tree", "difftool", "fetch", "for-each-ref", "format-patch", "fsck", "gc", "grep",
    "hash-object", "help", "hook", "init", "lfs", "log", "ls-files", "ls-remote", "ls-tree",
    "maintenance", "merge", "merge-base", "mergetool", "mv", "name-rev", "notes", "prune",
    "pull", "push", "range-diff", "read-tree", "rebase", "reflog", "remote", "repack",
    "replace", "reset", "restore", "rev-list", "rev-parse", "revert", "rm", "shortlog", "show",
    "show-ref", "sparse-checkout", "stash", "status", "submodule", "subtree", "switch",
    "symbolic-ref", "tag", "update-index", "update-ref", "var", "version", "whatchanged",
    "worktree", "write-tree",
}
GIT_OPTS_WITH_VALUE = {"-C", "-c", "--git-dir", "--work-tree", "--namespace", "--exec-path",
                       "--config-env", "--super-prefix"}
SHELLS = {"sh", "bash", "zsh", "dash", "ksh", "fish"}
SHELL_KEYWORDS = {"if", "then", "else", "elif", "fi", "do", "done", "while", "until", "case",
                  "esac", "{", "}", "!", "time", "coproc", "function", "select"}
WRAPPERS = {  # program -> options that take a value
    "command": set(), "builtin": set(), "nohup": set(), "exec": set(), "noglob": set(),
    "time": set(), "chronic": set(), "unbuffer": set(), "doas": {"-u"},
    "sudo": {"-u", "-g", "-C", "-h", "-p", "-U", "-r", "-t", "-D"},
    "caffeinate": {"-t", "-w"}, "nice": {"-n"}, "ionice": {"-c", "-n"}, "stdbuf": set(),
    "timeout": {"-s", "-k"}, "gtimeout": {"-s", "-k"}, "arch": set(),
    "xargs": {"-I", "-n", "-P", "-L", "-s", "-d", "-E", "-a"},
}
GITISH = re.compile(r"(?<![\w./-])(?:\S*/)?(git|gh)(?=\s)", re.I)

# --- reading what the user said -----------------------------------------------------------

NEG = re.compile(r"(?<![\w'])(?:не|ни|нет|без|нельзя|никогда|рано|стоп|don'?t|dont|do\s+not|"
                 r"not|never|no|nor|without|stop)(?![\w'])")
REMIND = re.compile(r"(?<![\w'])(?:не\s+забудь(?:те)?|don'?t\s+forget(?:\s+to)?)(?![\w'])")
DEFER = re.compile(r"(?<![\w'])(?:позже|попозже|later|after|после|не\s+сейчас|not\s+(?:yet|now))"
                   r"(?![\w'])")
TAIL = re.compile(r"(?:(?:пока|ещ[её]|только|just|only|but)\s+)*(?:не\s+(?:сейчас|сегодня|сразу|надо|"
                  r"нужно|стоит)|позже|попозже|later|not\s+(?:yet|now|today|right\s+now)|рано|"
                  r"пока\s+рано)")
PAIR = re.compile(r"(?<![\w/.-])(commit|push|коммит|пуш)\s*/\s*(?=(?:commit|push|коммит|пуш)\s*"
                  r"(?:please|pls|пожалуйста)?\s*(?:[,.;!?]|$))")
CANCEL = re.compile(r"(?<![\w'])(?:отмен\w*|cancel\w*|скип\w*|skip\w*|отбой|не\s+нужн\w*|"
                    r"not\s+needed)(?![\w'])")
COND = re.compile(r"(?<![\w'])(?:если(?!\s+что(?:[\s,—–-]|$))|когда|как\s+только|перед\s+тем\s+как|"
                  r"прежде\s+чем|if|when|once|unless|before|или|or)(?![\w'])")
POLITE = re.compile(r"(?<![\w'])(?:можешь|можете|сможешь|можно|please|pls|пожалуйста|"
                    r"could\s+you|can\s+you|would\s+you)(?![\w'])")
SPLIT = re.compile(r"\s*(?:[,;:—–&+]|\s-\s|(?<![\w'])(?:и|а|но|затем|потом|then|and|but)"
                   r"(?![\w']))\s*")
LEAD = re.compile(r"^(?:(?:ну|ок|окей|ok|okay|да|yes|yeah|yep|lgtm|давай|тогда|теперь|сейчас|"
                  r"now|so|go\s+ahead|go|just|also|ещ[её]|только|сразу|plz|pls|please|"
                  r"пожалуйста)\s+)+")
RU_IMPERATIVE = {
    "commit": r"(?:за)?комм?ит(?:ь|ни|ьте|ните)|(?:за|с)?мерж(?:и|ни)(?!\s+(?:\S+\s+)?"
              r"(?:пр|pr|пулл\w*|pull|mr|мр)\b)|ребейзни|засквошь|сквошни|(?:за)?амендь|амендни|"
              r"(?:сделай|сделайте|создай|оформи|собери|упакуй|схлопни)(?:\s+\S+){0,3}\s+коммит\w*",
    "push": r"(?:(?:за)?пуш(?:ь|ни|ьте|ните)|запуш)(?!\s+(?:в|на)\s+(?:main|master|develop|мастер|"
            r"мейн))|"
            r"залей(?:те)?(?:\s+\S+){0,2}\s+(?:на|в)\s+(?:ветк\w*|бранч\w*|origin|remote|ремоут|"
            r"гит|github|гитхаб)",
    "pr": r"(?:открой|создай|сделай|заведи)(?:\s+\S+)?\s+(?:пр|pr|пулл?-?реквест|pull\s+request|"
          r"мр|mr|merge\s+request)",
    "merge": r"(?:за|с)?мерж(?:и|ни)(?:\s+\S+)?\s+(?:пр|pr|пулл\w*|pull\s+request|mr|мр)",
    "force": r"форсни|(?:за)?форс-?пуш\w*|(?:за)?пуш\w*(?:\s+\S+)?\s+(?:в|на)\s+(?:main|master|"
             r"develop|мастер|мейн)",
    "history": r"сбрось|откати|подтяни|спулль",
    "tracker": r"(?:переведи|переведите|перекинь|перенеси|двинь|кинь|поставь)(?:\s+\S+){0,3}\s+"
               r"(?:в|на)\s+(?:\S+\s+)?(?:ревью|review|работу|progress|done|готово|qa|тест\w*|"
               r"closed|закрыт\w*)|(?:смени|поменяй|измени|обнови|поставь)(?:\s+\S+){0,2}\s+"
               r"статус\w*|(?:возьми|бери)(?:\s+\S+)?\s+в\s+работу|закрой(?:\s+\S+)?\s+"
               r"(?:задач\w*|тикет\w*|issue)|переоткрой\w*|назначь\w*|статус\s*(?:→|->)",
    "delete": r"(?:удали|сотри|снеси)(?:\s+(?:этот|тот|мой|свой|последний|предыдущий|старый|наш|"
              r"его))?\s+(?:коммент\w*|комментари\w*)"
              r"(?!(?:\s+\S+){0,2}\s+(?:в|из)\s+(?:код|файл))",
    "destructive": r"удали(?:\s+\S+){0,2}\s+(?:задач\w*|тикет\w*)",
}
RU_INFINITIVE = {  # only with a polite marker or «не забудь»
    "commit": r"(?:за)?комм?ит(?:ить|нуть)",
    "push": r"(?:за)?пуш(?:ить|нуть)",
    "tracker": r"перевести(?:\s+\S+){0,3}\s+(?:в|на)\s+(?:\S+\s+)?(?:ревью|review|работу|done)",
}
EN_TAIL = (r"(?=\s*$|\s+(?:it|this|that|them|these|those|the|all|my|your|everything|changes|now|"
           r"please|pls|plz|asap|already|to|with|--\S*)\b)")
EN_IMPERATIVE = {  # must start the list item
    "commit": r"(?:commit|amend|rebase|squash|cherry-?pick|revert|merge(?!\s+(?:the\s+)?"
              r"(?:pr|pull)))" + EN_TAIL,
    "push": r"push" + EN_TAIL,
    "pr": r"(?:open|create)\s+(?:a\s+|the\s+)?(?:pr|pull\s+request|mr|merge\s+request)",
    "merge": r"merge\s+(?:the\s+|this\s+)?(?:pr|pull\s+request)",
    "force": r"force[- ]?push",
    "history": r"(?:pull|reset)" + EN_TAIL,
    "tracker": r"(?:move|set|change|mark|close|reopen|assign)(?:\s+\S+){0,3}\s+(?:status|review|"
               r"done|task|issue|ticket|to\s+\S+)",
    "delete": r"(?:delete|remove)\s+(?:(?:the|that|this|my|last)\s+)*comment(?=\s*$|\s+(?:from|on|"
              r"in)\s+(?:the\s+)?(?:task|ticket|issue|tracker))",
    "destructive": r"delete\s+(?:the\s+|this\s+)?(?:task|issue|ticket)",
}
LITERAL = [(re.compile(r"\bgit\s+commit\b"), "commit"), (re.compile(r"\bgit\s+push\b"), "push"),
           (re.compile(r"\bgit\s+(?:pull|reset)\b"), "history"),
           (re.compile(r"\bgh\s+pr\s+create\b"), "pr"), (re.compile(r"\bgh\s+pr\s+merge\b"), "merge")]
SQUASH = re.compile(r"(?<![\w-])(?:засквошь|сквошни|схлопни|squash)(?![\w-])")
BARE = {"коммит": "commit", "commit": "commit", "пуш": "push", "push": "push"}
SEGMENT_STATUS = re.compile(r"^(?:\S+\s+)?(?:(?:probe|fix|full)\s+)?в\s+(?:ревью|review|работу)$")

TAGS = {"commit": "commit", "push": "push", "pr": "pr", "merge": "merge", "force-push": "force",
        "reset": "history", "status": "tracker", "delete-task": "destructive",
        "delete-comment": "delete"}
TAG_RE = re.compile(r"\[(commit|push|pr|merge|force-push|reset|status|delete-task|delete-comment|"
                    r"post)\]", re.I)
CONSUMED_BY_USE = {"commit", "push", "pr", "merge", "force", "history", "tracker", "destructive",
                   "delete"}


def normalize_text(s):
    return s.lower().replace("ё", "е")


def sentences(text):
    return [s for s in re.split(r"(?<=[.!?;])\s+|\n+", text) if s.strip()]


def detect(text):
    """Actions a typed message orders. Conservative: when in doubt, nothing."""
    text = PAIR.sub(r"\1, ", re.sub(r"\S+://\S+", " ", normalize_text(text)))
    found = set()
    for sent in sentences(text):
        if COND.search(sent) or CANCEL.search(sent):
            continue
        sent = re.sub(r"(?<![\w'])потом(?=\s*(?:[,.;!?]|$))", " позже", sent)
        added = set()
        question = sent.rstrip().endswith("?")
        polite = bool(POLITE.search(sent))
        sent_negative = bool(NEG.search(REMIND.sub(" ", sent)) or DEFER.search(sent))
        for raw in SPLIT.split(sent.strip(" .!?;")):
            seg = raw.strip(" .!?;\"'«»()")
            if not seg:
                continue
            remind = bool(REMIND.search(seg))
            seg_clean = REMIND.sub(" ", seg)
            if NEG.search(seg_clean) or DEFER.search(seg_clean):
                if TAIL.fullmatch(LEAD.sub("", seg_clean.strip()).strip()):
                    found -= added  # «запушь, но не сейчас»: the tail cancels the item before it
                added = set()
                continue
            before = set(found)
            core = LEAD.sub("", seg_clean.strip()).strip()
            for pattern, action in LITERAL:
                if pattern.search(core):
                    found.add(action)
            for action, pattern in RU_IMPERATIVE.items():
                if re.search(r"(?<![\w-])(?:" + pattern + r")(?![\w-])", core):
                    found.add(action)
            if polite or remind:
                for action, pattern in RU_INFINITIVE.items():
                    if re.search(r"(?<![\w-])(?:" + pattern + r")(?![\w-])", core):
                        found.add(action)
            for action, pattern in EN_IMPERATIVE.items():
                if re.match(r"(?:" + pattern + r")", core):
                    found.add(action)
            if SEGMENT_STATUS.match(core) and not question:
                found.add("tracker")
            if core in BARE and not question and not sent_negative:
                found.add(BARE[core])
            if "commit" in found - before and SQUASH.search(core):
                found.add("history")  # squashing several commits needs reset --soft
            added = found - before
    return found


def normalize_comment(s):
    s = s.replace("\r\n", "\n").strip()
    fence = re.match(r"^(`{3,}|~{3,})[^\n]*\n(.*)\n[ \t]*\1$", s, re.S)
    if fence:
        s = fence.group(2)
    lines = [ln.rstrip() for ln in s.split("\n")]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def split_multi(answer):
    """Picks of a multiSelect answer — the CLI joins them with ', ' and JSON-quotes any pick
    that contains ', ' or '"'."""
    items, i = [], 0
    while i < len(answer):
        if answer[i] == '"':
            try:
                value, end = json.JSONDecoder().raw_decode(answer, i)
                items.append(value)
                i = end
            except ValueError:
                items.append(answer[i:])
                break
        else:
            j = answer.find(", ", i)
            if j < 0:
                items.append(answer[i:])
                break
            items.append(answer[i:j])
            i = j
        if answer.startswith(", ", i):
            i += 2
    return items


# --- reading the transcript ---------------------------------------------------------------

def blocks_text(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(b.get("text", "") for b in content
                         if isinstance(b, dict) and b.get("type") == "text")
    return ""


def human_text(entry):
    if entry.get("type") == "attachment":
        text = blocks_text(entry["attachment"].get("prompt"))
    else:
        text = blocks_text(entry.get("message", {}).get("content"))
    if "<command-name>" in text:
        args = re.search(r"<command-args>(.*?)</command-args>", text, re.S)
        text = args.group(1) if args else ""
    return text


UNATTENDED = re.compile(r"(?<![\w-])--unattended(?![\w-])")
UNATTENDED_RUN = "an --unattended /ticket run"
TICKET_COMMAND = re.compile(r"<command-name>/?(?:[\w.-]+:)?ticket</command-name>")


def ticket_args(entry):
    """The arguments of a /ticket invocation carried by this entry, or None."""
    content = entry.get("message", {}).get("content")
    if entry.get("type") == "user":
        text = blocks_text(content)
        if TICKET_COMMAND.search(text):
            args = re.search(r"<command-args>(.*?)</command-args>", text, re.S)
            return args.group(1) if args else ""
    elif entry.get("type") == "assistant" and isinstance(content, list):
        for b in content:
            inp = b.get("input") or {} if isinstance(b, dict) else {}
            if (isinstance(b, dict) and b.get("type") == "tool_use" and b.get("name") == "Skill"
                    and re.search(r"(?:^|:)ticket$", str(inp.get("skill", "")))):
                return str(inp.get("args", ""))
    return None


def is_human(entry):
    if entry.get("isSidechain") or entry.get("isMeta"):
        return False
    if entry.get("type") == "user":
        origin = entry.get("origin")
        return isinstance(origin, dict) and origin.get("kind") == "human"
    if entry.get("type") == "attachment":
        att = entry.get("attachment") or {}
        origin = att.get("origin")
        return (att.get("type") == "queued_command" and att.get("commandMode", "prompt") == "prompt"
                and isinstance(origin, dict) and origin.get("kind") == "human")
    return False


def scan_back(transcript_path, max_bytes=64 << 20):
    """Return (human_entry or None, assistant/user entries after it in order, saw_origin,
    truncated)."""
    after, saw_origin, human = [], False, None
    with open(transcript_path, "rb") as f:
        f.seek(0, 2)
        pos = size = f.tell()
        tail = b""
        while pos > 0 and size - pos < max_bytes and human is None:
            step = min(1 << 20, pos)
            pos -= step
            f.seek(pos)
            lines = (f.read(step) + tail).split(b"\n")
            tail = lines[0] if pos > 0 else b""
            for raw in reversed(lines if pos == 0 else lines[1:]):
                if not raw.strip():
                    continue
                try:
                    entry = json.loads(raw)
                except ValueError:
                    continue
                if "origin" in entry or "origin" in (entry.get("attachment") or {}):
                    saw_origin = True
                if is_human(entry):
                    human = entry
                    break
                if entry.get("type") in {"assistant", "user"} and not entry.get("isSidechain"):
                    after.append(entry)
    after.reverse()
    return human, after, saw_origin, human is None and pos > 0


def executed(block):
    """Whether a tool result means the call ran: a call the guard denied, or one the user rejected
    or interrupted, did not run."""
    text = result_text(block).lstrip()
    if block.get("is_error") and "[ticket guard] Blocked" in text[:200]:
        return False
    return not text.startswith(("The user doesn't want to proceed", "[Request interrupted by user"))


def unprefix(text):
    return "\n".join(re.sub(r"^(?:[ \t]*>)*[ \t]*", "", ln) for ln in text.split("\n"))


def result_text(block):
    content = block.get("content")
    return blocks_text(content) if isinstance(content, list) else str(content or "")


def read_authorization(transcript_path, cwd):
    """Replay what happened since the user's latest message.

    Returns (human_text, actions, approved_comments, used_comments, unseen_comments, failure)."""
    if not transcript_path or not os.path.isfile(transcript_path):
        return None, set(), set(), set(), set(), "no transcript to read the user's command from"
    human, after, saw_origin, truncated = scan_back(transcript_path)
    # Nobody is there to give a command: whatever the transcript looks like, grant nothing.
    if any(UNATTENDED.search(args) for args in map(ticket_args, ([human] if human else []) + after)
           if args is not None):
        return None, set(), set(), set(), set(), UNATTENDED_RUN
    if human is None:
        if truncated:
            failure = "the user's latest message is beyond the guard's scan window"
        elif not saw_origin:
            failure = ("no message typed by the user was found — a headless or SDK prompt, or a "
                       "transcript format this guard does not know")
        else:
            failure = "no message typed by the user was found"
        if not after:
            return None, set(), set(), set(), set(), failure
    text = human_text(human) if human else None
    typed = detect(text) if text else set()
    actions = set(typed)
    approved, used, unseen = set(), set(), set()
    shown = unprefix(normalize_comment("\n".join(
        blocks_text(e["message"].get("content")) for e in after if e.get("type") == "assistant")))
    calls = {}
    for entry in after:
        content = entry.get("message", {}).get("content")
        if entry.get("type") == "assistant" and isinstance(content, list):
            for b in content:
                if isinstance(b, dict) and b.get("type") == "tool_use":
                    calls[b.get("id")] = b
                    if b.get("name") == "Skill" and re.search(
                            r"(?:^|:)ticket$", str((b.get("input") or {}).get("skill", ""))):
                        actions -= typed  # the model invoked /ticket: earlier typing is void
                        typed = set()
        elif entry.get("type") == "user" and isinstance(content, list):
            for b in content:
                if isinstance(b, dict) and b.get("type") == "tool_result":
                    call = calls.get(b.get("tool_use_id"))
                    if not call or not executed(b):
                        continue
                    for item in classify(call.get("name", ""), call.get("input") or {}, cwd):
                        if item[0] in CONSUMED_BY_USE:
                            actions.discard(item[0])
                        elif item[0] == "comment":
                            for t in comment_candidates(item):
                                used.add(normalize_comment(t))
                                approved.discard(normalize_comment(t))
            answer = entry.get("toolUseResult")
            if isinstance(answer, dict) and isinstance(answer.get("answers"), dict):
                granted, ok, missed = read_answers(answer, shown)
                actions |= granted
                approved |= ok
                unseen |= missed
    return text, actions, approved, used, unseen, (failure if human is None else None)


def read_answers(result, shown):
    if result.get("afkTimeoutMs") or result.get("followUp"):
        return set(), set(), set()
    granted, approved, unseen = set(), set(), set()
    questions = {q.get("question"): q for q in result.get("questions") or [] if isinstance(q, dict)}
    annotations = result.get("annotations") if isinstance(result.get("annotations"), dict) else {}
    for question, answer in result["answers"].items():
        if not isinstance(answer, str):
            continue
        q = questions.get(question) or {}
        options = {o.get("label"): o for o in q.get("options") or [] if isinstance(o, dict)}
        note = annotations.get(question) if isinstance(annotations.get(question), dict) else {}
        notes = note.get("notes")
        if isinstance(notes, str) and notes.strip():
            granted |= detect(notes)  # a pick with reservations grants nothing by itself
            continue
        picks = [answer] if answer in options or not q.get("multiSelect") else split_multi(answer)
        for pick in picks:
            option = options.get(pick)
            if option is None:
                granted |= detect(pick)  # free text the user typed ("Other")
                continue
            for tag in TAG_RE.findall(pick):
                tag = tag.lower()
                if tag in TAGS:
                    granted.add(TAGS[tag])
                    continue
                preview = option.get("preview")
                if not isinstance(preview, str) or not preview.strip():
                    continue
                norm = normalize_comment(preview)
                previews = [normalize_comment(o.get("preview") or "") for o in options.values()]
                seen = note.get("preview")
                displayed = (isinstance(seen, str) and normalize_comment(seen) == norm) \
                    or (bool(norm) and unprefix(norm) in shown)
                if previews.count(norm) == 1:
                    (approved if displayed else unseen).add(norm)
    return granted, approved, unseen


# --- what the tool call would do ----------------------------------------------------------

def strip_heredocs(command):
    """Remove heredoc bodies; return (command, bodies fed to a shell, all bodies)."""
    lines, out, fed, bodies = command.split("\n"), [], [], []
    i = 0
    while i < len(lines):
        line = lines[i]
        out.append(line)
        i += 1
        for m in re.finditer(r"<<(?!<)-?\s*(['\"]?)([^\s'\";&|()<>]+)\1", line):
            body, start = [], i
            while i < len(lines) and lines[i].strip() != m.group(2):
                body.append(lines[i])
                i += 1
            if i >= len(lines):  # never closed: keep the lines, they are still commands
                out.extend(lines[start:])
                break
            i += 1
            bodies.append("\n".join(body))
            before = re.split(r"[;&|(]", line[:m.start()])[-1].split()
            words = [os.path.basename(w).lower() for w in before if not re.match(r"^\w+=", w)]
            if words and words[0] in SHELLS and not any(
                    re.fullmatch(r"-[a-z]*c[a-z]*", w) for w in words[1:]):
                fed.append(bodies[-1])
    return "\n".join(out), fed, bodies


def split_segments(command):
    lexer = shlex.shlex(command.replace("\n", " ; "), posix=True, punctuation_chars=";&|()<>")
    lexer.whitespace_split = True
    lexer.commenters = ""
    segment, segments = [], []
    for token in lexer:
        if token and set(token) <= set(";&|()<>"):
            if segment:
                segments.append(segment)
            segment = []
        else:
            segment.append(token)
    if segment:
        segments.append(segment)
    return segments


def raw_scan(command, cwd, depth):
    """Conservative fallback: every git/gh word anywhere, parsed up to the next separator."""
    found = []
    for m in GITISH.finditer(command):
        rest = re.split(r"[;&|\n)`]", command[m.end():], 1)[0]
        args = rest.replace("'", " ").replace('"', " ").split()
        if m.group(1).lower() == "git":
            found += classify_git(args, cwd, depth + 1, {})
        else:
            found += classify_gh(args, cwd)
    return found


_GIT_CACHE = {}


def git_query(args, cwd, dash_c):
    key = (tuple(args), cwd, dash_c)
    if key not in _GIT_CACHE:
        cmd = ["git"] + (["-C", dash_c] if dash_c else []) + list(args)
        try:
            out = subprocess.run(cmd, cwd=cwd or None, capture_output=True, text=True, timeout=2)
            _GIT_CACHE[key] = out.stdout.strip() or None
        except (OSError, subprocess.SubprocessError):
            _GIT_CACHE[key] = None
    return _GIT_CACHE[key]


def git_alias(name, cwd, dash_c, inline):
    if name in inline:
        return inline[name]
    return git_query(["config", "--get", f"alias.{name}"], cwd, dash_c)


def push_kind(rest, cwd=None, dash_c=None):
    flags = [a for a in rest if a.startswith("-")]
    if {"--dry-run", "-n"} & set(flags):
        return None
    if any(f in {"-f", "--force", "--delete", "-d", "--mirror", "--prune"}
           or f.startswith(("--force-with-lease", "--force-if-includes")) for f in flags):
        return "force"
    positional = [a for a in rest if not a.startswith("-")]
    for spec in positional[1:]:
        dst = spec.split(":", 1)[-1]
        if spec.startswith(("+", ":")) or dst.replace("refs/heads/", "") in BASE_BRANCHES:
            return "force"
    if all(p in {"HEAD", "@"} for p in positional[1:]) and \
            git_query(["symbolic-ref", "-q", "--short", "HEAD"], cwd, dash_c) in BASE_BRANCHES:
        return "force"  # no destination named and the checkout is on the base branch
    return "push"


def classify_git(args, cwd, depth, inline):
    dash_c, i = None, 0
    while i < len(args) and args[i].startswith("-"):
        opt = args[i].split("=", 1)[0]
        if opt in GIT_OPTS_WITH_VALUE and "=" not in args[i]:
            if opt == "-C" and i + 1 < len(args):
                dash_c = args[i + 1]
            if opt == "-c" and i + 1 < len(args):
                m = re.match(r"alias\.([^=]+)=(.*)$", args[i + 1], re.S)
                if m:
                    inline = dict(inline, **{m.group(1): m.group(2)})
            i += 2
        else:
            i += 1
    if i >= len(args):
        return []
    sub, rest = args[i], args[i + 1:]
    if sub not in GIT_BUILTINS and depth < 3:
        alias = git_alias(sub, cwd, dash_c, inline)
        if alias:
            if alias.startswith("!"):
                return classify_shell(alias[1:] + " " + " ".join(shlex.quote(a) for a in rest),
                                      cwd, depth + 1)
            return classify_git(shlex.split(alias) + rest, cwd, depth + 1, inline)
    flags = set(rest)
    if sub in GIT_HISTORY:
        if flags & NON_WRITING or (sub in {"cherry-pick", "revert"} and "-n" in flags):
            return []
        return [("commit", f"git {sub}")]
    if sub == "push":
        kind = push_kind(rest, cwd, dash_c)
        label = "git push (force, delete, mirror or to the base branch)" if kind == "force" \
            else "git push"
        return [(kind, label)] if kind else []
    if sub == "submodule" and "foreach" in rest:
        return classify_shell(" ".join(rest[rest.index("foreach") + 1:]), cwd, depth + 1)
    if sub in {"subtree", "lfs"} and "push" in rest:
        return [("push", f"git {sub} push")]
    if sub in {"pull", "update-ref"}:
        return [("history", f"git {sub}")]
    if sub == "reset":
        before_dashdash = rest[:rest.index("--")] if "--" in rest else rest
        if flags & {"--hard", "--soft", "--merge", "--keep"} or any(
                re.match(r"^(?:HEAD[~^]\S*|[0-9a-f]{7,40}|origin/\S+|@\{\S+\})$", a)
                for a in before_dashdash if not a.startswith("-")):
            return [("history", "git reset")]
    if sub == "branch" and flags & {"-D", "-f", "--force", "-M", "-C"}:
        return [("history", "git branch (force/delete)")]
    if sub == "stash" and rest[:1] and rest[0] in {"drop", "clear"}:
        return [("history", f"git stash {rest[0]}")]
    return []


def option_value(args, names):
    for i, a in enumerate(args):
        for n in names:
            if a == n and i + 1 < len(args):
                return args[i + 1]
            if n.startswith("--") and a.startswith(n + "="):
                return a[len(n) + 1:]
    return None


def read_body(args, cwd, body_names, file_names):
    if {"-e", "--editor", "-w", "--web"} & set(args):
        return None
    body = option_value(args, body_names)
    if body is not None:
        return body
    path = option_value(args, file_names)
    if path and path != "-":
        try:
            with open(os.path.join(cwd or "", os.path.expanduser(path)), encoding="utf-8") as f:
                return f.read()
        except OSError:
            return None
    return None


def classify_gh(args, cwd):
    rest = list(args)
    while rest and rest[0].startswith("-"):
        rest = rest[2:] if rest[0] in {"-R", "--repo", "--hostname"} else rest[1:]
    if len(rest) < 2:
        return []
    group, verb, tail = rest[0], rest[1], rest[2:]
    if group == "api":
        return classify_gh_api(rest[1:], cwd)
    if group == "release" and verb in {"create", "upload", "delete", "edit"}:
        return [("push", f"gh release {verb}")]
    if group == "repo" and verb == "delete":
        return [("destructive", "gh repo delete")]
    if group not in {"issue", "pr"}:
        return []
    if group == "pr" and verb == "create":
        return [("pr", "gh pr create")]
    if group == "pr" and verb == "merge":
        return [("merge", "gh pr merge")]
    if verb in {"comment", "review"}:
        if verb == "review" and not ({"-c", "--comment", "-b", "--body", "-F", "--body-file",
                                      "-r", "--request-changes"} & set(tail)):
            return [("tracker", "gh pr review")]
        return [("comment", f"gh {group} {verb}",
                 read_body(tail, cwd, ["--body", "-b"], ["--body-file", "-F"]))]
    if verb == "delete":
        return [("destructive", f"gh {group} delete")]
    found = []
    if verb in {"create", "edit", "close", "reopen", "transfer", "lock", "unlock", "pin", "unpin",
                "develop", "ready"}:
        found.append(("tracker", f"gh {group} {verb}"))
        comment = option_value(tail, ["--comment", "-c"])
        if verb == "close" and comment is not None:
            found.append(("comment", f"gh {group} close --comment", comment))
    return found


def classify_gh_api(tail, cwd):
    method = ""
    for i, a in enumerate(tail):
        m = re.match(r"^(?:-X|--method=?)(\w*)$", a)
        if m:
            method = (m.group(1) or (tail[i + 1] if i + 1 < len(tail) else "")).upper()
    fields = [a for a in tail if a.split("=")[0] in {"-f", "-F", "--field", "--raw-field", "--input"}]
    endpoint = next((a for a in tail if not a.startswith("-") and a.upper() != method), "")
    if endpoint == "graphql":
        queries = [a.split("=", 1)[1] for a in tail if a.startswith("query=")]
        if "--input" not in tail and queries and all(
                re.match(r"\s*(?:query\b[^{]*)?\{", q) and "mutation" not in q for q in queries):
            return []
        if any(re.search(r"(?:add|update)\w*comment", q, re.I) for q in queries):
            return [("comment", "gh api graphql (comment)", None)]
        return [("tracker", "gh api graphql")]
    if method == "GET" or (not method and not fields):
        return []
    method = method or "POST"
    if "comments" in endpoint:
        if method == "DELETE":
            return [("delete", "gh api DELETE comment")]
        body = None
        for j, a in enumerate(tail):
            if a in {"-f", "--raw-field", "-F", "--field"} and j + 1 < len(tail) \
                    and tail[j + 1].startswith("body="):
                body = tail[j + 1][5:]
        return [("comment", "gh api (comment)", body)]
    if re.search(r"/pulls/\d+/merge$", endpoint):
        return [("merge", "gh api merge")]
    if re.search(r"/pulls/?$", endpoint):
        return [("pr", f"gh api {method} {endpoint}")]
    if "/git/refs" in endpoint:
        return [("force", f"gh api {method} {endpoint}")]
    return [("tracker", f"gh api {method}")]


def skip_prefix(tokens):
    i = 0
    while i < len(tokens):
        t = tokens[i]
        name = os.path.basename(t).lower()
        if re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", t) or t in SHELL_KEYWORDS:
            i += 1
        elif name == "env":
            i += 1
            while i < len(tokens) and (tokens[i].startswith("-") or "=" in tokens[i]):
                if tokens[i] == "-S":
                    break
                i += 2 if tokens[i] in {"-u", "-C"} else 1
            if i < len(tokens) and tokens[i] == "-S":
                return i - 1  # env -S "<command>": handled as a command carrier
        elif name in WRAPPERS:
            i += 1
            while i < len(tokens) and tokens[i].startswith("-"):
                i += 2 if tokens[i] in WRAPPERS[name] else 1
            if name in {"timeout", "gtimeout"} and i < len(tokens):
                i += 1
        else:
            break
    return i


def classify_shell(command, cwd, depth=0):
    if depth > 4:
        return []
    command = command.replace("\\\n", " ")
    command, fed, bodies = strip_heredocs(command)
    found = []
    for body in fed:
        found += classify_shell(body, cwd, depth + 1)
    for inner in re.findall(r"\$\(([^()]*)\)|`([^`]*)`", command):
        found += classify_shell(inner[0] or inner[1], cwd, depth + 1)
    if "<<<" in command or re.search(r"\|\s*(?:\S*/)?(?:sh|bash|zsh|dash|ksh)\b(?!\s+-\w*c)",
                                     command) or re.search(r"\beval\b|\$\(", command):
        found += raw_scan(command, cwd, depth)
        for body in bodies:  # a heredoc piped into a shell or captured runs as commands
            found += raw_scan(body, cwd, depth)
    try:
        segments = split_segments(command)
    except ValueError:
        return found + raw_scan(command, cwd, depth)
    per_segment = {}
    for tokens in segments:
        seg_start = len(found)
        i = skip_prefix(tokens)
        if i >= len(tokens):
            continue
        prog = os.path.basename(tokens[i]).lower()
        args = tokens[i + 1:]
        if prog in SHELLS or prog in {"su", "eval", "env"}:
            carrier = None
            if prog == "eval":
                carrier = " ".join(args)
            else:
                for j, a in enumerate(args):
                    if re.fullmatch(r"-[a-z]*c[a-z]*", a) or (prog == "env" and a == "-S"):
                        carrier = args[j + 1] if j + 1 < len(args) else None
                        break
            if carrier:
                found += classify_shell(carrier, cwd, depth + 1)
            if prog != "env":
                continue
        # every git/gh word in the segment: covers find -exec, xargs, submodule foreach, …
        for j in range(i, len(tokens)):
            name = os.path.basename(tokens[j]).lower()
            if name == "git":
                found += classify_git(tokens[j + 1:], cwd, depth, {})
            elif name == "gh":
                found += classify_gh(tokens[j + 1:], cwd)
            elif j > i and name in SHELLS and j + 2 < len(tokens) and \
                    re.fullmatch(r"-[a-z]*c[a-z]*", tokens[j + 1]):
                found += classify_shell(tokens[j + 2], cwd, depth + 1)  # find -exec sh -c '…'
        joined = " " + " ".join(args)
        if prog == "curl" and TRACKER_SERVER.search(joined) and re.search(
                r"\s-X\s*(?:POST|PUT|PATCH|DELETE)|\s--request\s+(?:POST|PUT|PATCH|DELETE)|"
                r"\s(?:-d|--data\S*|-F|--form)\s", joined):
            found.append(("comment", "curl to a tracker comment API", None)
                         if re.search(r"/comments?\b", joined) else ("tracker", "curl to a tracker API"))
        for action in {item[0] for item in found[seg_start:]} & CONSUMED_BY_USE:
            per_segment[action] = per_segment.get(action, 0) + 1
    found += [("repeat", f"{n} × {a} in one call") for a, n in per_segment.items() if n > 1]
    return found


def split_words(name):
    return set(re.split(r"[_\-\s]+", re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", name).lower()))


def nested_texts(value, key_ok=False):
    """String leaves whose own key names text (lists pass the key on; dicts do not)."""
    if isinstance(value, str):
        return [value] if key_ok else []
    if isinstance(value, dict):
        out = []
        for k, v in value.items():
            out += nested_texts(v, bool(TEXT_KEYS.search(str(k))) and str(k) != "type")
        return out
    if isinstance(value, list):
        return [t for v in value for t in nested_texts(v, key_ok)]
    return []


def comment_candidates(item):
    texts = item[2] if len(item) > 2 else None
    if texts is None:
        return []
    return [texts] if isinstance(texts, str) else list(texts)


def classify_mcp(tool_name, tool_input):
    m = re.match(r"^mcp__(.+?)__(.+)$", tool_name)
    if not m:
        return []
    server, words = m.group(1), split_words(m.group(2))
    if GIT_SERVER.search(server):
        if "commit" in words:
            return [("commit", tool_name)]
        if "push" in words:
            return [("push", tool_name)]
        if words & {"reset", "rebase", "merge"}:
            return [("history", tool_name)]
        return []
    if not TRACKER_SERVER.search(server):
        return []
    if {"resolve", "assignees"} <= words:
        return []
    request = words & {"request", "requests"}
    verbs = words - request - ({"merge"} if request else set()) if words & {"pull", "merge"} and \
        request else words
    if words & READ_WORDS and not verbs & WRITE_WORDS:
        return []
    inp = tool_input or {}
    has_text = any(isinstance(v, str) and v.strip() and TEXT_KEYS.search(k) for k, v in inp.items())
    reviewish = words & {"review", "thread", "comment", "comments", "note", "notes"}
    if re.search(r"github|gitlab", server, re.I) and not reviewish:
        if request and words & {"pull", "merge", "mr"} and "create" in words:
            return [("pr", tool_name)]
        if "merge" in words and (request or "mr" in words) and not words & {"update"}:
            return [("merge", tool_name)]
        if "push" in words or (words & {"file", "files", "branch", "tag", "release"}
                               and words & {"create", "update", "delete", "push"}):
            return [("push", tool_name)]
    if words & COMMENT_WORDS or ("review" in words and has_text):
        if words & {"delete", "remove"}:
            return [("delete", tool_name)]
        texts = [v for k, v in inp.items() if isinstance(v, str) and TEXT_KEYS.search(k)
                 and v.strip()]
        nested = [t for t in nested_texts({k: v for k, v in inp.items() if not isinstance(v, str)})
                  if t.strip()]
        if nested:
            texts.append("".join(nested))
        if texts:
            return [("comment", tool_name, texts)]
        if words & {"create", "add", "post", "reply", "send", "write"}:
            return [("comment", tool_name, None)]
    if words & {"delete", "remove", "archive", "merge"} and \
            words & {"task", "tasks", "issue", "issues", "page", "pages", "list", "folder",
                     "document", "project"} and \
            not words & {"from", "tag", "tags", "label", "labels", "link", "links", "dependency",
                         "watcher", "watchers", "attachment", "requests"}:
        return [("destructive", tool_name)]
    return [("tracker", tool_name)]


def tamper(tool_name, tool_input, data):
    if tool_name not in {"Bash", "Monitor", "Write", "Edit", "MultiEdit", "NotebookEdit"}:
        return []
    session = re.sub(r"[^A-Za-z0-9_-]", "", (data or {}).get("session_id") or "")
    blob = json.dumps(tool_input or {}, ensure_ascii=False)
    marks = ["task-runs/.guard", "/.guard"] + ([session + ".jsonl"] if len(session) >= 8 else [])
    hit = any(m in blob for m in marks)
    if not hit and tool_name in {"Bash", "Monitor"} and "task-runs" in blob:
        hit = bool(re.search(r"(?<![\w-])(?:rm|rmdir|mv|unlink|truncate|chmod|shred|find)(?![\w-])",
                             (tool_input or {}).get("command") or ""))
    if hit:
        return [("tamper", f"{tool_name} on the session transcript or the guard's markers")]
    return []


def classify(tool_name, tool_input, cwd, data=None):
    found = tamper(tool_name, tool_input, data) if data is not None else []
    if tool_name in {"Bash", "Monitor"}:
        found += classify_shell((tool_input or {}).get("command") or "", cwd)
    elif tool_name.startswith("mcp__"):
        found += classify_mcp(tool_name, tool_input)
    unique, seen = [], set()
    for item in found:
        key = json.dumps(item, ensure_ascii=False, default=str)
        if key not in seen:
            seen.add(key)
            unique.append(item)
    return unique


# --- decision -----------------------------------------------------------------------------

HOW = {
    "commit": ("«закоммить»", "[commit]"),
    "push": ("«запушь»", "[push]"),
    "pr": ("«открой PR»", "[pr]"),
    "merge": ("«смержи PR»", "[merge]"),
    "force": ("«форс-пушь» / «запушь в main»", "[force-push]"),
    "history": ("«сбрось» / «подтяни»", "[reset]"),
    "tracker": ("«переведи в ревью»", "[status]"),
    "destructive": ("«удали задачу»", "[delete-task]"),
    "delete": ("«удали коммент»", "[delete-comment]"),
}


STEMS = {"commit": r"комм?ит|commit", "push": r"пуш|push|залей", "pr": r"\bpr\b|\bпр\b|пулл|pull",
         "tracker": r"статус|ревью|review|status|работу", "merge": r"мерж|merge",
         "force": r"форс|force|main|master", "history": r"сброс|reset|pull|подтян",
         "delete": r"удали|delete", "destructive": r"удали|delete"}


def decide(gated, text, actions, approved, used, unseen, failure):
    if failure == UNATTENDED_RUN:
        what = ", ".join(item[1] for item in gated)
        return (f"[ticket guard] Blocked: {what}. In {UNATTENDED_RUN} nothing leaves the working "
                "tree from this session — the caller publishes. Do not retry or work around this; "
                "finish the run and write RESULT.json (SKILL.md, Unattended).")
    problems = []
    for item in gated:
        action, what = item[0], item[1]
        if action == "tamper":
            problems.append(f"{what}: the guard's own state is off limits in a /ticket session.")
        elif action == "repeat":
            problems.append(f"{what}: one command is one action — split the call, each repeat "
                            "needs its own command.")
        elif action == "comment":
            texts = [normalize_comment(t) for t in comment_candidates(item)]
            if any(t in approved for t in texts):
                continue
            if texts and any(t in unseen for t in texts):
                problems.append(
                    f"{what}: the user picked [post] for this text, but it was never shown in full "
                    "— the dialog cuts long previews and it was not printed verbatim in your "
                    "messages since their latest message. Print the whole text as plain text (not "
                    "quoted or indented), then ask again.")
            elif texts and any(t in used for t in texts):
                problems.append(f"{what}: this exact text was already posted since the user's "
                                "latest message; posting it again needs a new approval.")
            else:
                problems.append(
                    f"{what}: a tracker comment is posted only after the user approved these exact "
                    "words — an AskUserQuestion, after their latest message, whose picked option "
                    "carries [post] in its label and exactly this text as its `preview`, shown in "
                    "full (SKILL.md, Task comments, step 4). Post the text unchanged.")
        elif action not in actions:
            typed, tag = HOW[action]
            hint = ""
            if text and re.search(STEMS.get(action, r"$^"), normalize_text(text)):
                hint = (" (The latest message mentions it, but not as a plain order the guard "
                        "reads — conditional, deferred, negated, misspelt or unusual phrasing is "
                        "not counted.)")
            problems.append(f"{what}: no command for it since the user's latest message, or it was "
                            f"already used once; the user authorizes it by typing it (e.g. {typed}) "
                            f"or by picking an AskUserQuestion option whose label carries {tag}."
                            + hint)
    if not problems:
        return None
    note = ""
    if text is not None:
        snippet = " ".join(text.split())
        note = f" Latest user message: «{snippet[:120]}{'…' if len(snippet) > 120 else ''}»."
    elif failure:
        note = f" ({failure}.)"
    return ("[ticket guard] Blocked. " + " ".join(problems) + note +
            " Stop and ask the user; do not retry this call or reach the same result another "
            "way until they give the command.")


MARK_DIR = os.path.expanduser("~/.claude/task-runs/.guard")
MARK_TTL = 14 * 24 * 3600


def marker(session_id):
    safe = re.sub(r"[^A-Za-z0-9_-]", "", session_id or "")
    return os.path.join(MARK_DIR, safe) if safe else None


def activate(session_id):
    path = marker(session_id)
    if not path:
        return
    if os.path.exists(path):
        os.utime(path, None)
        return
    os.makedirs(MARK_DIR, exist_ok=True)
    with open(path, "w") as f:
        f.write("ticket session\n")
    now = os.path.getmtime(path)
    for name in os.listdir(MARK_DIR):
        old = os.path.join(MARK_DIR, name)
        try:
            if now - os.path.getmtime(old) > MARK_TTL:
                os.unlink(old)
        except OSError:
            pass


def subagent_reason(gated):
    what = ", ".join(item[1] for item in gated)
    return (f"[ticket guard] Blocked: {what}. In a /ticket session subagents never commit, push "
            "or write to the tracker — the orchestrator does that, and only on the user's "
            "command. Do not retry or work around this; report what you would have done.")


def deny(reason):
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse",
                                             "permissionDecision": "deny",
                                             "permissionDecisionReason": reason}}))


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "--main"
    raw = sys.stdin.read()
    try:
        data = json.loads(raw)
        tool_name = data.get("tool_name", "")
        session, agent = data.get("session_id"), data.get("agent_id")
        if mode == "--subagent":
            path = marker(session)
            if not agent or not path or not os.path.exists(path):
                return 0
        else:
            activate(session)
        cwd = data.get("cwd")
        gated = classify(tool_name, data.get("tool_input") or {}, cwd, data)
        if not gated:
            return 0
        if agent:
            reason = subagent_reason(gated)
        else:
            text, actions, approved, used, unseen, failure = read_authorization(
                data.get("transcript_path"), cwd)
            reason = decide(gated, text, actions, approved, used, unseen, failure)
    except Exception as exc:  # fail closed for anything that looks gated
        if not re.search(r"\bgit\b|\bgh\b|commit|push|merge|rebase|comment|status|mcp__|curl|"
                         r"\.guard", raw, re.I):
            return 0
        if mode == "--subagent" and '"agent_id"' not in raw:
            return 0
        reason = f"[ticket guard] Blocked: the guard failed ({type(exc).__name__}: {exc}); " \
                 "it fails closed. Tell the user."
    if reason:
        deny(reason)
    return 0


if __name__ == "__main__":
    sys.exit(main())
