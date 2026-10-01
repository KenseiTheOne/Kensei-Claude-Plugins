# Changelog

Versions are per plugin and live in each plugin's `.claude-plugin/plugin.json`. Release tags are
`<plugin>--v<version>` (`claude plugin tag`).

## kensei-toolkit 2.0.0 — 2026-10

Breaking: `ticket --unattended` is removed (see Removed), `todo` no longer writes a `TODO.md` unless
given its path, and the ticket guard has new answer tags (`[merge-local]`, `[create-task]`,
`[tracker-edit]`, `[publish]`, `[repo-admin]`) with `[status]` narrowed to the status field. Rolls up the hotfixes
planned as 1.8.2 and the ticket rework planned as 1.9.0.

### Removed
- **`ticket --unattended`** and everything that served it: `--task-id`, `unattended.md`, the
  `## Unattended` section, `caller-ticket.md`, `RESULT.json` (including the planned `contract: 2`)
  and the guard's unattended branch. The toolkit no longer carries a headless contract.
  **Migration:** the night runner gets its own `night:ticket` skill in its own repository; runner
  v1 keeps working by loading a frozen toolkit 1.8.0 copy with `--plugin-dir`. An old command that
  still passes `--unattended` (or any other `--` option) stops at Step 0 and says so, instead of
  running as an interactive run.

### learn
- Deduplicates against every place a takeaway could already live: project, nested and local
  `CLAUDE.md`, `~/.claude/CLAUDE.md` and the project's auto-memory (`MEMORY.md` as an index, the
  matching memory files opened before proposing).
- Routes each takeaway to one home: project `CLAUDE.md` for rules every contributor and headless
  run needs, the auto-memory for facts about the user (this project only), `~/.claude/CLAUDE.md`
  for preferences that hold in every project. Memory is written one fact per file with
  frontmatter, and `MEMORY.md` gets only a pointer line.
- Never proposes secrets, tokens, private or signed URLs, internal hostnames or third parties'
  personal data. With no project `CLAUDE.md`, the target `<repo root>/CLAUDE.md` is shown and
  created on approval.
- Selection is grouped by destination, every option is a real item (no All / None / Remaining)
  and every question has 2–4 options; Other rewords an item or moves it (`2: global`). Replies in
  the user's language. Still user-invoked only.
- Questions follow the same rule as todo: one question per destination, named in its text; more
  than 4 items split into balanced batches with no single-item batch; a single item is an
  Apply / Skip question. Argument text that is not a path narrows the review to that topic.

### todo
- **Breaking:** delivers to where the user already keeps tasks instead of a `TODO.md` it looked for
  or created: personal items to the Todoist Inbox (Todoist MCP or a CLI that is really Todoist,
  otherwise a paste-ready block), project work to ClickUp into a list the user picks in this run
  (read-only duplicate check first; no status, assignees, priority or dates unless asked). A
  markdown file is written only when its path is the argument; other argument text is a focus
  hint.
- Every draft carries an evidence line (quote or fact from the session); drafts are deduplicated
  and marked with a destination, `(?)` when it is a guess. Selection is multiSelect per
  destination, batches of up to 4 with no single-item batch, no All / None / Remaining; edits go
  through Other. Nothing is created before the user ticks it in this run. Still user-invoked only.
- **No built-in ClickUp workspace or server name.** The ClickUp tools are found on whichever server
  provides them (`clickup_*`); the workspace comes from the project rules, `CLAUDE.md` (project or
  personal) or the session's ClickUp task, otherwise from the workspace hierarchy, asking when
  there are several. Lists are looked up before the question, so drafts and the list choice come
  in one question. Without ClickUp it says so in one line and prints the drafts.
- Each ClickUp list option ends with `[create-task]`, the ticket guard's tag for creating tasks,
  so `/todo` works in a session where `/ticket` ran. A list typed through Other, or a draft moved
  to ClickUp by an edit, gets one confirmation («Create N tasks in <list>?») first.

### unity-review
- Rewritten as a Unity-specialist review: four lenses (Performance, Memory & lifecycle, Unity
  architecture, Platform) in modes `quick` (one agent, Critical and Warning only), `perf`, `arch`,
  `full`. **Changed meaning:** Code Quality, Bug Hunter and Security are gone — generic review is
  `/code-review`'s job, so `quick` no longer means "Code Quality + Bug Hunter".
