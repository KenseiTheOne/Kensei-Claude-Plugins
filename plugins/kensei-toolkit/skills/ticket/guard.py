#!/usr/bin/env python3
"""ticket guard — PreToolUse hook registered by the /kensei-toolkit:ticket skill.

Blocks, in code, what the skill may only do on the user's explicit command:

  commit       git commit / merge / rebase / cherry-pick / revert / am (history-writing) other
               than the two below — including a commit on a base branch the session was already
               on (the user chose to work there)
  merge-local  a local git merge / rebase that integrates into a base branch: run while a base
               branch is checked out, after `git switch <base>` in the same command, or
               `git rebase <upstream> <base>`; and any history write (cherry-pick, am, commit)
               after `git switch <base>` in the same command; `git commit` concluding a merge
               on a base branch; `git fetch . <branch>:<base>`. Bringing a base branch up to date
               from its own remote branch (`git merge --ff-only origin/main` on main) is history;
               a rebase of the base branch's own commits (`git rebase -i HEAD~3`) is commit
  base-sync    a git merge / rebase / pull of a base branch into the task branch (`git merge
               main`, `git rebase --onto origin/main …`, `git pull origin main`) — allowed under
               commit or merge-local; it uses
               up the commit command only when no merge-local command is open
  push         git push to a non-base branch, git send-email / send-pack, gh repo sync,
               gh pr update-branch (force with --force / --rebase), any gh call with --push,
               GitHub/GitLab/GitKraken MCP file/branch pushes
  publish      creating something public outside the task branch, one grant per object — a
               release (gh release create / upload / edit, gh api writes to …/releases), a gist
               (gh gist create / edit, gh api …/gists), a repository (gh repo create / fork,
               gh api POST …/repos or …/forks); and the same through a GitHub MCP. A grant for
               one object does not reach another: «создай репо» is no release
  repo-admin   changing an existing repository, its secrets or CI, one grant per kind:
               settings (gh repo edit incl. --visibility / rename / archive / unarchive /
               autolink, gh api PATCH repos/o/r, hooks, collaborators, pages, topics, graphql
               updateRepository), secrets (gh secret / variable / deploy-key / ssh-key / gpg-key,
               …/secrets, …/variables, …/environments, …/keys, user/keys), ci (gh workflow / run /
               cache, …/actions, …/dispatches, …/deployments), protection (gh ruleset, …/rulesets,
               …/branches/<b>/protection, tags/protection), delete (gh release delete /
               delete-asset, gh gist delete); org endpoints and full api URLs alike; the same
               through a GitHub MCP. «поставь секрет» is no visibility change. gh repo delete and
               MCP repository deletes are destructive
  pr           opening a PR / MR (gh pr create, create_pull_request, api POST …/pulls)
  merge        merging a PR / MR (gh pr merge, merge_pull_request, api …/merge)
  force        a push that rewrites, deletes or widens: --force*, -f in any bundle (-fu),
               --delete, --mirror, --all, --tags, +refspec; or one to a base branch — main,
               master, develop, production, …, the remote's default branch, the `base_branch:`
               of this session's RUN.md, or the current branch when none is named
  history      git pull, reset --hard/--soft or to a ref, update-ref, branch -D/-f, checkout -B,
               switch -C, filter-branch/-repo, stash pop/apply/drop; and throwing local changes
               away: clean -f, checkout/restore of paths, checkout/switch --force
  status       a change of the status field only: an MCP update, transition or close / reopen
               tool whose only changed key is the status (state, transition), gh issue close /
               reopen
  create-task  creating a task / issue (clickup_create_task, create_issue, gh issue create, an
               operator create on a task model); one command covers the whole batch
  tracker      any other tracker write (MCP tool, clickup_execute_operator write pairs, gh issue /
               pr / label / project edits, curl/wget/httpie writes to a tracker) — including an
               update or transition that changes the status together with other fields
  destructive  deleting a task / issue / page, merging tasks
  delete       deleting a tracker comment
  comment      posting or editing a tracker comment — only text the user approved word for word
  tamper       writing to this session's transcript, the guard's markers, the guard's own files
               or plugin install, or hook settings (a Bash write to a settings*.json; a Write/Edit
               that changes hooks, disableAllHooks, enabledPlugins or allowManagedHooksOnly, the
               file compared as JSON before and after; `claude plugin disable`) — never allowed.
               A settings file is any settings*.json in the config dir ($CLAUDE_CONFIG_DIR or
               ~/.claude) or in a `.claude` dir, or managed-settings.json, matched on the path as
               written and on its realpath (a symlink to dotfiles is still the settings);
               reading them is fine. The guard's own files are the copy that runs: with
               `--plugin-dir` on a dev clone, a /ticket session cannot edit that clone's
               skills/ticket/ or hooks/ (deliberate — the session would be editing its own
               guard); develop the plugin with /ticket from the installed copy instead
  opaque       a command the guard cannot read: a program named by $VAR or $(…) that plausibly
               is git (its name says git; or it names no other tool and its first argument is
               a writing git subcommand; a literal basename after it, `$ROOT/gradlew`, decides), a
               git subcommand built from $VAR or $(…) (`git $S origin`), runner targets named
               exactly push / publish / release / deploy / ship (`make push`, `npm run release`)
               — never allowed. A shell named by $VAR (`$SHELL -c "…"`) is read like `sh -c`
  skill-post   a skill told to post (/code-review --comment, --post) — never allowed
  delegate     SendMessage — the user confirms it (permissionDecision "ask")
  stash        git stash push — subagents only; the orchestrator stashes on the Step 5 answer

A command comes from the session transcript, read back to the latest message the user typed
(origin.kind == "human"). A message the user queued while the model was busy adds its orders to
the message before it, where it arrived — unless it holds back: a stop word («стоп», «подожди»,
«не сейчас», wait), a negated, cancelled or deferred gated action («не коммить пока», «пуш
позже», «отмена»), or a change of plan whatever it names («передумал», «я сам закоммичу»,
«сначала …», "first …", «перед этим», «дай посмотреть», «не надо», "let me see"). That voids
every command given so far, and the message itself grants nothing. Taking the step over is read
in the first person only: «я сам», «сам запушу», "I'll do it" revoke; «сделай сам» / «давай сам»
(the model is told to do it) do not. A negation about anything
else («тесты не трогай») voids nothing.

  typed text     conservative: imperatives such as «закоммить», «запушь», «залей ветку»,
                 «переведи в ревью» (status), «создай задачу» (create-task), «залейся в мейн» /
                 «смерджи в мейн» (commit + merge-local; «залей» also the push to the base
                 branch); negation scoped to its list item, conditional or cancelled sentences
                 dropped.
                 A question («почему git push упал?», "commit?") orders nothing unless it is an
                 imperative or a polite request («закоммить?», «можешь закоммитить?», "could you
                 push it?"). A git/gh command counts only as the whole item, never mentioned
                 inside a sentence; pasted text — fenced blocks, `>` lines, the middle of a long
                 message (only the first and last 4 KB are read) — never counts. English verbs
                 need a git object: "revert that commit", not "revert these functions".
  AskUserQuestion answers after that message: an option the user picked grants exactly the tags
                 in its label — [commit] [merge-local] [push] [pr] [merge] [force-push]
                 [publish] [repo-admin] [reset] [status] [create-task] [tracker-edit]
                 [delete-task] [delete-comment]; [publish] grants the object its label names
                 (релиз / release, репо / repo, гист / gist) and [repo-admin] the kind its label
                 names (visibility / rename / archive, секрет / variable, workflow / CI, защита /
                 ruleset, удалить релиз / гист) — nothing when it names none; [post]
                 approves the option's `preview` as the comment text, if the preview was shown
                 in full

A command is used up by the call it authorized: one commit, one push, one status write — and one
call may not carry the same action twice. A create-task command is the exception: it covers every
task of the batch it was given for, until the user's next message. A call the user rejected uses nothing up, nor does one
that failed (is_error: a non-zero exit, a rejected push, a commit a hook refused) — for a shell
command only when the failure is the gated step's own: one command, or an `&&` chain ending in
it. In `git push; false` or `git push && npm test` the push may have happened, so it is used
up. An MCP call that failed is used up unless the head of its error plainly refuses it (a
validation error, invalid params / -32602, a 4xx code, "not found"): after a timeout or an
unclear error the write may have landed, and it is not repeated blind. A comment text that was posted cannot be posted again;
every text field of the call must be the approved text.
When the model invoked /ticket itself, what the user typed before that does not count.

Two registrations, because a skill's frontmatter hooks do not reach its subagents (measured):

  guard.py --main      SKILL.md frontmatter; the main session once /ticket is invoked. Marks the
                       session as a ticket session, then checks the command.
  guard.py --subagent  plugin hooks/hooks.json via hooks/subagent-guard.sh, which runs this only
                       for subagent calls (`agent_id` set) in a marked session. Subagents are
                       refused every gated action — only the orchestrator commits, pushes or
                       writes to the tracker.
  guard.py --post      SKILL.md frontmatter, PostToolUse; only notes this session's run (below).

This session's run is the run directory whose RUN.md the main session last wrote (Write / Edit,
or a shell redirect into it), noted by `guard.py --post` once the call has run; the marker keeps
it. Only its `base_branch:` joins the base
branches; before the session writes a RUN.md there is none, and another task's RUN.md in the
same repository never counts.

Output: nothing when the call is not gated or is authorized — the normal permission flow
continues, the hook never grants anything. A JSON "deny" with the reason otherwise ("ask" for
SendMessage). Internal errors fail closed for calls that look gated.

Known gaps, where the skill's text rules alone apply: git run from a script or an interpreter
(`sh ./x.sh`, `python -c`), the browser, a child `claude` session, tracker CLIs other than gh.
A typed status command allows any status change, closing the issue included — the guard cannot
see the target status. A typed «сначала прогони тесты, потом закоммить» grants the commit at
once — the order rests on the skill text.
The transcript fields read here (origin.kind, queued_command attachments, toolUseResult,
is_error) were checked against Claude Code 2.1.285.
"""

import fnmatch
import json
import os
import re
import shlex
import subprocess
import sys

# --- classification tables ----------------------------------------------------------------

TRACKER_SERVER = re.compile(
    r"(?<![a-z0-9])(?:clickup|jira|atlassian|confluence|linear|github|gitlab|youtrack|asana|"
    r"notion|trello|monday|shortcut|taiga|plane|gitkraken)(?![a-z0-9])", re.I)
GIT_SERVER = re.compile(r"^git$|git[-_]?mcp|^mcp[-_]?git$|gitkraken", re.I)
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
ID_KEY = re.compile(r"(?:^|_|-)id$|[a-z]Id$|^id$", re.I)


def text_key(key):
    """A key that names comment text — `comment_text`, `body`; never an id (`comment_id`)."""
    key = str(key)
    return bool(TEXT_KEYS.search(key)) and not ID_KEY.search(key) and key != "type"


GIT_HISTORY = {"commit", "merge", "rebase", "cherry-pick", "revert", "am", "commit-tree"}
NON_WRITING = {"--abort", "--quit", "--dry-run", "--no-commit", "--show-current-patch",
               "--edit-todo"}
BASE_BRANCHES = {"main", "master", "develop", "dev", "trunk", "release", "production", "prod",
                 "staging", "stable"}
# gh: commands that only read or touch local config; anything else is a write
GH_LOCAL_GROUPS = {"auth", "config", "alias", "completion", "help", "extension", "version",
                   "browse", "search", "status", "codespace", "co"}
GH_READ_VERBS = {"view", "list", "ls", "diff", "checks", "status", "download", "watch", "clone",
                 "checkout", "get", "field-list", "item-list", "verify", "verify-asset", "check",
                 "logs"}
# skills that publish what the guard cannot see when invoked with these flags
PUBLISH_FLAGS = re.compile(r"(?<![\w-])--(?:comment|post)(?![\w-])")
# kinds refused to subagents only — the orchestrator may run them (the Step 5 "stash it")
SUBAGENT_ONLY = {"stash"}
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
GITISH = re.compile(r"(?<![^\s;&|(`'\"=])(?:\S*/)?(git|gh)(?=\s)", re.I)  # at token starts only
# a command word produced by a substitution: `$(echo git) push`, `` `which git` push ``
SUBST_PROGRAM = re.compile(r"(?:^|[;&|(\n])\s*(?:\w+=\S*\s+)*((?:\$\([^()]*\)|`[^`]*`)\S*)\s+"
                           r"([^;&|\n]*)")

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
POLITE_LEAD = re.compile(r"^(?:(?:could|can|would|will)\s+you\s+(?:please\s+)?|please\s+|"
                         r"pls\s+|plz\s+)+")
LEAD = re.compile(r"^(?:(?:ну|ок|окей|ok|okay|да|yes|yeah|yep|lgtm|давай|тогда|теперь|сейчас|"
                  r"now|so|go\s+ahead|go|just|also|ещ[её]|только|сразу|plz|pls|please|"
                  r"пожалуйста)\s+)+")