- Arguments work: `[quick|perf|arch|full] [paths | ref | a..b] [focus]`. A mode named in words
  («проверь на перф», «по памяти», «полное ревью») counts as given; otherwise it is asked once,
  after the scope is known. Scope: uncommitted work with untracked files; on a clean tree, the
  branch's work against the default branch (diff-tour looks at the upstream first, unity-review
  does not); a ref, a range or paths. Paths in findings are relative to the repository root.
- Reviewers are read-only by allowlist: Read, Grep, Glob, ToolSearch only to load Unity MCP
  tools, read-only git and shell commands (`git diff` without `--output`, `find` without
  `-delete`/`-exec`), and Unity MCP tools whose name starts with `get_`, `find_`, `list_`, `read_` (plus `ping`,
  `status`); anything else (`open_scene`, `execute_menu_item`, `call_method`, dumps) is named in
  the report instead of called. The verifier gets the same paragraph word for word. Reviewers
  see the whole project for serialized references (GUIDs and field names of changed or deleted scripts), and every finding
  needs `path:line`, a failure scenario and a fix. A fresh agent tries to refute each finding;
  the report groups confirmed ones by severity, lists unconfirmed ones apart, and has no score.
- Project facts are read from files, not guessed: platforms from build profiles and the
  per-platform `ProjectSettings` maps, scripting backend, domain reload, Burst/Jobs only when an
  `.asmdef` or the code uses them.
- **A project review skill** (such as `pw-review`) stays the main review for a general request. When
  the skill was picked automatically and the user named a lens the project skill lacks («проверь на
  перф» in a project whose review skill has no performance category), those lenses run here, with
  one line saying the general review is the project skill's. Only Performance, Memory & lifecycle
  and Platform run here this way; an architecture-only request goes to a project skill that has an
  architecture category. A project's own "lifecycle" categories do not count as the Unity memory
  and lifecycle lens.
- Domain reload: Unity 6 still writes `m_EnterPlayModeOptionsEnabled` but no longer reads it; the
  skill reads the `DisableDomainReload` flag of `m_EnterPlayModeOptions` instead.
- Checklists moved to `lenses.md`, read only by the reviewer agents; `flow.md` is gone.

### ticket
- **Run notes stay out of the repository**, so a task commit no longer carries review files into
  the project's history. This reverses the 1.5.0 design choice that the basis of acceptance
  travels to origin with the commit: approved criteria and review files are no longer copied to
  `.task-runs/<id>/` and committed. They stay in the run dir and are named at the gate.
  They go into a commit only when the project sets `notes_path:` in `.claude/task-flow-rules.md`;
  a path under `.gitignore` is skipped with one line in the report.
- **One frame for every agent**, because the read-only Explore agent could not write its file:
  agents are `general-purpose`, so the context agent
  actually writes `01-context.md` (the orchestrator saves the reply there if it did not); the
  40-line reply cap stays, justified once; models are inherited from the session unless project
  rules name one for a role. `general-purpose` is required only for the agents that write a file.
- **PR body is fact-checked like a task comment**: drafted from `REPORT.md` into
  `<run_dir>/PR-BODY.md`, checked by a fresh agent, shown in full, and created with
  `gh pr create --body-file` only on the `[pr]` answer.
- **Kept from the unattended mode, now for every run**: a `manual` criterion is reported as
  `NOT PROVEN — needs a human look`; tests already failing on `base_sha` (named in the user's
  instructions or project rules) are reported apart from new failures; a test command named in
  the user's instructions comes first in the "first hit wins" list.
- Tests and captures must come from the run's own checkout: an editor, editor MCP test runner or
  device on another checkout gives `NOT PROVEN`.
- Any `--word` standing alone as an option stops the run at Step 0; a `--flag` inside a quoted or
  named command from the instructions («тесты: dotnet test --filter Combat») belongs to it. Every
  "stop, outcome blocked/tampered" ends at Step 12 with a `REPORT.md`; a second review with
  blocking findings ends the run as `stopped`.
- The runs root is `~/.claude/task-runs`, or `KENSEI_TASK_RUNS_DIR` when set; the guard reads the
  same variable.
- **Gate builds a diff tour** of `<base_sha>..<reviewed_tree>` with notes from the criteria,
  review and `03-changes.md`.
- **Visual proof by the agent**: an `agent-visual` evidence type (screenshot, MCP, adb,
  logcat), guided by the project's verification map, is tried before `manual`; captures go to
  `<run_dir>/evidence/` and into the report and the review.