BASE_WORDS = r"(?:main|master|develop|мастер|мейн|мэйн|девелоп)"
PR_WORDS = r"(?:пр|pr|пулл?-?реквест\w*|пул\s+реквест\w*|pull\s+request|мр|mr|merge\s+request)"
POUR = r"(?:за|в)?(?:лей|ливай)(?:ся|тесь|те)?"  # «залей(ся)», «влей», «заливай» … в мейн
# a word between the verb and «в мейн» that is not the PR: «смерджи пр в мейн» merges the PR
NOT_PR = r"(?!(?:пр|pr|пулл?\S*|пул|pull|мр|mr|merge\s+request)(?![\w-]))"
# publish and repo-admin objects: whole nouns, not «релизную ветку», «репорт», "release build"
RELEASE_RU = r"релиз(?:а|ы|ов|ом)?(?![\w-])"
REPO_WORD = (r"(?:репо|репозитори(?:й|я|ю|и|ем)|repos?|repository)(?![\w-])")
NO_PREP = r"(?:\s+(?!(?:в|во|к|на|из|по|для|от|с|со|in|to|into|for)\s)\S+)?"  # «создай в репо …»
NOT_RELEASE = (r"(?!\s+(?:branch|build|candidate|notes?|mode|config\w*|flag|script|job|pipeline|"
               r"process|checklist|version|tag)(?![\w-]))")
NOT_REPO = (r"(?!\s+(?:pattern|class|interface|layer|object|method|module|abstraction|"
            r"implementation|instance|field|wrapper|mock|stub|test|type|struct|service|helper|"
            r"паттерн|класс|интерфейс|слой|метод|модул)\w*)")
RU_IMPERATIVE = {
    "commit": r"(?:за)?комм?ит(?:ь|ни|ьте|ните)|(?:за|с)?мерд?ж(?:и|ни)(?!\s+(?:\S+\s+)?"
              r"(?:пр|pr|пулл\w*|pull|mr|мр)\b)|ребейзни|засквошь|сквошни|(?:за)?амендь|амендни|"
              r"(?:сделай|сделайте|создай|оформи|собери|упакуй|схлопни)(?:\s+\S+){0,3}\s+коммит\w*|" +
              POUR + r"(?:\s+" + NOT_PR + r"\S+){0,2}\s+(?:в|на)\s+" + BASE_WORDS + r"|"
              r"мерд?ж(?:\s+" + NOT_PR + r"\S+)?\s+(?:в|на)\s+" + BASE_WORDS,
    "push": r"(?:(?:за)?пуш(?:ь|ни|ьте|ните)|запуш)(?!\s+(?:в|на)\s+" + BASE_WORDS + r")|"
            r"за(?:лей|ливай)(?:те|ся)?(?:\s+\S+){0,2}\s+(?:(?:на|в)\s+)?(?:ветк\w*|бранч\w*|"
            r"origin|remote|ремоут|гит|github|гитхаб)",
    "pr": r"(?:открой|создай|сделай|заведи)(?:\s+\S+)?\s+" + PR_WORDS,
    "merge": r"(?:за|с)?мерд?ж(?:и|ни)(?:\s+\S+)?\s+(?:пр|pr|пулл\w*|pull\s+request|mr|мр)",
    "force": r"форсни|(?:за)?форс-?пуш\w*|(?:за)?пуш\w*(?:\s+\S+)?\s+(?:в|на)\s+" + BASE_WORDS +
             r"|" + POUR + r"(?:\s+\S+){0,2}\s+(?:в|на)\s+" + BASE_WORDS,
    "history": r"сбрось|откати|подтяни|спулль|(?:верни|достань|примени|восстанови)(?:\s+\S+)?\s+"
               r"(?:ст[еэ]ш\w*|stash)|(?:почисти|очисти)(?:\s+\S+){0,2}\s+(?:рабоч\w+|дерев\w*|"
               r"worktree|untracked)|выкинь(?:\s+\S+){0,2}\s+изменени\w*",
    "merge-local": POUR + r"(?:\s+" + NOT_PR + r"\S+){0,2}\s+(?:в|на)\s+" + BASE_WORDS + r"|"
                   r"(?:с|за)?мерд?ж(?:и|ни)?(?:\s+" + NOT_PR + r"\S+)?\s+(?:в|на)\s+" +
                   BASE_WORDS,
    "status": r"(?:переведи|переведите|перекинь|перенеси|двинь|кинь|поставь)(?:\s+\S+){0,3}\s+"
               r"(?:в|на)\s+(?:\S+\s+)?(?:ревью|review|работу|progress|done|готово|qa|тест\w*|"
               r"closed|закрыт\w*)|(?:смени|поменяй|измени|обнови|поставь)(?:\s+\S+){0,2}\s+"
               r"статус\w*|(?:возьми|бери)(?:\s+\S+)?\s+в\s+работу|закрой(?:\s+\S+)?\s+"
               r"(?:задач\w*|тикет\w*|issue)|переоткрой\w*|статус\s*(?:→|->)",
    "tracker": r"назначь\w*",
    "create-task": r"(?:создай|создайте|заведи|заведите|добавь|добавьте)"
                   r"(?:\s+(?!(?:в|во|к|на|из|по|для|от)\s)\S+){0,2}\s+"
                   r"(?:задач\w*|тикет\w*|таск\w*|issue\w*|подзадач\w*)"
                   r"(?!\s+(?:коммент|комментари|comment)\w*)",
    "publish-release": r"(?:опубликуй|выпусти|создай|сделай)" + NO_PREP + r"\s+(?:" + RELEASE_RU +
                       r"|release(?![\w-])" + NOT_RELEASE + r")",
    "publish-repo": r"(?:создай|заведи|форкни)" + NO_PREP + r"\s+" + REPO_WORD + NOT_REPO,
    "publish-gist": r"(?:создай|заведи)" + NO_PREP + r"\s+(?:гист(?:а|ы)?|gists?)(?![\w-])",
    "repo-admin-settings": r"(?:сделай|переведи)(?:\s+\S+)?\s+" + REPO_WORD + r"\s+(?:в\s+)?"
                           r"(?:публичн\w*|приватн\w*|открыт\w*|закрыт\w*|public|private)|"
                           r"(?:переименуй|заархивируй|архивируй|разархивируй)(?:\s+\S+)?\s+" +
                           REPO_WORD,
    "repo-admin-secrets": r"(?:поставь|задай|добавь|обнови|смени|удали|установи)(?:\s+\S+)?\s+"
                          r"(?:секрет(?:ы|а|ов)?|secrets?|переменн\w*\s+(?:окружени\w*\s+)?"
                          r"(?:в\s+)?(?:репо\w*|ci|actions|github)|deploy[- ]?keys?|"
                          r"деплой[- ]?ключ\w*)(?![\w-])(?!(?:\s+\S+){0,2}\s+(?:в|во|из)\s+"
                          r"(?:код|конфиг|файл|класс|модул|скрипт|тест|\.?env)\w*)",
    "repo-admin-ci": r"(?:запусти|перезапусти|включи|выключи|отключи)(?:\s+\S+)?\s+(?:workflow|"
                     r"воркфло\w*|ci|джоб\w*|пайплайн\w*)(?![\w-])",
    "repo-admin-protection": r"(?:включи|выключи|настрой|поставь|сними|убери)(?:\s+\S+)?\s+"
                             r"(?:защит\w*\s+(?:\S+\s+)?(?:ветк\w*|бранч\w*|branch\w*|тег\w*|"
                             r"main|master|мейн\w*|мастер\w*)|ruleset\w*|branch\s+protection)",
    "repo-admin-delete": r"удали(?:\s+\S+)?\s+(?:" + RELEASE_RU + r"|releases?|гист(?:а|ы)?|gists?)"
                         r"(?![\w-])",
    "delete": r"(?:удали|сотри|снеси)(?:\s+(?:этот|тот|мой|свой|последний|предыдущий|старый|наш|"
              r"его))?\s+(?:коммент\w*|комментари\w*)"
              r"(?!(?:\s+\S+){0,2}\s+(?:в|из)\s+(?:код|файл))",
    "destructive": r"удали(?:\s+\S+){0,2}\s+(?:задач\w*|тикет\w*)",
}
RU_INFINITIVE = {  # only with a polite marker or «не забудь»
    "commit": r"(?:за)?комм?ит(?:ить|нуть)",
    "push": r"(?:за)?пуш(?:ить|нуть)",
    "status": r"перевести(?:\s+\S+){0,3}\s+(?:в|на)\s+(?:\S+\s+)?(?:ревью|review|работу|done)",
    "create-task": r"(?:создать|завести)(?:\s+\S+){0,2}\s+(?:задач\w*|тикет\w*|issue\w*)",
}
# An English verb orders a git action only with a git object: "commit it", "push the changes",
# "revert that commit" — not "revert these functions" or "reset the counter".
GIT_OBJECT = (r"(?:changes?|commits?|work|fix(?:es)?|branch(?:es)?|diff|stuff|everything|all|"
              r"result|edits?|code)")
EN_TAIL = (r"(?=\s*$|\s+(?:it|this|that|them|everything|now|please|pls|plz|asap|already|"
           r"--\S*)(?![\w'])|\s+(?:(?:the|my|your|these|those|this|that|all|our|its)\s+)+"
           + GIT_OBJECT + r"(?![\w'])|\s+" + GIT_OBJECT + r"(?![\w'])|\s+(?:to|into|onto|with)\s+"
           r"(?:the\s+)?(?:branch|remote|origin|\S*/\S+|" + BASE_WORDS + r")(?![\w']))")
EN_STATUS = (r"(?:review|done|qa|testing|test|closed|complete|completed|backlog|todo|to\s+do|"
             r"ready|blocked|in\s+(?:review|progress|qa|testing|work)|progress|\"[^\"]+\")")
EN_IMPERATIVE = {  # must start the list item
    "commit": r"(?:commit|amend|rebase|squash|cherry-?pick|revert|merge(?!\s+(?:the\s+)?"
              r"(?:pr|pull)))" + EN_TAIL,
    "push": r"push" + EN_TAIL,
    "pr": r"(?:open|create|raise|file)\s+(?:a\s+|the\s+)?(?:pr|pull\s+request|mr|merge\s+request)",
    "merge": r"merge\s+(?:the\s+|this\s+)?(?:pr|pull\s+request)",
    "force": r"force[- ]?push|push(?:\s+\S+){0,2}\s+(?:to|into)\s+(?:origin/)?" + BASE_WORDS +
             r"(?![\w'])",
    "history": r"(?:pull|reset)" + EN_TAIL + r"|(?:pop|apply|restore)\s+(?:the\s+)?stash|"
               r"stash\s+pop|discard\s+(?:(?:the|my|all|local)\s+)*changes",
    "merge-local": r"merge(?:\s+(?!(?:pr|pull|mr|merge)(?![\w-]))\S+){0,2}\s+(?:to|into)\s+"
                   r"(?:origin/)?" + BASE_WORDS + r"(?![\w'])",
    "status": r"(?:move|set|change|mark|close|reopen)(?:\s+\S+){0,3}\s+(?:status|"
              r"(?:as\s+|to\s+)?" + EN_STATUS + r"(?![\w']))|(?:close|reopen)\s+"
              r"(?:the\s+|this\s+)?(?:task|issue|ticket)",
    "tracker": r"assign\s+(?:the\s+|this\s+)?(?:task|issue|ticket)",
    "create-task": r"(?:create|open|file|add)\s+(?:a\s+|an\s+|the\s+|these\s+|new\s+)*"
                   r"(?:tasks?|issues?|tickets?)(?![\w-])(?!\s+comments?)",
    "publish-release": r"(?:publish|create|cut)\s+(?:a\s+|the\s+|new\s+)*release(?![\w-])" +
                       NOT_RELEASE,
    "publish-repo": r"(?:create|fork)\s+(?:a\s+|the\s+|new\s+|private\s+|public\s+)*"
                    r"(?:repo|repository)(?![\w-])" + NOT_REPO,
    "publish-gist": r"create\s+(?:a\s+|the\s+|new\s+)*gist(?![\w-])",
    "repo-admin-settings": r"make\s+(?:the\s+|this\s+)?(?:repo|repository)\s+(?:public|private)|"
                           r"(?:rename|archive|unarchive)\s+(?:the\s+|this\s+)?(?:repo|repository)"
                           r"(?![\w-])",
    # a secret or variable of the repository or CI — not "add a local variable for the count"
    "repo-admin-secrets": r"(?:set|add|update|delete|remove|rotate)\s+(?:a\s+|an\s+|the\s+)?"
                          r"(?:new\s+)?(?:(?:repo|repository|ci|actions|github|org)\s+"
                          r"(?:secret|variable)s?(?![\w-])|(?:\S+\s+)?secrets?(?:\s+\w*_[\w_]*)?"
                          r"(?=\s*$|\s+(?:in|on|to|for|from)\s+(?:the\s+)?(?:repo|repository|ci|"
                          r"actions|github)(?![\w-]))|(?:secret|variable)s?(?:\s+\S+)?\s+(?:in|on|to|"
                          r"for|from)\s+(?:the\s+)?(?:repo|repository|ci|actions|github)(?![\w-])|"
                          r"deploy\s+keys?(?![\w-]))",
    "repo-admin-ci": r"(?:re)?run\s+(?:the\s+)?(?:\S+\s+)?(?:workflow|ci|pipeline)(?![\w-])|"
                     r"(?:enable|disable)\s+(?:the\s+)?(?:\S+\s+)?workflow(?![\w-])",
    "repo-admin-protection": r"(?:enable|disable|add|set\s+up|remove)\s+(?:the\s+)?branch\s+"
                             r"protection|(?:create|update|delete)\s+(?:a\s+|the\s+)?ruleset",
    "repo-admin-delete": r"delete\s+(?:the\s+)?(?:release|gist)(?![\w-])",
    "delete": r"(?:delete|remove)\s+(?:(?:the|that|this|my|last)\s+)*comment(?=\s*$|\s+(?:from|on|"
              r"in)\s+(?:the\s+)?(?:task|ticket|issue|tracker))",
    "destructive": r"delete\s+(?:the\s+|this\s+)?(?:task|issue|ticket)",
}
# A typed git/gh command counts only when it is the whole list item ("git push", "git commit
# это") — not when it is mentioned ("почему git push упал", "объясни gh pr create").
LITERAL = [(re.compile(r"git\s+commit\b"), "commit"), (re.compile(r"git\s+push\b"), "push"),
           (re.compile(r"git\s+(?:pull|reset)\b"), "history"),
           (re.compile(r"gh\s+pr\s+create\b"), "pr"), (re.compile(r"gh\s+pr\s+merge\b"), "merge"),
           (re.compile(r"gh\s+issue\s+create\b"), "create-task")]