- **Worktree as an option, base shown at Step 5**: `worktree: always|ask|never` in project
  rules, otherwise a non-default "separate worktree" answer, with a package-restore step
  (`worktree_setup:`). Not the default, because a cold Unity checkout does not build. The run dir
  is keyed to the main checkout (git common dir).
- **Base-branch work at the gate**: merge into the base branch (local `--no-ff`, tests re-run, no
  push) is its own command and its own tag, `[merge-local]`; `[merge]` is a PR merge only. One
  «закоммить и залей в мейн» runs commit → local merge → push without asking again; «смерджи в
  мейн» orders the commit and the merge. Push to the base branch lists every commit it publishes
  and is never forced; a documented rebase path when the base moved (patch-id compare with the
  reviewed tree, tests re-run). Switch, merge and rebase require a clean tree and offer a worktree
  or a stash, never `--autostash`. Before a local merge the skill fetches the target and asks if
  the local `<target>` is behind `origin` (updating it is a `[reset]` command of its own).
- **The target branch.** «Мейн» / "main" means the default branch; when the run was based on
  another task's branch, the skill asks which branch to merge into or push to. A PR goes against
  `base_branch` when that is not the default branch, says in its first line that it is stacked,
  and the commits it carries towards the default branch are listed before it is created. Before,
  a stacked task's PR went to main together with the other task's unreviewed commits.
- **Changes after the gate** (the most common request at the gate in real runs): a fresh
  implementer makes them, never the orchestrator; a new requirement is appended to the approved
  criteria as an addendum whose hash goes into `RUN.md` (`criteria_addendum:`); in `full` mode a
  new automatic criterion gets its test first; then tests, review and report run once more.
- The tag list names every guard tag: `[commit] [merge-local] [push] [pr] [merge] [force-push]
  [publish] [repo-admin] [reset] [status] [create-task] [tracker-edit] [delete-task] [delete-comment]`, and
  `[post]` for an approved text. Other skills that create tasks in a ticket session use
  `[create-task]`.
- **Split text**: `SKILL.md` (rules, Steps 0–5, Commands, guard) + `flow.md` (Steps 6–11) +
  `publish.md` (gate, task comments and PR body, read at the gate). Each rule stated once; the
  `guard.py` docstring is the guard's full specification; the design-doc revision history dropped.
  A run reads ≈53 KB up to the gate (`SKILL.md` + `flow.md`, was ≈60 KB), ≈80 KB with
  `publish.md` — the total grew with the new features (local merge, target branch, changes after
  the gate). The "publish only on command" rule is stated once (rule 7) and referenced
  elsewhere.
- Parallel reviewers read the snapshot (`git show <tree>:<path>`), and test runs that write files
  finish before they start. Russian triggers in the description; `--transport http` in
  `trackers.md`; Windows/python3 requirement documented; PerfectWar specifics
  (`generated_paths`, `test_report_parts`) are examples from project rules.

### ticket guard (`guard.py`)
- **Force pushes in disguise**: bundled short flags are read one by one per subcommand
  (`-fu`, `-uf` force; `-fn` dry run; a value-taking flag such as `-o` ends the bundle). `--all`,
  `--tags`, `--mirror`, a push to `production`/`prod`/`staging`/`stable` or to the `base_branch:`
  of the `RUN.md` this session last wrote (recorded by a `PostToolUse` hook) count as force, and so does the remote's default branch (`origin/HEAD`);
  `send-email`, `send-pack`, `http-push` count as push.
- **Real phrases are recognised**: «push и pr», «PR»/«пр», «залей ветку», «залей(ся) в мейн»
  (commit + local merge + push to the base branch), «смерджи/мердж в мейн» (commit + local merge),
  «смерджи пр» (PR merge only), "push it to main", «верни стэш», «создай задачу», «назначь …»,
  «опубликуй релиз». A test checks every example in the `SKILL.md` command table.
- **Local merge is its own class, `merge-local`**: a `git merge`/`git rebase` into a base branch
  (checked out, switched to in the same command, or `git rebase <upstream> <base>`), and a
  cherry-pick, `am` or commit right after `git switch <base>`. The task commit does not use it up,
  so commit → merge → push passes after one «закоммить и залей в мейн». Bringing a base branch
  into the task branch (`git merge origin/main`, `git rebase --onto origin/main …`) is allowed by
  `[commit]` or `[merge-local]`, and so is `git pull <remote> <base>` on the task branch;
  fast-forwarding local main from `origin/main` is a history write (`[reset]`). On a base branch,
  a commit that concludes a merge (`MERGE_HEAD` present) and `git fetch . <branch>:<base>` are
  `merge-local`; squashing the branch's own commits (`git rebase -i HEAD~3`) is `commit`.
- **Tracker writes split by what they change.** `create-task` / `[create-task]`: creating tasks
  (`clickup_create_task`, a create through `clickup_execute_operator`, `create_issue`, Linear
  `save_issue` without an id, `gh issue create`, `gh api POST …/issues`); one command covers a
  whole batch until the user's next message, because a tracker without a bulk operation creates
  one task per call. `/todo` tags its ClickUp options with it.
  `status` / `[status]`: only the status field (an update whose only changed key is status or
  state, transition tools, `gh issue close/reopen`). Every other tracker field is `tracker` /
  `[tracker-edit]` («назначь на меня»), and `gh pr close` is now one of them. Before, «переведи в ревью» let through
  any tracker or `gh` write, including `gh repo create --public`.
- **Publishing is `publish` / `[publish]`, one grant per object**: creating or editing a release
  (`gh release create/upload/edit`, writes to `…/releases`), a repository (`gh repo create/fork`,
  `POST user/repos|orgs/*/repos|…/forks`) or a gist (`gh gist create/edit/rename`, `gists`). A
  typed command grants only the object it names («выпусти релиз», «создай репо», «создай гист»;
  "cut a release", "fork a repo"); a picked `[publish]` option grants the object its label names
  (релиз/release, репо/repo, гист/gist) and nothing when it names none. So «выпусти релиз» does not
  cover `gh repo create --push`, a visibility change or a secret. This is stricter than putting
  them under push, so «запушь» cannot create a public repository.
- **Repository settings, secrets and CI are `repo-admin` / `[repo-admin]`**, in five kinds, one
  call per grant: settings (`gh repo edit/rename/archive/unarchive`, autolinks, repo `PATCH`,
  hooks, collaborators), secrets (secrets, variables, environments, deploy/ssh/gpg keys), CI
  (`gh workflow`, `gh run`, caches, dispatches, deployments), protection (rulesets, branch and tag
  protection) and deletes of a release or gist. Typed: «сделай репо публичным», «поставь секрет»,
  «запусти workflow», «включи защиту ветки», «удали релиз»; "rerun the ci", "set the X secret".
  The tag grants only the kind its label names. `gh repo delete`, `gh api -X DELETE repos/<o>/<r>`
  and MCP repository deletes stay destructive. Any `gh` command with `--push` also counts as push,
  on top of its own class (`gh pr merge … --push` needs `[merge]` too). GitHub, GitLab and
  GitKraken MCP writes map to the same grants; reads (`gh api` GET) are free.
- **Owner decisions** (confirmed for 2.0.0): the old single `[publish]` is split into per-object
  `[publish]` and per-kind `[repo-admin]`; `[tracker-edit]` stays a tag of its own; bringing the
  base branch into the task branch is allowed by `[commit]` or `[merge-local]`; one
  `[create-task]` command is not used up within the message, so a batch of tasks passes;
  `gh pr close` is a tracker write (`[tracker-edit]`).
- **A message queued mid-turn** adds its orders to the message before it. One that says stop or
  holds a gated action back voids every command so far and grants nothing itself: «не надо»,
  «стой», «передумал», «я сам», «сам закоммичу», «давай я сделаю», «сначала …», «перед этим /
  перед коммитом», «дай посмотреть / гляну», "first …", "changed my mind", "let me check",
  "I'll do it", "hold off", "no wait". So «сначала покажи дифф, потом закоммить» asks again.
  «сам тест упал» voids nothing. These phrases are mandatory refusals in the tests.
- **A failed call** uses nothing up when the gated step is the whole command or ends an `&&`
  chain (a hook-refused commit, a rejected push). An MCP call uses its command up unless the
  server plainly refused it (validation error, `-32602`, a 4xx, "not found" on the first line of
  the error): after a timeout, a 500 or an unclear error the write may have happened, so the same
  comment is not posted twice. This reverses the earlier 2.0.0 draft, where any failed MCP call
  freed its command.