LITERAL_ARGS = re.compile(r"(?:\s+(?:[!-~]+|это|все|всё|пожалуйста|плиз|плз))*")
SQUASH = re.compile(r"(?<![\w-])(?:засквошь|сквошни|схлопни|squash)(?![\w-])")
BARE = {"коммит": "commit", "commit": "commit", "пуш": "push", "push": "push", "pr": "pr",
        "пр": "pr", "pull request": "pr", "пулл реквест": "pr", "пул реквест": "pr",
        "пулреквест": "pr", "mr": "pr", "мр": "pr", "merge request": "pr"}
SEGMENT_STATUS = re.compile(r"^(?:\S+\s+)?(?:(?:probe|fix|full)\s+)?в\s+(?:ревью|review|работу)$")

TAGS = {"commit": "commit", "merge-local": "merge-local", "push": "push", "pr": "pr",
        "merge": "merge", "force-push": "force", "reset": "history",
        "status": "status", "create-task": "create-task", "tracker-edit": "tracker",
        "delete-task": "destructive", "delete-comment": "delete"}
# [publish] and [repo-admin] grant the objects their option's label names; naming none grants nothing
LABEL_OBJECTS = {
    "publish": {
        "publish-release": r"(?<!\w)(?:релиз(?:а|ы|ов)?|releases?)(?![\w-])",
        "publish-repo": r"(?<!\w)(?<!в )(?<!во )(?<!in )(?<!to )" + REPO_WORD,
        "publish-gist": r"(?<!\w)(?:гист(?:а|ы)?|gists?)(?![\w-])"},
    "repo-admin": {
        "repo-admin-settings": r"видим|visib|публичн|(?<!\w)public(?!\w)|приватн|private|"
                               r"переимен|renam|архив|archiv",
        "repo-admin-secrets": r"секрет|secret|переменн|variable|deploy.?key|деплой.?ключ",
        "repo-admin-ci": r"workflow|воркфло|(?<!\w)ci(?!\w)|пайплайн|pipeline|джоб|(?<!\w)jobs?"
                         r"(?!\w)",
        "repo-admin-protection": r"защит|protect|ruleset",
        "repo-admin-delete": r"(?:удал|delet)\w*\s+(?:\S+\s+)?(?:релиз|release|гист|gist)"},
}
LABEL_OBJECTS = {tag: {a: re.compile(rx, re.I) for a, rx in objs.items()}
                 for tag, objs in LABEL_OBJECTS.items()}
TAG_RE = re.compile(r"\[(" + "|".join(re.escape(t) for t in sorted(
    list(TAGS) + list(LABEL_OBJECTS), key=len, reverse=True)) + r"|post)\]", re.I)
REPO_ADMIN = {"repo-admin-settings", "repo-admin-secrets", "repo-admin-ci",
              "repo-admin-protection", "repo-admin-delete"}
# create-task is not used up: one command covers the batch of tasks the dialog agreed on, which a
# tracker without a bulk operator creates one call per task
CONSUMED_BY_USE = {"commit", "merge-local", "push", "pr", "merge", "force", "publish-release",
                   "publish-repo", "publish-gist", "history", "status", "tracker", "destructive",
                   "delete"} | REPO_ADMIN


def normalize_text(s):
    return s.lower().replace("ё", "е")


def sentences(text):
    return [s for s in re.split(r"(?<=[.!?;])\s+|\n+", text) if s.strip()]


DETECT_EDGE = 4096  # detect() reads this much from each end of a long message
URL = re.compile(r"[a-z][a-z0-9+.-]{0,15}://\S{0,2048}")
FENCE = re.compile(r"^[ \t]*(`{3,}|~{3,}).*?(?:^[ \t]*\1[ \t]*$|\Z)", re.M | re.S)


def typed_lines(text):
    """The text a user typed, without what they pasted: fenced blocks and `>` quoted lines."""
    if len(text) > 2 * DETECT_EDGE:  # a pasted log: its middle is not an order, and regexes
        text = text[:DETECT_EDGE] + "\n" + text[-DETECT_EDGE:]  # stay within the hook timeout
    text = FENCE.sub("\n", text)
    return "\n".join(ln for ln in text.split("\n") if not ln.lstrip().startswith(">"))


def detect(text):
    """Actions a typed message orders. Conservative: when in doubt, nothing."""
    text = PAIR.sub(r"\1, ", URL.sub(" ", normalize_text(typed_lines(text))))
    found = set()
    for sent in sentences(text):
        sent = " ".join(sent.split())  # one space between words keeps SPLIT linear
        if COND.search(sent) or CANCEL.search(sent):
            continue
        sent = re.sub(r"(?<![\w'])потом(?=\s*(?:[,.;!?]|$))", " позже", sent)
        added, at_start, no_push = set(), set(found), False
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
                no_push = no_push or bool(re.search(r"пуш|push", seg_clean))
                added = set()
                continue
            before = set(found)
            core = LEAD.sub("", seg_clean.strip()).strip()
            for pattern, action in LITERAL:
                m = pattern.match(core)
                if m and not question and LITERAL_ARGS.fullmatch(core[m.end():]):
                    found.add(action)
                    args = core[m.end():].split()
                    if action == "push" and push_kind(args, look=False) == "force":
                        found.add("force")
            for action, pattern in RU_IMPERATIVE.items():
                if re.search(r"(?<![\w-])(?:" + pattern + r")(?![\w-])", core):
                    found.add(action)
            if polite or remind:
                for action, pattern in RU_INFINITIVE.items():
                    if re.search(r"(?<![\w-])(?:" + pattern + r")(?![\w-])", core):
                        found.add(action)
            if not question or polite:  # "commit?" asks; "could you commit it?" orders
                en = POLITE_LEAD.sub("", core) if polite else core
                for action, pattern in EN_IMPERATIVE.items():
                    if re.match(r"(?:" + pattern + r")", en):
                        found.add(action)
            if SEGMENT_STATUS.match(core) and not question:
                found.add("status")
            if core in BARE and not question and not sent_negative:
                found.add(BARE[core])
            if "commit" in found - before and SQUASH.search(core):
                found.add("history")  # squashing several commits needs reset --soft
            added = found - before
        if no_push:  # «залей в мейн, но не пушь»: the merge stays local
            found -= {"push", "force"} - at_start
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


def is_queued(entry):
    return entry.get("type") == "attachment"


MAX_QUEUED = 8


def scan_back(transcript_path, max_bytes=64 << 20):
    """Return (human_entry or None, entries after it in order, saw_origin, truncated).

    A message the user queued while the model was busy does not end the scan: the scan goes on to
    the message typed before it, and the queued ones stay in the entries, where they were read."""
    after, saw_origin, human, queued = [], False, None, 0
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
                    if is_queued(entry) and queued < MAX_QUEUED:
                        queued += 1
                        after.append(entry)
                        continue
                    human = entry
                    break
                if entry.get("type") in {"assistant", "user"} and not entry.get("isSidechain"):
                    after.append(entry)
    after.reverse()
    if human is None and queued and pos == 0:  # the transcript starts with a queued message
        first = next(i for i, e in enumerate(after) if is_queued(e))
        human, after = after[first], after[first + 1:]
    return human, after, saw_origin, human is None and pos > 0


STOP = re.compile(r"(?<![\w'])(?:подожди\w*|погоди\w*|стой(?:те)?|wait|hold|отставить|halt)"
                  r"(?![\w'])")


BARE_STOP = re.compile(r"(?:стоп|стой(?:те)?|нет|не\s+надо|не\s+нужно|no|nope|stop|halt|отмена|"
                       r"отбой|don'?t|do\s+not|"
                       r"cancel|отставить|hold(?:\s+on)?|wait|подожди\w*|погоди\w*)")
NO_LEAD = re.compile(r"^(?:(?:no|nope|нет|не|ой|oh|oops)[,\s]+)+")
NONE = re.compile(r"(?<![\w'])(?:никак\w*|ничего|nothing|none|no\s+more)(?![\w'])")
GATED_WORDS = re.compile(r"(?:комм?ит|commit|мерд?ж|merge|пуш|push|зал[еи]|вле|форс|force|\bpr\b|"
                         r"\bпр\b|пулл|pull|реквест|request|статус|status|ревью|review|сброс|"
                         r"reset|подтян|стэш|стеш|stash|откат|revert|restore|clean|удали|delete|"
                         r"коммент|comment|пост|post|опубликуй|publish|задач|task|ветк|branch|"
                         r"main|master|мейн|мастер)")


# a change of plan, whatever it names: the user takes the step over, wants something done or
# shown first, or changed their mind
REPLAN = re.compile(r"(?<![\w'])(?:передумал\w*|раздумал\w*|я\s+(?:\w+\s+){0,2}сам[аи]?|"
                    r"сначала|сперва|для\s+начала|"
                    r"перед\s+(?:коммит\w*|пуш\w*|мерд?ж\w*|этим|тем)|"
                    r"дай(?:те)?\s+(?:\S+\s+)?(?:посмотреть|глянуть|взглянуть|проверить|"
                    r"почитать)|дай(?:те)?\s+(?:я\s+)?(?:гляну|посмотрю|проверю|взгляну|почитаю)|"
                    r"давай(?:те)?\s+я\s+\S*(?:у|ю)|i'?ll\s+do\s+it|i\s+will\s+do\s+it|"
                    r"не\s+надо|first|myself|changed\s+my\s+mind|never\s?mind|"
                    r"let\s+me\s+(?:see|look|check|review|do)|hold\s+off)(?![\w'])")
# «сам закоммичу», «сам всё запушу», «сам разберусь», «закоммичу сам» — first person by the
# verb's -у/-ю(сь), which a noun shares («сделай всю работу сам»): a clause that also addresses
# the model (an imperative, «ты», «вы») is the model told to do it alone, as are «сделай сам» /
# «давай сам» / «пушни ветку сам», and holds nothing back
SELF = re.compile(r"(?<![\w'])(?:сам[аи]?\s+(?:\S+\s+){0,2}\S*(?:у|ю)(?:сь)?|"
                  r"\w+(?:у|ю)(?:сь)?\s+(?:\w+\s+)?сам[аи]?)(?![\w'])")
# an imperative: -ай/-яй/-уй, -лей (залей), -[шжт]ни (пушни, мержни), -ите, -ь except -усь/-юсь
# (разберусь) and the words listed; and their -те forms
YOU = re.compile(r"(?<![\w'])(?:ты|вы|\w+(?:[аяу]й|[шжт]ни)(?:те)?|\w*лей(?:те)?|"
                 r"(?!(?:теперь|опять|чуть|день|путь|ветвь|здесь|весь|ведь|вновь|лишь|пусть|"
                 r"мой|твой|свой)(?![\w'])|\w*[ую]сь(?![\w']))\w+ь(?:те)?|\w+ите)(?![\w'])")


def takes_over(text):
    """The user says they do the step themselves (SELF, in a clause that addresses no one)."""
    for clause in re.split(r"[,.;!?…:()]|\s(?:а|но|и)\s", text):
        if SELF.search(clause) and not YOU.search(clause):
            return True
    return False