- **Tamper: reads pass, writes to the guard are refused.** Read-only `find`, and `rm`/`mv`/`cp`
  inside the run dir pass (RUN.md → RUN.prev.md works again). Refused: writes to the `.guard`
  markers, the session and subagent transcripts, the guard's own `skills/ticket/` and `hooks/` (with
  `--plugin-dir`, the dev clone — deliberate), `~/.claude/plugins`, any Bash write to a settings
  file (`settings*.json` in the config dir — `CLAUDE_CONFIG_DIR` honoured — or in any `.claude` dir,
  and `managed-settings.json`, matched on the written path and on the realpath, so a symlink into
  dotfiles is covered), a Write/Edit that changes `hooks`, `disableAllHooks`, `enabledPlugins` or
  `allowManagedHooksOnly` (compared as parsed JSON), and `claude plugin` other than list/validate.
- **Fewer accidental grants, fewer blind spots**: questions, git commands mentioned inside a
  sentence and pasted text grant nothing; English verbs need a git object. Gated now: throwing
  local changes away (`clean -f`, `checkout -- <paths>`, `restore`, `stash pop/apply/drop`;
  `[reset]`), `reset <ref>`, `checkout -B`, `switch -C`, `filter-*`; `gh` anything off its read
  list; `curl --json`/`-d@`/`--request=POST`, wget and httpie writes, self-hosted tracker APIs;
  ClickUp `execute_operator` judged by model + operator. `git stash push` is refused to subagents
  only. Always refused: a git subcommand built from `$` or backticks (`git $S`,
  `git "$(echo push)"`, `` git `echo push` ``); a program named by `$VAR`/`$(…)` that is plausibly
  git (`$GIT`, `$(which git)`, or any unnamed program whose first argument is a writing git
  subcommand); `$SHELL -c "…"` is read like `sh -c`; a runner target named exactly push,
  publish, release, deploy or ship (`make push`, `npm publish`); a `Skill` call with
  `--comment`/`--post`. `SendMessage` asks the user. Ordinary commands no longer trip this, since
  they could never be unblocked: `$PY -m pytest -k checkout`, `$ROOT/gradlew build`,
  `$GIT_EDITOR`, `npm run release-notes` and `make deploy-docs` pass.
- Comment check: every text field must equal the approved text; `*_id` keys are not text. Tracker
  names match on word boundaries (`plane` ≠ `planetscale`; `gitkraken` added).
- **Linear time**: typed text is read from its first and last 4 KB, URL and split regexes
  are linear, and a speed test guards it, so a huge command no longer outruns the 15 s timeout.
- The subagent hook's shell one-liner is now `hooks/subagent-guard.sh`, tested to start no Python
  outside a marked session; `Skill` and `SendMessage` are in both matchers and `MultiEdit` is
  gone. `SendMessage` asks before the transcript is read, so a malformed transcript cannot turn
  the ask into a refusal. It takes the hook input's first `session_id`, so one inside
  `tool_input` cannot point it at another session.
- Tests: a headless invocation (`claude -p`) that contains «закоммить и запушь» grants nothing,
  and ticket text read from a file or echoed by the model grants no gated call.

### diff-tour
- **The model can run it**: `disable-model-invocation` removed; the description triggers on
  «покажи дифф», «что поменялось», «дифф-тур», «ревью перед коммитом», or when another skill or
  CLAUDE.md says to show changes this way. Still read-only and still only on request.
- **No silently lost file**: the throwaway index is copied with `copy2`, keeping its mtime,
  so a same-size edit in the same second is not treated as clean (collect and drift check); the
  test is deterministic.
- After a commit, with nothing uncommitted, it shows the commits beyond the upstream (or the
  default branch) and names that base instead of stopping at "No changes.".
- Ranges accept a tree id on either side (`<base_sha>..<reviewed_tree>`), for callers such as
  ticket; `--out-root` is documented; a "When another skill calls it" section.
- highlight.js pinned with SRI; `~/.cache/kensei-diff` is 0700 and keeps the newest 20 runs per
  repository. Russian example notes, unambiguous size and read-length rules, by-product files are
  `inferred`, ResourceWarnings in tests fixed.

### brainstorm
- Docs go outside the project by default: `.claude/brainstorm-rules.md`, then the project's
  existing `docs/brainstorms`, then `~/docs/brainstorms`; the path is named before writing.