def revokes(text):
    """A queued message that holds back a command: a list item that negates, cancels or defers
    a gated action («не коммить пока», «пуш позже»), a bare «не сейчас» / «позже», one that is
    or starts with a stop word («стоп», «подожди», wait), or a change of plan whatever it names
    (REPLAN: «я передумал», «сначала покажи дифф», "first show me the diff", «дай посмотреть»,
    «не надо»; takes_over: «сам закоммичу», but not «сделай сам»). «тесты не трогай» holds back
    nothing the guard gates."""
    t = " ".join(PAIR.sub(r"\1, ", URL.sub(" ", normalize_text(typed_lines(text)))).split())
    if REPLAN.search(t) or takes_over(t):
        return True
    for sent in sentences(t):
        for raw in SPLIT.split(sent.strip(" .!?;")):
            seg = raw.strip(" .!?;\"'«»()")
            core = LEAD.sub("", seg).strip()
            if not core:
                continue
            led = NO_LEAD.sub("", core)  # "no wait", «нет, стой»
            if BARE_STOP.fullmatch(core) or TAIL.fullmatch(core) or STOP.match(core) or \
                    led != core and (BARE_STOP.fullmatch(led) or STOP.match(led)):
                return True
            seg_clean = REMIND.sub(" ", seg)
            if (NEG.search(seg_clean) or NONE.search(seg) or CANCEL.search(seg)
                    or DEFER.search(seg)) and \
                    GATED_WORDS.search(seg):
                return True
    return False


# a call a hook or the permission flow stopped before it ran
NOT_RUN = re.compile(r"\[ticket guard\] Blocked|^PreToolUse:|hook error|"
                     r"Permission to use \S+ (?:has been|was) denied", re.I | re.M)
# an MCP server that plainly refused the call: nothing was written. Read at the head of the
# error only, where the code and the server's verdict stand — an error that echoes the request
# ("crash when asset not found") or a timeout "after 400 ms" is not a refusal
REFUSED = re.compile(
    r"^(?:<tool_use_error>\s*)?(?:(?:MCP\s+)?error\b[^:\n]{0,40}:\s*)?(?:"
    r"InputValidationError|validation\s+(?:error|failed)|invalid\s+(?:argument|param|input|"
    r"request|arguments|parameters)|bad\s+request|unauthori[sz]ed|forbidden|"
    r"(?:HTTP\s*|status(?:\s+code)?:?\s*)?4(?:00|01|03|04|05|09|10|22)\b|"
    r"(?:\S+\s+){0,2}(?:not\s+found|does\s+not\s+exist|is\s+required)\b)"
    r"|^(?:<tool_use_error>\s*)?MCP\s+error\s+-32602\b|InputValidationError|"
    r"\b(?:HTTP|status(?:\s+code)?:?)\s*4(?:00|01|03|04|05|09|10|22)\b", re.I)


def executed(block, call=None):
    """Whether a tool result means the call may have done its work. A call the guard denied and
    one the user rejected or interrupted did not. A shell command that failed (`is_error`: a
    non-zero exit, a rejected push, a hook that refused the commit) did not when its failure
    must be the gated part's own (see `error_is_own`). An MCP call that failed did only if the
    server did not plainly refuse it: a timeout or an unclear error may have landed the write."""
    text = result_text(block).lstrip()
    if text.startswith(("The user doesn't want to proceed", "[Request interrupted by user")):
        return False
    if not block.get("is_error"):
        return True
    if NOT_RUN.search(text[:2000]):
        return False
    call = call or {}
    if call.get("name") in {"Bash", "Monitor"}:
        return not error_is_own((call.get("input") or {}).get("command") or "")
    if str(call.get("name", "")).startswith("mcp__"):
        return not REFUSED.search(text.split("\n", 1)[0][:300])
    return False


def error_is_own(command):
    """Whether a failed shell command's exit status can only come from a step that did nothing:
    one simple command, or an `&&` chain whose gated step is the last one (redirects allowed). In `git push; false`
    or `git push && npm test` the push may have gone through before the failure."""
    command, fed, _ = strip_heredocs(command)  # `git commit -F - <<EOF` is one command
    if fed:
        return False
    subst = re.compile(r"\$\(([^()`]*)\)|`([^`]*)`")
    while subst.search(command):  # `-m "$(cat <<EOF …)"`: a substitution that gates nothing
        m = subst.search(command)
        if classify_shell(m.group(1) if m.group(1) is not None else m.group(2), None):
            return False
        command = command[:m.start()] + "x" + command[m.end():]
    if "`" in command or "$(" in command or "\n" in command.strip():
        return False
    try:
        lexer = shlex.shlex(command, posix=True, punctuation_chars=";&|()<>")
        lexer.whitespace_split = True
        lexer.commenters = ""
        tokens = list(lexer)
    except ValueError:
        return False
    segments, segment = [], []
    for token in tokens:
        if token and set(token) <= set("<>&") and set(token) & set("<>"):
            continue  # a redirect (`2>&1`, `> log`) keeps the exit status
        if token and set(token) <= set(";&|()<>"):
            if token != "&&":
                return False  # `;`, `||`, a pipe, a background job or a subshell
            segments.append(segment)
            segment = []
        else:
            segment.append(token)
    if not segment:
        return False
    return not any(classify_shell(shlex.join(seg), None) for seg in segments)


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
    calls, replay = {}, {"replay": True}
    for entry in after:
        if is_queued(entry):  # queued mid-turn: adds its orders, or holds everything back
            text = queued_text = human_text(entry)
            if revokes(queued_text):  # it voids every command so far and grants nothing itself
                actions, approved, typed = set(), set(), set()
                continue
            granted = detect(queued_text)
            actions |= granted
            typed |= granted
            continue
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
                    if not call or not executed(b, call):
                        continue
                    for item in classify(call.get("name", ""), call.get("input") or {}, cwd,
                                         state=replay):
                        if item[0] in CONSUMED_BY_USE:
                            actions.discard(item[0])
                        elif item[0] == "base-sync" and "merge-local" not in actions:
                            actions.discard("commit")  # under merge-local it is part of the merge
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
                if tag in LABEL_OBJECTS:
                    granted |= {a for a, rx in LABEL_OBJECTS[tag].items()
                                if rx.search(TAG_RE.sub(" ", pick))}
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


# short options that take a value, per git subcommand: in a bundle, the rest after one of these
# letters is its value (`push -on` is push-option "n", not a dry run)
SHORT_WITH_VALUE = {
    "push": "o", "clean": "e", "commit": "mFcCtS", "merge": "mFsXS", "rebase": "sXSx",
    "cherry-pick": "mXS", "revert": "mXS", "checkout": "bB", "switch": "cC", "branch": "u",
    "restore": "s", "stash": "m", "tag": "mFu", "am": "pSC",
}


def expand_flags(args, sub=None):
    """`-fu` → `-f`, `-u`: git accepts bundled short flags. The bundle ends at a letter that
    takes a value (SHORT_WITH_VALUE[sub]); the rest of the bundle is that value."""
    valued, out = SHORT_WITH_VALUE.get(sub, ""), []
    for a in args:
        if re.fullmatch(r"-[A-Za-z]{2,}", a):
            for i, c in enumerate(a[1:], 2):
                out.append("-" + c)
                if c in valued:
                    out.append(a[i:])  # the value as its own word, as `-o n` would give
                    break
        else:
            out.append(a)
    return out


PUSH_OPTS_WITH_VALUE = {"-o", "--push-option", "--repo", "--receive-pack", "--exec"}


def push_kind(rest, cwd=None, dash_c=None, look=True):
    """"push", "force" (rewrites or targets a base branch) or None (a dry run)."""
    rest = expand_flags(rest, "push")
    flags = [a for a in rest if a.startswith("-")]
    if {"--dry-run", "-n"} & set(flags):
        return None
    if any(f in {"-f", "--force", "--delete", "-d", "--mirror", "--prune", "--all", "--branches",
                 "--tags"}
           or f.startswith(("--force-with-lease", "--force-if-includes")) for f in flags):
        return "force"
    positional, skip = [], False
    for a in rest:
        if skip:
            skip = False
        elif a in PUSH_OPTS_WITH_VALUE:
            skip = True
        elif not a.startswith("-"):
            positional.append(a)
    bases = base_set(cwd, dash_c) if look else BASE_BRANCHES
    for spec in positional[1:]:
        dst = spec.split(":", 1)[-1]
        if spec.startswith(("+", ":")) or dst.replace("refs/heads/", "") in bases:
            return "force"
    if look and all(p in {"HEAD", "@"} for p in positional[1:]) and \
            git_query(["symbolic-ref", "-q", "--short", "HEAD"], cwd, dash_c) in bases:
        return "force"  # no destination named and the checkout is on the base branch
    return "push"


def default_branch(cwd, dash_c):
    out = git_query(["symbolic-ref", "-q", "--short", "refs/remotes/origin/HEAD"], cwd, dash_c)
    return out.split("/", 1)[-1] if out else None


def base_set(cwd, dash_c):
    """Branch names that count as a base branch here: the usual names, the remote's default
    branch and the `base_branch:` of this session's run."""
    return BASE_BRANCHES | run_base_branches() | ({default_branch(cwd, dash_c)} - {None})


def names_base(ref, bases):
    """`main`, `origin/main`, `refs/heads/main`, `refs/remotes/upstream/main` name a base."""
    ref = re.sub(r"^refs/(?:heads|remotes)/", "", ref)
    return ref in bases or "/" in ref and ref.split("/", 1)[1] in bases


RUN_BASE = re.compile(r"^[ \t>*-]*`?base[_ ]branch`?\s*:\s*`?([^\s`]+)", re.M | re.I)


def run_base_branches():
    """The `base_branch:` in this session's RUN.md (RUN_DIR). No run recorded — none: another
    task's RUN.md in the same repository says nothing about this one."""
    if not RUN_DIR:
        return set()
    try:
        with open(os.path.join(RUN_DIR, "RUN.md"), encoding="utf-8", errors="replace") as f:
            head = f.read(8192)
    except OSError:
        return set()
    found = set()
    for m in RUN_BASE.finditer(head):
        branch = m.group(1).strip("`'\"").replace("refs/heads/", "")
        if branch and branch not in {"HEAD", "(detached)"}:
            found.add(branch)
    return found


def git_ref(arg, cwd, dash_c):
    return bool(git_query(["rev-parse", "-q", "--verify", "--end-of-options", arg + "^{commit}"],
                          cwd, dash_c))