- Fewer questions: one "Asking questions" section; design sections come in batches of up to
  three with one "which need changes?" question; independent enumerable questions are batched
  (up to 4); no empty "needs changes" options — edits go in Other. One decision at a time stays.
- Questions, options, the doc and the plan are in the user's language. The 1.8.1 behaviour (no
  `EnterPlanMode`, implementation only on "Start here") is kept and has an eval case.

### Repository
- `evals/` with `claude plugin eval` cases: diff-tour fires on «покажи дифф», brainstorm
  never enters plan mode, ticket stops at criteria without committing and its context agent writes
  `01-context.md`, unity-review with a mode given asks nothing and edits nothing, learn and todo
  write nothing before approval, and `ticket-commit-at-gate` resumes a run stopped at the publish
  gate, types «закоммить» and checks one commit on the task branch, no run notes in the index, no
  push, PR or merge. The smoke command uses `--scaffold`. Evals run on Opus only, every command
  with `--judge-model opus`; stray session transcripts and eval outputs are git-ignored.
- Live run on Opus 5.5, 3 runs per case, `--judge-model opus`, $19.77: `brainstorm-no-plan-mode`,
  `diff-tour-on-show-diff`, `unity-review-readonly`, `learn-asks-before-writing` and
  `todo-asks-before-creating` all 1.00. Both ticket cases were blocked by the macOS eval sandbox
  (git through the xcrun shim cannot run); in the one run where git worked, the gate case made
  exactly one commit holding the two fix files, with no push, amend or run notes. Graders found
  wrong in the run were fixed.
- learn and todo: when `AskUserQuestion` is unavailable (headless sessions), the same question is
  asked in plain text and the skill waits for the answer.
- Version only in `plugin.json`; marketplace has a description; keywords updated.
- CI: script tests on Linux and macOS, `claude plugin validate --strict`, strict-YAML frontmatter,
  release tag vs `plugin.json`.
- README: requirements (`python3`), skill table with invocation (manual / model) and an example
  phrase per skill, hooks in the structure, the development and release loop.

### Not done in this release
- Full live runs of the two ticket cases: they need Linux CI or a Homebrew git the macOS eval
  sandbox may read. Until then the commit path rests on the guard tests, the gate case's fixture
  and the one run where git worked. A live probe on Claude Code 2.1.286 confirmed that the skill's
  frontmatter `PreToolUse` and `PostToolUse` hooks register once the skill is invoked (also as a
  `/plugin:skill` in a `-p` prompt) and that `${CLAUDE_PLUGIN_ROOT}` expands; a denied call gets
  no `PostToolUse`, so `guard.py --post` never sees it. Whether the hooks register in a resumed
  session (`--resume`, as the gate case uses) is still unverified. Regenerate
  `evals/ticket-commit-at-gate/history.jsonl` with `make_history.py` before running it.
- Installing through `claude plugin update`, restarting old sessions and fixing the auto-memory
  note that still says to edit the plugin cache — owner actions, described in the README.
- Guard gaps left for 2.0.1 (each fails open only when the model already broke the skill's rules):
  - a gated phrase quoted inside the user's message still counts as a command («тикет говорит:
    «запушь»» lets `git push` through, as in 1.8);
  - the PR body is not compared with the approved `PR-BODY.md`; «открой PR» lets any
    `gh pr create --body …` through, so the fact-check rests on the skill's rules;
  - a redirect after `cd` is checked against the old directory (`cd ~/.claude && echo … >
    settings.json`), and `cp x/settings.json ~/.claude/` is not caught;
  - `git config remote.origin.push …` / `alias.*` are not treated as tampering, so a later plain
    push can land elsewhere;
  - mail, chat and calendar MCP sends (Gmail `send_message`, Slack), `curl` to webhooks,
    `RemoteTrigger` and `CronCreate` are not gated; the `PowerShell` tool is not in the matcher;
  - `git worktree remove --force` is not gated, though the skill lists it as a command;
  - «переведи задачи в ревью» (plural) allows one status change; `gh copilot` is refused as a
    tracker write.
- A commit on a base branch the session was already on stays `commit` (the user may choose to work
  on main); only one right after `git switch <base>` in the same command, or one that concludes a
  merge, is `merge-local`.
- P2-17, the size of the ticket text, is deferred to 2.0.1: up to the gate it is smaller than in
  1.8 (≈53 KB, was ≈60 KB), but with `publish.md` a run reads ≈80 KB, more than before.