def classify_git(args, cwd, depth, inline, state=None):
    """What `git <args>` does. `state` carries the branch an earlier `git switch` / `git
    checkout` of the same command moved to."""
    state = {} if state is None else state
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
    if "$" in sub or "`" in sub:
        return [("opaque", f"`git {sub} …`: a git subcommand built from a variable or a "
                           "substitution")]
    if sub not in GIT_BUILTINS and depth < 3:
        alias = git_alias(sub, cwd, dash_c, inline)
        if alias:
            if alias.startswith("!"):
                return classify_shell(alias[1:] + " " + " ".join(shlex.quote(a) for a in rest),
                                      cwd, depth + 1)
            return classify_git(shlex.split(alias) + rest, cwd, depth + 1, inline, state)
    flags = set(expand_flags(rest, sub))
    before_dashdash = rest[:rest.index("--")] if "--" in rest else rest
    after_dashdash = rest[rest.index("--") + 1:] if "--" in rest else []
    positional = [a for a in before_dashdash if not a.startswith("-")]
    if sub in {"switch", "checkout"} and positional and "--" not in rest:
        state["branch"] = state["here"] = positional[0]
    if sub in GIT_HISTORY:
        if flags & NON_WRITING or (sub in {"cherry-pick", "revert"} and "-n" in flags):
            return []
        if sub in {"merge", "rebase"}:
            return classify_integration(sub, rest, positional, cwd, dash_c, state)
        if state.get("here") and names_base(state["here"], base_set(cwd, dash_c)):
            # `git switch main && git cherry-pick task/1-x`: integrating into the base branch
            return [("merge-local", f"git {sub} on {state['here']} after switching to it")]
        if sub == "commit" and not state.get("replay") and git_query(
                ["rev-parse", "-q", "--verify", "MERGE_HEAD"], cwd, dash_c):
            head = state.get("branch") or git_query(["symbolic-ref", "-q", "--short", "HEAD"],
                                                    cwd, dash_c)
            if head and names_base(head, base_set(cwd, dash_c)):
                # concluding a merge into the base branch that stopped on a conflict
                return [("merge-local", f"git commit concluding a merge into {head}")]
        return [("commit", f"git {sub}")]
    if sub == "push":
        kind = push_kind(rest, cwd, dash_c)
        label = "git push (force, delete, all/tags/mirror or to the base branch)" \
            if kind == "force" else "git push"
        return [(kind, label)] if kind else []
    if sub in {"send-pack", "http-push", "send-email"}:
        return [("push", f"git {sub}")]
    if sub == "submodule" and "foreach" in rest:
        return classify_shell(" ".join(rest[rest.index("foreach") + 1:]), cwd, depth + 1)
    if sub in {"subtree", "lfs"} and "push" in rest:
        return [("push", f"git {sub} push")]
    if sub == "pull" and len(positional) >= 2 and not any(":" in r for r in positional[1:]):
        bases = base_set(cwd, dash_c)
        head = state.get("branch") or (None if state.get("replay") else git_query(
            ["symbolic-ref", "-q", "--short", "HEAD"], cwd, dash_c))
        if all(names_base(r, bases) for r in positional[1:]) and not (
                head and names_base(head, bases)) and (head or state.get("replay")):
            # `git pull origin main` on the task branch: the base catching up, as a merge
            return [("base-sync", f"git pull of the base branch into {head or 'the task branch'}")]
    if sub == "fetch" and positional[:1] == ["."] and any(
            ":" in r and names_base(r.split(":", 1)[1].lstrip("+"), base_set(cwd, dash_c))
            for r in positional[1:]):
        return [("merge-local", "git fetch . <branch>:<base> (fast-forwards the base branch)")]
    if sub in {"pull", "update-ref", "filter-branch", "filter-repo"}:
        return [("history", f"git {sub}")]
    if sub == "symbolic-ref" and len(positional) >= 2:
        return [("history", "git symbolic-ref")]
    if sub == "replace" and (len(positional) >= 2 or flags & {"-d", "--delete", "-f"}):
        return [("history", "git replace")]
    if sub == "reset":
        if flags & {"--hard", "--soft", "--merge", "--keep"} or any(
                re.match(r"^(?:HEAD[~^]\S*|@[~^]\S*|[0-9a-f]{7,40}|origin/\S+|@\{\S+\})$", a)
                or (a not in {"HEAD", "@"} and git_ref(a, cwd, dash_c)) for a in positional):
            return [("history", "git reset")]
    if sub == "branch" and flags & {"-D", "-f", "--force", "-M", "-C"}:
        return [("history", "git branch (force/delete)")]
    if sub == "checkout" and flags & {"-B"} or sub == "switch" and flags & {"-C",
                                                                          "--force-create"}:
        return [("history", f"git {sub} (reset a branch)")]
    if sub == "stash":
        action = rest[0] if rest and not rest[0].startswith("-") else "push"
        if action in {"drop", "clear", "pop", "apply", "branch"}:
            return [("history", f"git stash {action}")]
        if action in {"push", "save"}:
            return [("stash", "git stash")]
        return []
    # local changes thrown away: needs the same command as a reset
    if sub == "clean" and flags & {"-f", "--force"} and not flags & {"-n", "--dry-run"}:
        return [("history", "git clean (deletes untracked files)")]
    if sub in {"checkout", "switch"} and flags & {"-f", "--force", "--discard-changes"}:
        return [("history", f"git {sub} --force (discards changes)")]
    if sub == "checkout" and not flags & {"-b", "--orphan", "-p", "--patch"}:
        paths = after_dashdash if "--" in rest else [
            a for a in positional if not (git_ref(a, cwd, dash_c)
                                          or git_ref("origin/" + a, cwd, dash_c))]
        if paths:
            return [("history", "git checkout <paths> (discards changes)")]
    if sub == "restore" and not flags & {"-p", "--patch"} and (
            not flags & {"-S", "--staged"} or flags & {"-W", "--worktree"}):
        return [("history", "git restore (discards changes)")]
    return []


def classify_integration(sub, rest, positional, cwd, dash_c, state):
    """git merge / rebase: into a base branch (merge-local), a base branch into the task branch
    (base-sync), or any other history write (commit)."""
    valued = {"-m", "-F", "--file", "-s", "--strategy", "-X", "--strategy-option", "--onto",
              "-x", "--exec", "--message", "--into-name"}
    positional, skip = [], False
    for a in rest[:rest.index("--")] if "--" in rest else rest:
        if skip:
            skip = False
        elif a in valued:
            skip = True
        elif not a.startswith("-"):
            positional.append(a)
    bases = base_set(cwd, dash_c)
    head = state.get("branch") or git_query(["symbolic-ref", "-q", "--short", "HEAD"], cwd,
                                            dash_c)
    if sub == "rebase" and len(positional) >= 2:
        head = positional[1]  # `git rebase <upstream> <branch>` checks <branch> out first
    upstream = positional[:1] if sub == "rebase" else positional
    onto = option_value(rest, ["--onto"])
    names_a_base = any(names_base(r, bases) for r in upstream + ([onto] if onto else []))
    if state.get("replay") and not state.get("branch") and names_a_base:
        # replaying an earlier call: today's HEAD may not be the branch it ran on, and a base
        # merged into something is the task branch catching up
        return [("base-sync", f"git {sub} of the base branch into the task branch")]
    if head and names_base(head, bases):
        short = re.sub(r"^refs/heads/", "", head)
        own = re.compile(r"^(?:HEAD|@|" + re.escape(short) + r")(?:[~^]\d*)+$|^[0-9a-f]{7,40}$")
        if sub == "rebase" and not onto and ("--root" in rest or upstream and
                                             own.match(upstream[0])):
            # `git rebase -i HEAD~3` on main rewrites its own commits: no other branch comes in
            return [("commit", f"git rebase of {head}'s own commits")]
        if len(upstream) == 1 and not onto and re.sub(r"^refs/remotes/", "", upstream[0]) \
                .split("/", 1)[-1] == short and "/" in re.sub(r"^refs/remotes/", "", upstream[0]):
            # `git merge --ff-only origin/main` on main: bringing it up to date is a pull
            return [("history", f"git {sub} of {upstream[0]} into {head} (updates it, as a pull)")]
        return [("merge-local", f"git {sub} into {head}")]
    if names_a_base:
        return [("base-sync", f"git {sub} of the base branch into {head or 'this branch'}")]
    return [("commit", f"git {sub}")]


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


# gh groups that change a repository, its secrets or CI → the repo-admin kind each one is
GH_ADMIN_GROUPS = {"secret": "secrets", "variable": "secrets", "environment": "secrets",
                   "deploy-key": "secrets", "ssh-key": "secrets", "gpg-key": "secrets",
                   "workflow": "ci", "run": "ci", "cache": "ci", "ruleset": "protection",
                   "attestation": "settings", "repo": "settings"}
# gh api endpoints of repository, CI and account settings
GH_API_REPO = re.compile(
    r"^/?(?:repos/[^/]+/[^/]+/?$|orgs/[^/]+/?$|(?:user|orgs/[^/]+)/repos/?$|gists\b|"
    r"(?:repos/[^/]+/[^/]+|orgs/[^/]+|user)/(?:actions|secrets|variables|rulesets|hooks|keys|"
    r"gpg_keys|ssh_signing_keys|codespaces/secrets|dependabot|collaborators|pages|environments|"
    r"releases|deployments|forks|transfer|topics|branches/[^/]+/protection|tags/protection|"
    r"dispatches|vulnerability-alerts|automated-security-fixes|autolinks|properties|"
    r"interaction-limits|invitations)\b)")


def api_admin_kind(endpoint):
    """The repo-admin kind of a write to a repository, org or account settings endpoint."""
    if re.search(r"/(?:secrets|variables|environments|keys|gpg_keys|ssh_signing_keys)\b",
                 "/" + endpoint):
        return "repo-admin-secrets"
    if re.search(r"/(?:rulesets|protection)\b", endpoint):
        return "repo-admin-protection"
    if re.search(r"/(?:actions|dispatches|deployments)\b", endpoint):
        return "repo-admin-ci"
    return "repo-admin-settings"


def classify_gh(args, cwd, push_read=False):
    rest = list(args)
    while rest and rest[0].startswith("-"):
        rest = rest[2:] if rest[0] in {"-R", "--repo", "--hostname"} else rest[1:]
    if len(rest) < 2:
        return []
    group, verb, tail = rest[0], rest[1], rest[2:]
    if group == "api":
        return classify_gh_api(rest[1:], cwd)
    if "--push" in tail and not push_read:
        # `--push` may also be another flag's value (`--subject --push`): the command keeps
        # its own class too
        return [("push", f"gh {group} {verb} --push")] + classify_gh(args, cwd, True)
    if group == "release" and verb in {"create", "upload", "edit"}:
        return [("publish-release", f"gh release {verb}")]
    if group == "gist" and verb in {"create", "edit", "rename"}:
        return [("publish-gist", f"gh gist {verb}")]
    if group == "repo" and verb in {"create", "fork"}:
        return [("publish-repo", f"gh repo {verb}")]
    if group == "repo" and verb == "sync" or group == "pr" and verb == "update-branch":
        force = {"--force", "-f", "--rebase"} & set(expand_flags(tail))  # sync -f: hard reset
        return [("force" if force else "push", f"gh {group} {verb} (updates a branch)")]
    if group == "repo" and verb == "delete":
        return [("destructive", "gh repo delete")]
    if group in {"release", "gist"} and verb in {"delete", "delete-asset"}:
        return [("repo-admin-delete", f"gh {group} {verb}")]
    if group == "repo" and verb in {"deploy-key", "autolink"}:  # gh repo deploy-key add …
        group, verb = verb, (tail[0] if tail else "list")
    if group in GH_LOCAL_GROUPS or verb in GH_READ_VERBS or verb.startswith("-") or \
            group == "repo" and verb in {"set-default", "license", "gitignore", "credits"}:
        return []  # reads, local git config, templates
    if group in {"release", "gist"}:
        return [(f"publish-{group}", f"gh {group} {verb}")]
    if group in GH_ADMIN_GROUPS or group == "autolink":  # not tracker fields
        kind = GH_ADMIN_GROUPS.get(group, "settings")
        return [(f"repo-admin-{kind}", f"gh {group} {verb} (repository or CI settings)")]
    if group not in {"issue", "pr"}:  # gh project, label, workflow run, secret set, repo edit, …
        return [("tracker", f"gh {group} {verb}")]
    if group == "issue" and verb == "create":
        return [("create-task", "gh issue create")]
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
    if group == "issue" and verb in {"close", "reopen"}:
        found = [("status", f"gh issue {verb}")]
    else:
        found = [("tracker", f"gh {group} {verb}")]
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
    endpoint = re.sub(r"^https?://[^/]+/(?:api/v3/)?", "", endpoint)  # a full URL
    if endpoint == "graphql":
        queries = [a.split("=", 1)[1] for a in tail if a.startswith("query=")]
        if "--input" not in tail and queries and all(
                re.match(r"\s*(?:query\b[^{]*)?\{", q) and "mutation" not in q for q in queries):
            return []
        joined = " ".join(queries)
        if re.search(r"\b(?:update|archive|unarchive|transfer|cloneTemplate)Repository\b", joined):
            return [("repo-admin-settings", "gh api graphql (repository settings)")]
        if re.search(r"\b(?:create|update|delete)(?:BranchProtectionRule|RepositoryRuleset)\b",
                     joined):
            return [("repo-admin-protection", "gh api graphql (branch protection)")]
        if re.search(r"\bcreateRepository\b", joined):
            return [("publish-repo", "gh api graphql (createRepository)")]
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
    if method == "POST" and re.search(r"/issues/?$", endpoint):
        return [("create-task", f"gh api POST {endpoint}")]
    if "/git/refs" in endpoint:
        return [("force", f"gh api {method} {endpoint}")]
    if GH_API_REPO.search(endpoint):
        if method == "DELETE" and re.search(r"^/?repos/[^/]+/[^/]+/?$", endpoint):
            return [("destructive", f"gh api DELETE {endpoint}")]
        if method == "DELETE" and re.search(r"/releases\b|^/?gists\b", endpoint):
            return [("repo-admin-delete", f"gh api DELETE {endpoint}")]
        if re.search(r"^/?gists\b", endpoint):
            return [("publish-gist", f"gh api {method} {endpoint}")]
        if re.search(r"/releases\b", endpoint):  # also …/releases/<id>/assets, like gh release upload
            return [("publish-release", f"gh api {method} {endpoint}")]
        if re.search(r"^/?(?:(?:user|orgs/[^/]+)/repos|repos/[^/]+/[^/]+/forks)/?$", endpoint) \
                and method == "POST":
            return [("publish-repo", f"gh api {method} {endpoint}")]
        return [(api_admin_kind(endpoint), f"gh api {method} {endpoint} (repository settings)")]
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


def classify_shell(command, cwd, depth=0, state=None):
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
    for m in SUBST_PROGRAM.finditer(command):
        try:
            words = shlex.split(m.group(2))
        except ValueError:
            words = m.group(2).split()
        if plausibly_git(m.group(1), words):
            found.append(("opaque", "a program named by a command substitution that may be git"))
    try:
        segments = split_segments(command)
    except ValueError:
        return found + raw_scan(command, cwd, depth)
    per_segment, state = {}, {} if state is None else state
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
                found += classify_git(tokens[j + 1:], cwd, depth, {}, state)
            elif name == "gh":
                found += classify_gh(tokens[j + 1:], cwd)
            elif j > i and name in SHELLS and j + 2 < len(tokens) and \
                    re.fullmatch(r"-[a-z]*c[a-z]*", tokens[j + 1]):
                found += classify_shell(tokens[j + 2], cwd, depth + 1)  # find -exec sh -c '…'
        found += classify_http(prog, args)
        runner = re.sub(r"^\$\{?|\}$", "", prog) if "$" in tokens[i] else prog
        if "$" in tokens[i] and runner not in RUNNERS:
            carrier = next((args[j + 1] for j, a in enumerate(args[:-1])
                            if re.fullmatch(r"-[a-z]*c[a-z]*", a)), None)
            if carrier is not None:  # `$SHELL -c "git push"`: read the carried command too
                found += classify_shell(carrier, cwd, depth + 1)
            if plausibly_git(tokens[i], args):
                found.append(("opaque", f"`{tokens[i]} …`: a program named by a variable or a "
                                        "substitution that may be git"))
        if runner in RUNNERS and any(PUBLISH_TARGET.fullmatch(t)
                                     for t in runner_targets(runner, args)):
            found.append(("opaque", f"`{prog} {' '.join(args)[:60]}`: a project script that "
                                    "looks like it publishes"))
        for action in {item[0] for item in found[seg_start:]} & CONSUMED_BY_USE:
            per_segment[action] = per_segment.get(action, 0) + 1
    found += [("repeat", f"{n} × {a} in one call") for a, n in per_segment.items() if n > 1]
    return found


GIT_VOCAB = re.compile(r"(?:push|commit|merge|rebase|reset|pull|cherry-pick|revert|stash|checkout|"
                       r"switch|restore|clean|filter-branch|update-ref)(?![a-z])", re.I)
GIT_WRITING = {"push", "commit", "merge", "rebase", "reset", "pull", "cherry-pick", "revert",
               "stash", "checkout", "switch", "restore", "clean", "filter-branch", "filter-repo",
               "update-ref", "am", "branch", "send-email", "send-pack", "symbolic-ref", "replace",
               "subtree", "submodule", "lfs", "commit-tree", "tag"}


GIT_GLOBAL_FLAGS = {"-p", "--paginate", "-P", "--no-pager", "--bare", "--no-replace-objects",
                    "--literal-pathspecs", "--glob-pathspecs", "--noglob-pathspecs",
                    "--icase-pathspecs", "--no-optional-locks", "--no-advice", "--no-lazy-fetch"}


EXPANSION = re.compile(r"\$\{[^}]*\}|\$\([^()]*(?:\([^()]*\)[^()]*)*\)|`[^`]*`|\$\w+")
# words in a variable or substitution that name a tool other than git, or a git setting
OTHER_TOOL_WORDS = {
    "editor", "pager", "ssh", "askpass", "dir", "root", "home", "config", "hooks", "toplevel",
    "work", "tree", "docker", "podman", "dotnet", "npm", "npx", "yarn", "pnpm", "bun", "node",
    "deno", "gradle", "gradlew", "mvn", "maven", "cargo", "go", "python", "python3", "py", "pip",
    "make", "cmake", "ninja", "unity", "kubectl", "helm", "bazel", "nuget", "msbuild",
    "xcodebuild", "swift", "java", "ruby", "gem", "bundle", "terraform", "aws", "gcloud", "az",
    "flutter", "dart", "conan", "brew", "hg", "svn", "p4", "rsync", "scp", "curl", "wget",
    "cc", "cxx", "gcc", "clang", "ld", "tar", "zip", "unzip", "sed", "awk", "grep", "find",
}


def plausibly_git(program, args):
    """Whether a program named by $VAR or $(…) may be git. A literal basename after the
    expansion decides by itself (`$ROOT/gradlew` is not git; `$ROOT/git` is read as git where
    it stands). A bare expansion whose words name git (`$GIT`, `${GIT_BIN}`, `$(which git)`)
    is git unless its first argument is a known read-only subcommand; one that names another
    tool (`$DOTNET`, `$DOCKER`, `$GIT_EDITOR`) is not; any other (`$CMD`, `$X`) is git when its
    first argument — after nothing but git's own global options — is a writing git
    subcommand. `$PY -m pytest -k checkout` and `$CC -o tag main.c` are not."""
    program = program.strip("\"'")
    marked = EXPANSION.sub("\0", program)
    if "/" in marked and "\0" not in marked.rsplit("/", 1)[1]:
        return False  # a literal basename: `git` there is classified as git directly
    words = {w.lower() for w in re.findall(r"[A-Za-z0-9]+", program)}
    i, global_only = 0, True
    while i < len(args) and args[i].startswith("-"):
        opt = args[i].split("=", 1)[0]
        if opt in GIT_OPTS_WITH_VALUE:
            i += 1 if "=" in args[i] else 2
        else:
            global_only = global_only and args[i] in GIT_GLOBAL_FLAGS
            i += 1
    first = args[i] if i < len(args) else ""
    if words & OTHER_TOOL_WORDS:
        return False
    if "git" in words:
        return bool(first) and (first in GIT_WRITING or first not in GIT_BUILTINS)
    return global_only and first in GIT_WRITING


RUNNERS = {"make", "gmake", "just", "task", "rake", "npm", "pnpm", "yarn", "bun", "mise"}
PUBLISH_TARGET = re.compile(r"push|publish|release|deploy|ship", re.I)  # whole target names
RUNNER_OPTS_WITH_VALUE = {"-C", "-f", "--file", "--makefile", "-I", "--include-dir", "-o",
                          "--old-file", "-W", "--what-if", "--assume-new", "--new-file", "-d",
                          "--dir", "--justfile", "--working-directory", "-t", "--taskfile",
                          "-r", "-R", "--prefix", "-w", "--workspace", "--filter", "-F", "--cwd",
                          "--dotenv-path", "--shell", "--color", "-E", "--env"}


def runner_targets(runner, args):
    """The target slot of a runner: every make / rake / task target, the first just recipe, the
    script after npm / pnpm / yarn / bun / mise `run` (or the first word: `npm publish`, `yarn
    release`) — not a test filter (`bun test push`) or a script's own arguments."""
    words, skip = [], False
    for a in args[:args.index("--")] if "--" in args else args:
        if skip:
            skip = False
        elif a.startswith("-"):
            skip = a in RUNNER_OPTS_WITH_VALUE
        elif not re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", a):
            words.append(a)
    if runner in {"make", "gmake", "rake", "task"}:
        return [w for w in words if not w.isdigit()]  # `make -j 4 push`
    if words and words[0] in {"run", "run-script", "rr", "r"} and runner != "just":
        return words[1:2]
    return words[:1]
TRACKER_PATH = re.compile(r"/rest/api/\d|/rest/agile/|/api/v\d+/(?:task|issue|projects)|"
                          r"/youtrack/api/|/api/issues", re.I)
WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def classify_http(prog, args):
    """curl, wget and httpie calls that write to a tracker API."""
    urls = [a for a in args if re.match(r"^(?:https?://)?[\w.-]+\.[a-z]{2,}(?:[:/]|$)", a, re.I)
            or "://" in a]
    if not any(TRACKER_SERVER.search(u) or TRACKER_PATH.search(u) for u in urls):
        return []
    write = False
    if prog == "curl":
        for j, a in enumerate(args):
            m = re.match(r"^(?:-X|--request)(?:=)?(\w*)$", a)
            if m:
                method = (m.group(1) or (args[j + 1] if j + 1 < len(args) else "")).upper()
                write = write or method in WRITE_METHODS
            elif re.match(r"^(?:-d|--data(?:-\w+)?|--json|-F|--form(?:-string)?|-T|--upload-file)"
                          r"(?:=|@|$)", a) or re.match(r"^-[dFT]\S", a):
                write = True
    elif prog == "wget":
        write = any(re.match(r"^--(?:post-data|post-file|body-data|body-file)(?:=|$)", a)
                    or re.match(r"^--method=?(?!get\b)(?!head\b)\w", a, re.I) for a in args)
    elif prog in {"http", "https", "xh", "xhs"}:
        positional = [a for a in args if not a.startswith("-")]
        method = positional[0].upper() if positional and positional[0].isalpha() else ""
        items = [a for a in positional if re.match(r"^[\w.\[\]-]*(?:=|:=|=@|:=@|@)", a)]
        write = method in WRITE_METHODS or (method != "GET" and bool(items))
    else:
        return []
    if not write:
        return []
    if any(re.search(r"/comments?\b", u) for u in urls):
        return [("comment", f"{prog} to a tracker comment API", None)]
    return [("tracker", f"{prog} to a tracker API")]


MCP_ADMIN_WORDS = [
    ("repo-admin-secrets", {"secret", "secrets", "variable", "variables", "key", "keys"}),
    ("repo-admin-protection", {"ruleset", "rulesets", "protection"}),
    ("repo-admin-ci", {"workflow", "workflows", "actions", "action", "dispatch", "rerun", "cache",
                       "caches", "job", "jobs", "pipeline", "pipelines"}),
]