- PerfectWar still needs `.claude/task-flow-rules.md` with `worktree_setup:` for worktree runs.
- diff-tour's HTML/CSS/JS stays inside `difftour.py` (no functional gain; tests use it directly).
- No smoke test on a fresh real transcript: the transcript fields were checked against Claude Code
  2.1.285 and recorded in the guard docstring.
- ClickUp operator names are classified by their words; the live operator catalogue was empty
  and could not be cross-checked.
- `displayName` / `homepage` in manifests (cosmetic).

## kensei-statusline 1.5.0 — 2026-10

- Output tokens include workflow subagents (recursive transcript scan); before, about two thirds of
  a workflow-heavy session was missing.
- Prices per exact model version (Fable 5.1, Opus 5.5, Sonnet 5.5, Haiku 4.5 and earlier), with
  1.25× / 2× cache-write rates for 5-minute / 1-hour writes; ids are normalised (`[1m]`, Bedrock
  prefixes including `global.` and `us-gov.`, inference-profile ARNs, snapshot dates). An unknown
  model and fast-mode requests show `n/a` instead of a guess. Used only when Claude Code does not
  report the cost.
- `git --no-optional-locks` on every git call, so the statusline never takes the index lock.
- The wrapper ships as a file and resolves the installed version from `installed_plugins.json`
  (project install first), skipping orphaned copies and honouring `CLAUDE_CONFIG_DIR`.
- Setup runs `setup.py`: it keeps `refreshInterval` and your other `statusLine` fields, backs up
  `settings.json`, writes through a symlink keeping file mode, offers a dry run, and reports a
  `statusLine` in `settings.local.json` that would override it. The setup offer mentions the OAuth
  token read.
- The SessionStart check honours `CLAUDE_CONFIG_DIR` and `settings.local.json` and runs on
  `startup` only. The setup trigger moved from the non-standard `trigger:` field into the
  description.
- Project stats cached per HEAD (they were ~80% of render time).
- README: setup is offered, not run automatically; agents are grouped by `subagent_type`.
- `statusline_test.py` added, including the usage-limit fetch (keychain and `.credentials.json`
  token, cache, backoff per HTTP code, lock takeover, stale cache, the Fable row) with stubbed
  network and keychain: 91% line coverage of `statusline.py` (coverage.py). The refresh cancels
  its 30-second kill timer when done. Not done: splitting out `usage.py` (the tests do not need
  it).

## Earlier history

Reconstructed from git; dates are commit dates.

### kensei-toolkit
- **1.8.1** (2026-09-30): brainstorm saves a standalone `<slug>-plan.md` and asks Save only / Start
  here / Revise instead of entering plan mode. Repository renamed to `kensei-claude-plugins`, MIT
  license.
- **1.8.0** (2026-09-29): ticket `--unattended` for headless runners (REPORT.md, commit-msg.txt,
  RESULT.json); snapshot index in the git dir, built without `rm`.
- **1.7.0** (2026-09-24): diff-tour — annotated diff page for self-review before a commit.
- **1.6.0** (2026-09-22): ticket publishes only on command; reviewed task comments; guard hook.
- **1.5.0** (2026-09-10): ticket — run one tracker task end to end.
  Committing the acceptance notes dates from this design; reversed in 2.0.0.
- **1.4.0** (2026-06-11): brainstorm skill.
- **1.3.0** (2026-05-26): todo skill; pr-preview removed.
- **1.2.x** (2026-05): learn skill (1.2.0); pr-preview overhaul; unity-review always shows the mode
  picker.
- **1.1.x** (2026-04): pr-preview skill with standalone HTML output; frontmatter quoting fixes.
- **1.0.0** (2026-04-08): first release as `toolkit`, renamed `kensei-toolkit`; unity-review.

### kensei-statusline
- **1.4.0** (2026-09-24): per-model usage meters (e.g. Fable) from the claude.ai usage endpoint;
  setup hook moved to `hooks/hooks.json`.
- **1.3.1** (2026-06-11): usage limits on their own line.
- **1.3.0** (2026-06-11): subscription usage limits with reset times.
- **1.2.0** (2026-04-15): context size instead of cumulative input tokens.
- **1.1.0** (2026-04-08): `python3` in the statusline command; setup skill and SessionStart hook.
- **1.0.0** (2026-04-06): first release — model, context, tokens, cost, subagents, git, project
  stats.