def split_words(name):
    return set(re.split(r"[_\-\s]+", re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", name).lower()))


def nested_texts(value, key_ok=False):
    """String leaves whose own key names text (lists pass the key on; dicts do not)."""
    if isinstance(value, str):
        return [value] if key_ok else []
    if isinstance(value, dict):
        out = []
        for k, v in value.items():
            out += nested_texts(v, text_key(k))
        return out
    if isinstance(value, list):
        return [t for v in value for t in nested_texts(v, key_ok)]
    return []


def comment_candidates(item):
    texts = item[2] if len(item) > 2 else None
    if texts is None:
        return []
    return [texts] if isinstance(texts, str) else list(texts)


def comment_texts(inp):
    """Comment text a call would post: text-named string fields, plus nested rich text joined."""
    texts = [v for k, v in inp.items() if isinstance(v, str) and text_key(k) and v.strip()]
    nested = [t for t in nested_texts({k: v for k, v in inp.items() if not isinstance(v, str)})
              if t.strip()]
    if nested:
        texts.append("".join(nested))
    return texts


def classify_mcp(tool_name, tool_input):
    m = re.match(r"^mcp__(.+?)__(.+)$", tool_name)
    if not m:
        return []
    server, words = m.group(1), split_words(m.group(2))
    inp = tool_input if isinstance(tool_input, dict) else {}
    if GIT_SERVER.search(server):
        if "commit" in words:
            return [("commit", tool_name)]
        if "push" in words:
            return [("push", tool_name)]
        if words & {"reset", "rebase", "merge", "checkout", "stash", "restore", "clean"}:
            return [("history", tool_name)]
        if not TRACKER_SERVER.search(server) or words & {"git", "status", "diff", "log"}:
            return []
    if not TRACKER_SERVER.search(server):
        return []
    if {"execute", "operator"} <= words:
        return classify_operator(tool_name, inp)
    if {"resolve", "assignees"} <= words:
        return []
    request = words & {"request", "requests"}
    verbs = words - request - ({"merge"} if request else set()) if words & {"pull", "merge"} and \
        request else words
    if words & READ_WORDS and not verbs & WRITE_WORDS:
        return []
    has_text = any(isinstance(v, str) and v.strip() and text_key(k) for k, v in inp.items())
    reviewish = words & {"review", "thread", "comment", "comments", "note", "notes"}
    if re.search(r"github|gitlab|gitkraken", server, re.I) and not reviewish:
        if request and words & {"pull", "merge", "mr"} and "create" in words:
            return [("pr", tool_name)]
        if "merge" in words and (request or "mr" in words) and not words & {"update"}:
            return [("merge", tool_name)]
        # secrets, CI and protection first: create_repository_secret is no new repository
        for kind, names in MCP_ADMIN_WORDS:
            if words & names:
                return [(kind, tool_name)]
        objects = words & {"repository", "repo", "gist", "release", "releases"}
        kind = "publish-release" if objects & {"release", "releases"} else \
            "publish-gist" if "gist" in objects else "publish-repo"
        if objects and words & {"create", "fork", "publish"}:
            return [(kind, tool_name)]
        if objects and "delete" in words:
            return [("destructive" if kind == "publish-repo" else "repo-admin-delete", tool_name)]
        if objects and words & {"update", "edit"}:
            return [("repo-admin-settings" if kind == "publish-repo" else kind, tool_name)]
        if "push" in words or (words & {"file", "files", "branch", "tag"}
                               and words & {"create", "update", "delete", "push"}):
            return [("push", tool_name)]
    return classify_tracker_write(tool_name, words, inp, has_text)


def classify_tracker_write(name, words, inp, has_text):
    if words & COMMENT_WORDS or ("review" in words and has_text):
        if words & {"delete", "remove"}:
            return [("delete", name)]
        texts = comment_texts(inp)
        if texts:
            return [("comment", name, texts)]
        if words & {"create", "add", "post", "reply", "send", "write"}:
            return [("comment", name, None)]
    if words & {"delete", "remove", "archive", "merge"} and \
            words & {"task", "tasks", "issue", "issues", "page", "pages", "list", "folder",
                     "document", "doc", "docs", "project", "space"} and \
            not words & {"from", "tag", "tags", "label", "labels", "link", "links", "dependency",
                         "watcher", "watchers", "attachment", "requests"}:
        return [("destructive", name)]
    item = words & ITEM_WORDS
    if item and words & {"create", "add", "new", "duplicate"} and \
            not words & {"tag", "tags", "label", "labels", "link", "links", "dependency",
                         "watcher", "watchers", "attachment", "list", "time", "entry"}:
        return [("create-task", name)]
    if item and words & {"save", "upsert"} and not {"id", "issueId", "issue_id",
                                                     "identifier"} & set(inp):
        return [("create-task", name)]  # Linear save_issue without an id creates one
    if words & {"many", "bulk"}:
        return [("tracker", name)]
    changed = {k for k in inp if not id_key(k) or k in STATUS_KEYS}  # `stateId` is a change
    status_tool = bool(words & {"transition", "transitions"} or words & {"status", "state"} and
                       words & {"set", "update", "change", "move"} or
                       item and words & {"close", "reopen"})
    if changed <= STATUS_KEYS and (status_tool or changed and
                                   words & {"update", "edit", "save", "set", "upsert"}):
        return [("status", name)]
    texts = [v for k, v in inp.items() if re.match(r"comment", str(k), re.I) and
             isinstance(v, str) and v.strip()]
    extra = [("comment", f"{name} (comment)", texts)] if texts else []
    if status_tool or changed & STATUS_KEYS:
        return [("tracker", f"{name} (changes the status together with other fields — a "
                            "[status] command covers a call that changes only the status)")] + extra
    return [("tracker", name)] + extra


ITEM_WORDS = {"task", "tasks", "issue", "issues", "ticket", "tickets", "subtask", "subtasks",
              "story", "bug", "card"}
STATUS_KEYS = {"status", "state", "statusId", "stateId", "status_id", "state_id", "transition",
               "transitionId", "transition_id", "state_reason", "stateReason"}
ID_EXTRA = {"owner", "repo", "repository", "issue_number", "number", "key", "identifier",
            "issueIdOrKey", "custom_task_ids", "cloudId", "team_id", "workspace_id", "model",
            "operator"}


def id_key(key):
    """A key that names what is changed, not a change: `task_id`, `issueIdOrKey`, `owner`."""
    key = str(key)
    return bool(ID_KEY.search(key)) or key in ID_EXTRA or key.endswith("IdOrKey")


def word_list(name):
    """`Task.getMany` → ["task", "get", "many"]."""
    return [w for w in re.split(r"[_\-\s.]+", re.sub(r"([a-z0-9])([A-Z])", r"\1_\2",
                                                     name).lower()) if w]


def reads_only(model, operator):
    """An operator that only reads: get, list, get_many, getMany, Task.Get, get_comments,
    list_children, search — its first word after the model's own is a read word and none is a
    write word. The live catalog had no operators enabled to check these names against."""
    words, own = word_list(operator), set(word_list(model))
    if not words or set(words) & WRITE_WORDS:
        return False
    first = next((w for w in words if w not in own), words[0])  # `Task.Get` → get
    return words[0] in READ_WORDS or first in READ_WORDS


def classify_operator(name, inp):
    """clickup_execute_operator: a `<model>.<operator>` pair — reads pass, writes are judged by
    the pair as a dedicated tool of that name would be."""
    model, operator = str(inp.get("model") or ""), str(inp.get("operator") or "")
    label = f"{name} {model}.{operator}"
    if reads_only(model, operator):
        return []
    words = split_words(model) | split_words(operator)
    body = inp.get("body") if isinstance(inp.get("body"), dict) else {}
    if words & COMMENT_WORDS and operator not in {"delete", "delete_many"}:
        texts = comment_texts(body)
        return [("comment", label, texts or None)]
    return classify_tracker_write(label, words - {"children"}, body,
                                  bool(comment_texts(body)))


# --- tampering with the guard -------------------------------------------------------------

CONFIG_DIR = os.path.expanduser(os.environ.get("CLAUDE_CONFIG_DIR") or "~/.claude")
PLUGIN_ROOT = os.path.realpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
SETTINGS_NAME = re.compile(r"^(?:settings[^/]*|managed-settings)\.json$")


def settings_file(path, cwd=None):
    """Whether `path` is a Claude Code settings file: settings*.json in the config dir or in any
    `.claude` dir, or managed-settings.json — checked on the path as written and on its realpath,
    and against the realpaths of the known settings files (a dotfiles symlink target)."""
    if not path:
        return False
    written = os.path.abspath(os.path.join(cwd or os.getcwd(), os.path.expanduser(path)))
    real = os.path.realpath(written)
    config = {os.path.abspath(CONFIG_DIR), os.path.realpath(CONFIG_DIR)}
    for p in (written, real):
        name, parent = os.path.basename(p), os.path.dirname(p)
        if SETTINGS_NAME.match(name) and (name.startswith("managed-") or parent in config
                                          or os.path.basename(parent) == ".claude"):
            return True
    return real in known_settings(cwd)


_KNOWN_SETTINGS = {}


def known_settings(cwd):
    """Realpaths of the settings files that exist for this config dir and project."""
    if cwd not in _KNOWN_SETTINGS:
        dirs = [CONFIG_DIR, os.path.join(cwd or os.getcwd(), ".claude")]
        top = git_query(["rev-parse", "--show-toplevel"], cwd, None) if cwd else None
        if top:
            dirs.append(os.path.join(top, ".claude"))
        found = set()
        for d in dirs:
            try:
                names = os.listdir(d)
            except OSError:
                continue
            found |= {os.path.realpath(os.path.join(d, n)) for n in names
                      if SETTINGS_NAME.match(n)}
        _KNOWN_SETTINGS[cwd] = found
    return _KNOWN_SETTINGS[cwd]
DELETERS = {"rm", "rmdir", "unlink", "shred", "mv", "trash", "srm"}
MODIFIERS = {"truncate", "chmod", "chown", "chgrp", "chflags", "touch", "xattr", "setfacl", "tee"}
COPIERS = {"cp", "install", "ln", "rsync", "ditto", "scp"}  # the last argument is written
IN_PLACE = {"sed", "gsed", "perl"}
READERS = {"cat", "head", "tail", "less", "more", "ls", "stat", "file", "wc", "grep", "egrep",
           "fgrep", "rg", "ag", "test", "[", "echo", "printf", "readlink", "realpath", "du", "diff",
           "cmp", "jq", "sort", "uniq", "cut", "awk", "sed", "gsed", "tree", "md5", "md5sum",
           "shasum", "sha1sum", "sha256sum", "xxd", "od", "basename", "dirname", "cd", "pushd",
           "find", "true", "column", "nl", "strings", "hexdump", "bat", "fd", "eza", "exa", "tac",
           "cksum", "git", "gh", "open"}


def protected_paths(data):
    """(paths a call may not write, paths a call may not delete or move along with a parent)."""
    paths = [MARK_DIR, os.path.join(PLUGIN_ROOT, "skills", "ticket"),
             os.path.join(PLUGIN_ROOT, "hooks"), os.path.join(CONFIG_DIR, "plugins")]
    transcript = (data or {}).get("transcript_path")
    if isinstance(transcript, str) and transcript.endswith(".jsonl"):
        paths += [transcript, transcript[:-len(".jsonl")]]  # and its subagent transcripts
    return [os.path.realpath(os.path.expanduser(p)) for p in paths]


def session_marks(data):
    """Strings that name this session's transcript or the guard's markers wherever they appear."""
    session = re.sub(r"[^A-Za-z0-9_-]", "", (data or {}).get("session_id") or "")
    return ["task-runs/.guard"] + ([session + ".jsonl"] if len(session) >= 8 else [])


def resolve_path(token, cwd):
    token = re.sub(r"^\$\{?HOME\}?(?=/|$)", os.path.expanduser("~"), token)
    token = os.path.expanduser(token)
    if "$" in token or "`" in token:
        return None
    return os.path.realpath(os.path.join(cwd or os.getcwd(), token))


def touches(token, cwd, protected, deleting):
    """Whether writing (deleting, when `deleting`) the path `token` reaches a protected path."""
    path = resolve_path(token, cwd)
    if path is None:  # $VAR we cannot expand: judge by the words
        return bool(re.search(r"task-runs|\.guard|\.claude/plugins|/hooks|guard\.py|\.jsonl|"
                              r"settings", token)) and (deleting or "task-runs" not in token
                                                         or ".guard" in token)
    written = re.sub(r"^\$\{?HOME\}?(?=/|$)", os.path.expanduser("~"), token)
    if settings_file(written, cwd) or settings_file(path, cwd):
        return True
    glob = re.search(r"[*?\[]", path)
    if glob:
        base = os.path.dirname(path[:glob.start()] + "x")
        if touches(base + "/x", cwd, protected, False):
            return True
    for p in protected:
        if path == p or path.startswith(p + "/"):
            return True
        if deleting and p.startswith(path.rstrip("/") + "/"):
            return True
        if glob and any(fnmatch.fnmatchcase(c, path) for c in ([p] + (ancestors(p)
                                                                       if deleting else []))):
            return True
    return False


def ancestors(path):
    out = []
    while os.path.dirname(path) != path:
        path = os.path.dirname(path)
        out.append(path)
    return out


def shell_tokens(command):
    lexer = shlex.shlex(command.replace("\n", " ; "), posix=True, punctuation_chars=";&|()<>")
    lexer.whitespace_split = True
    lexer.commenters = ""
    return list(lexer)


def tamper_shell(command, cwd, protected, marks, depth=0):
    if depth > 4:
        return False

    def hits(token, cwd, protected, deleting):
        return any(m in token for m in marks) or touches(token, cwd, protected, deleting)

    command, fed, _ = strip_heredocs(command.replace("\\\n", " "))
    if any(tamper_shell(b, cwd, protected, marks, depth + 1) for b in fed):
        return True
    for inner in re.findall(r"\$\(([^()]*)\)|`([^`]*)`", command):
        if tamper_shell(inner[0] or inner[1], cwd, protected, marks, depth + 1):
            return True
    try:
        tokens = shell_tokens(command)
    except ValueError:
        return any(m in command for m in marks)
    segments, segment, redirect = [], [], False
    for t in tokens:
        if t and set(t) <= set(";&|()<>"):
            if ">" in t:
                redirect = True
                continue
            if "<" in t:
                continue
            if segment:
                segments.append(segment)
            segment = []
        elif redirect:
            redirect = False
            if not t.startswith("&") and hits(t, cwd, protected, False):
                return True
        else:
            segment.append(t)
    if segment:
        segments.append(segment)
    for seg in segments:
        i = skip_prefix(seg)
        if i >= len(seg):
            continue
        prog, args = os.path.basename(seg[i]).lower(), seg[i + 1:]
        paths = [a for a in args if not a.startswith("-")]
        if prog in {"cd", "pushd"} and paths:
            cwd = resolve_path(paths[0], cwd) or cwd
            continue
        if prog in SHELLS or prog == "eval" or "$" in seg[i]:  # `$SHELL -c "…"` too
            carrier = " ".join(args) if prog == "eval" else next(
                (args[j + 1] for j, a in enumerate(args[:-1])
                 if re.fullmatch(r"-[a-z]*c[a-z]*", a)), None)
            if carrier and tamper_shell(carrier, cwd, protected, marks, depth + 1):
                return True
        if prog in DELETERS and any(hits(a, cwd, protected, True) for a in paths):
            return True
        if prog in MODIFIERS and any(hits(a, cwd, protected, False) for a in paths):
            return True
        if prog in COPIERS and paths and hits(paths[-1], cwd, protected, False):
            return True
        if prog in IN_PLACE and any(re.match(r"^-[a-z]*i", a) or a.startswith("--in-place")
                                    for a in args) and \
                any(hits(a, cwd, protected, False) for a in paths):
            return True
        if prog == "dd" and any(a.startswith("of=") and hits(a[3:], cwd, protected, False)
                                for a in args):
            return True
        if prog == "find":
            roots = []
            for a in args:
                if a.startswith(("-", "(", "!")):
                    break
                roots.append(a)
            execs = [args[j + 1] for j, a in enumerate(args[:-1])
                     if a in {"-exec", "-execdir", "-ok", "-okdir"}]
            if ("-delete" in args or any(os.path.basename(e) in DELETERS | MODIFIERS
                                         for e in execs)) and \
                    any(hits(r, cwd, protected, True) for r in roots or ["."]):
                return True
        if prog == "claude" and {"plugin", "plugins"} & set(args) and not {
                "list", "validate", "--help", "-h"} & set(args):
            return True
        if prog == "git":
            dash_c = option_value(args, ["-C"])
            where = resolve_path(dash_c, cwd) if dash_c else os.path.realpath(cwd or os.getcwd())
            if where and any(where == p or where.startswith(p + "/") for p in protected) and \
                    GIT_VOCAB.search(" ".join(args)):
                return True
        if prog not in READERS | DELETERS | MODIFIERS | COPIERS and \
                any(m in a for a in args for m in marks):
            return True  # an interpreter or tool we do not know, pointed at the markers
    return False


HOOK_SETTINGS = ("hooks", "disableAllHooks", "enabledPlugins", "allowManagedHooksOnly")


def settings_change(tool_name, inp, path):
    """Whether a Write/Edit of a settings*.json changes what decides which hooks run. The file
    before and after the call are compared as JSON; text that does not parse counts as a change."""
    try:
        with open(path, encoding="utf-8") as f:
            before, missing = f.read(4 << 20), False
    except FileNotFoundError:
        before, missing = "{}", True
    except OSError:
        return True
    if tool_name == "Write":
        after = inp.get("content")
    elif tool_name == "Edit":
        old, new = inp.get("old_string"), inp.get("new_string")
        if not isinstance(old, str) or not isinstance(new, str):
            return True
        after = before
        if old == "":  # creates the file with new_string; fails on an existing one
            after = new if missing else before
        elif old in before:
            after = before.replace(old, new) if inp.get("replace_all") else \
                before.replace(old, new, 1)
        # an old_string that is not there: the Edit fails and changes nothing
    else:
        return True  # NotebookEdit on a settings file
    if not isinstance(after, str):
        return True
    try:
        a, b = json.loads(before or "{}"), json.loads(after or "{}")
    except ValueError:
        return True
    if not isinstance(a, dict) or not isinstance(b, dict):
        return True
    return any(a.get(k) != b.get(k) for k in HOOK_SETTINGS)


def tamper(tool_name, tool_input, data):
    inp = tool_input if isinstance(tool_input, dict) else {}
    protected, marks = protected_paths(data), session_marks(data)
    cwd = (data or {}).get("cwd")
    hit = False
    if tool_name in {"Bash", "Monitor"}:
        hit = tamper_shell(inp.get("command") or "", cwd, protected, marks)
    elif tool_name in {"Write", "Edit", "NotebookEdit"}:
        path = inp.get("file_path") or inp.get("notebook_path") or ""
        if isinstance(path, str) and path:
            resolved = resolve_path(path, cwd) or path
            if settings_file(path, cwd):
                hit = settings_change(tool_name, inp, resolved)
            else:
                hit = touches(path, cwd, protected, False) or any(m in resolved for m in marks)
    if hit:
        return [("tamper", f"{tool_name} on the guard itself, its markers, the session "
                           "transcript, the plugin install or the hooks settings")]
    return []


def classify_skill(tool_input):
    """A skill that posts what the guard cannot read: /code-review --comment, ultra --post."""
    inp = tool_input if isinstance(tool_input, dict) else {}
    name, args = str(inp.get("skill") or ""), str(inp.get("args") or "")
    if PUBLISH_FLAGS.search(args):
        return [("skill-post", f"Skill {name} {args[:60]}".strip())]
    return []


def classify(tool_name, tool_input, cwd, data=None, state=None):
    """What a call does. `state` (the replay of the transcript) carries the branch a replayed
    `git switch` moved to from one call to the next."""
    found = tamper(tool_name, tool_input, data) if data is not None else []
    if state is not None:
        state.pop("here", None)  # a switch in an earlier call is not a switch in this one
    if tool_name in {"Bash", "Monitor"}:
        found += classify_shell((tool_input or {}).get("command") or "", cwd, 0, state)
    elif tool_name.startswith("mcp__"):
        found += classify_mcp(tool_name, tool_input)
    elif tool_name == "Skill":
        found += classify_skill(tool_input)
    elif tool_name == "SendMessage":
        found.append(("delegate", "SendMessage to another agent or session"))
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
    "merge-local": ("«смерджи в мейн» / «залей в мейн»", "[merge-local]"),
    "base-sync": ("«закоммить» / «залей в мейн»", "[commit] or [merge-local]"),
    "push": ("«запушь»", "[push]"),
    "pr": ("«открой PR»", "[pr]"),
    "merge": ("«смержи PR»", "[merge]"),
    "force": ("«форс-пушь» / «запушь в main» / «залей в мейн»", "[force-push]"),
    "publish-release": ("«выпусти релиз»", "[publish] and names the release"),
    "publish-repo": ("«создай репо»", "[publish] and names the repo"),
    "publish-gist": ("«создай гист»", "[publish] and names the gist"),
    "repo-admin-settings": ("«сделай репо публичным» / «переименуй репо» / «заархивируй репо»",
                            "[repo-admin] and names that change (visibility, rename, archive)"),
    "repo-admin-secrets": ("«поставь секрет»", "[repo-admin] and names the secret or variable"),
    "repo-admin-ci": ("«запусти workflow»", "[repo-admin] and names the workflow"),
    "repo-admin-protection": ("«включи защиту ветки»", "[repo-admin] and names the protection"),
    "repo-admin-delete": ("«удали релиз» / «удали гист»",
                          "[repo-admin] and names deleting the release or gist"),
    "history": ("«сбрось» / «подтяни» / «верни стэш»", "[reset]"),
    "status": ("«переведи в ревью» / «закрой задачу»", "[status]"),
    "create-task": ("«создай задачу»", "[create-task]"),
    "tracker": ("«назначь на меня»", "[tracker-edit]"),
    "destructive": ("«удали задачу»", "[delete-task]"),
    "delete": ("«удали коммент»", "[delete-comment]"),
}


STEMS = {"commit": r"комм?ит|commit|мерд?ж|merge", "push": r"пуш|push|залей",
         "merge-local": r"мерд?ж|merge|зал[еи]|вле|мейн|main", "base-sync": r"комм?ит|commit|мерд?ж|merge|зал[еи]",
         "pr": r"\bpr\b|\bпр\b|пулл|pull", "status": r"статус|ревью|review|status|работу|закр|close",
         "create-task": r"созда|завед|задач|task|issue", "tracker": r"назнач|assign|задач|task",
         "publish-release": r"релиз|release|публик|publish",
         "publish-repo": r"репо|repo", "publish-gist": r"гист|gist",
         "repo-admin-settings": r"репо|repo|публичн|public|приватн|private|переимен|rename|архив|"
                                r"archive",
         "repo-admin-secrets": r"секрет|secret|переменн|variable|ключ|key",
         "repo-admin-ci": r"workflow|воркфло|ci\b|пайплайн|pipeline|джоб|job",
         "repo-admin-protection": r"защит|protect|ruleset",
         "repo-admin-delete": r"удали|delete",
         "merge": r"мерд?ж|merge", "force": r"форс|force|main|master|мейн|мастер",
         "history": r"сброс|reset|pull|подтян|стэш|стеш|stash|откат|restore|clean",
         "delete": r"удали|delete", "destructive": r"удали|delete"}


def decide(gated, text, actions, approved, used, unseen, failure):
    problems = []
    # what the latest message itself ordered (a change of plan in it orders nothing)
    ordered = detect(text) if text and not revokes(text) else set()
    for item in gated:
        action, what = item[0], item[1]
        if action == "tamper":
            problems.append(f"{what}: the guard's own state is off limits in a /ticket session.")
        elif action == "opaque":
            problems.append(f"{what}: the guard cannot tell what this runs. Write the git or gh "
                            "command out plainly, so it can be checked against the user's command.")
        elif action == "skill-post":
            problems.append(f"{what}: this skill would post to the PR or tracker text the guard "
                            "never sees. Run it without the posting flag and show the result; the "
                            "user posts it, or a comment goes through Task comments.")
        elif action == "delegate":
            problems.append(f"{what}: another session is outside this guard, so it is not a way "
                            "to run anything the guard refuses here.")
        elif action == "repeat":
            problems.append(f"{what}: one command is one action — split the call, each repeat "
                            "needs its own command.")
        elif action == "comment":
            texts = [normalize_comment(t) for t in comment_candidates(item)]
            if texts and all(t in approved for t in texts):
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
                    "full (publish.md, Task comments, step 4). Post the text unchanged.")
        elif action == "base-sync" and actions & {"commit", "merge-local"}:
            continue
        elif action not in actions:
            typed, tag = HOW[action]
            if action in ordered:
                problems.append(f"{what}: the user's latest message gave this command and it was "
                                "already used once since; another one needs a new command — typed "
                                f"(e.g. {typed}) or an AskUserQuestion option whose label carries "
                                f"{tag}.")
                continue
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


# The skill text names the same override (SKILL.md, "The run directory").
TASK_RUNS = os.path.expanduser(os.environ.get("KENSEI_TASK_RUNS_DIR") or "~/.claude/task-runs")
MARK_DIR = os.path.join(TASK_RUNS, ".guard")
MARK_TTL = 14 * 24 * 3600


def marker(session_id):
    safe = re.sub(r"[^A-Za-z0-9_-]", "", session_id or "")
    return os.path.join(MARK_DIR, safe) if safe else None


# this session's run directory: the one whose RUN.md the session last wrote, kept in its marker
RUN_DIR = None
RUN_WRITE = re.compile(r"(?:>>?|\btee(?:\s+-a)?)\s*[\"']?((?:[^\s\"';&|<>]*/)?RUN\.md)(?![\w.])")
CD = re.compile(r"(?:^|[;&|(]\s*)cd\s+[\"']?([^\s\"';&|<>()]+)")


def run_dir_of(path, cwd=None):
    """The run directory `path` is the RUN.md of (<runs root>/<repo>/<task>/RUN.md), or None."""
    if not isinstance(path, str) or os.path.basename(path) != "RUN.md":
        return None
    path = resolve_path(path, cwd)
    run = os.path.dirname(path or "")
    if path and os.path.dirname(os.path.dirname(run)) == os.path.realpath(TASK_RUNS) and \
            not os.path.basename(os.path.dirname(run)).startswith("."):
        return run
    return None


def note_run(session_id, tool_name, tool_input, cwd):
    """Record in the marker the run whose RUN.md this call wrote (Write / Edit, or a Bash
    redirect or tee into it; a bare RUN.md resolves against the last `cd` before it)."""
    tool_input = tool_input or {}
    paths = []
    if tool_name in {"Write", "Edit", "MultiEdit", "NotebookEdit"}:
        paths = [(tool_input.get("file_path"), cwd)]
    elif tool_name == "Bash":
        command = str(tool_input.get("command") or "")
        for m in RUN_WRITE.finditer(command):
            where = cwd
            for d in CD.finditer(command[:m.start()]):
                where = resolve_path(d.group(1), where) or where
            paths.append((m.group(1), where))
    path = marker(session_id)
    for p, where in reversed(paths):
        run = run_dir_of(p, where)
        if run and path and os.path.exists(path):
            with open(path, "w") as f:
                f.write(f"ticket session\nrun: {run}\n")
            return


def marked_run(session_id):
    path = marker(session_id)
    try:
        with open(path or "", encoding="utf-8", errors="replace") as f:
            m = re.search(r"^run: (.+)$", f.read(4096), re.M)
    except OSError:
        return None
    return m.group(1) if m else None


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


def deny(reason, decision="deny"):
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse",
                                             "permissionDecision": decision,
                                             "permissionDecisionReason": reason}}))


ASK_DELEGATE = ("[ticket guard] SendMessage hands work to another agent or session, which this "
                "guard does not watch. The user confirms it.")


def main():
    global RUN_DIR
    mode = sys.argv[1] if len(sys.argv) > 1 else "--main"
    raw = sys.stdin.read()
    try:
        data = json.loads(raw)
        tool_name = data.get("tool_name", "")
        session, agent = data.get("session_id"), data.get("agent_id")
        if mode == "--post":  # PostToolUse: the call ran, so its RUN.md is this session's run
            if not agent:
                note_run(session, tool_name, data.get("tool_input"), data.get("cwd"))
            return 0
        if mode == "--subagent":
            path = marker(session)
            if not agent or not path or not os.path.exists(path):
                return 0
        else:
            activate(session)
        cwd = data.get("cwd")
        RUN_DIR = marked_run(session)
        gated = classify(tool_name, data.get("tool_input") or {}, cwd, data)
        if not gated:
            return 0
        if agent:
            reason = subagent_reason(gated)
        else:
            gated = [g for g in gated if g[0] not in SUBAGENT_ONLY]
            if not gated:
                return 0
            if {g[0] for g in gated} == {"delegate"}:
                deny(ASK_DELEGATE, "ask")  # not refused: the user decides at the prompt
                return 0
            text, actions, approved, used, unseen, failure = read_authorization(
                data.get("transcript_path"), cwd)
            reason = decide(gated, text, actions, approved, used, unseen, failure)
    except Exception as exc:  # fail closed for anything that looks gated
        if not re.search(r"\bgit\b|\bgh\b|commit|push|merge|rebase|comment|status|mcp__|curl|"
                         r"\.guard|SendMessage|--comment|--post|settings|hooks", raw, re.I):
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
