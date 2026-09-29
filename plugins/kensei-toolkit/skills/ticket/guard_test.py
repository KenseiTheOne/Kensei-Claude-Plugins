#!/usr/bin/env python3
"""Tests for guard.py — run: python3 guard_test.py"""

import json
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import guard  # noqa: E402

HOME = tempfile.mkdtemp()  # markers go to $HOME/.claude/task-runs/.guard — keep them out of ~


def repo(branch):
    path = tempfile.mkdtemp()
    subprocess.run(["git", "init", "-q", "-b", branch, path], check=True)
    return path


TASKREPO = repo("task/test")   # a plain `git push` from here is an ordinary push
MAINREPO = repo("main")        # … and from here a push to the base branch


# --- transcript builders ------------------------------------------------------------------

def human(text):
    return {"type": "user", "origin": {"kind": "human"}, "promptSource": "typed",
            "message": {"role": "user", "content": text}}


def queued(text):
    return {"type": "attachment", "attachment": {"type": "queued_command", "prompt": text,
                                                 "commandMode": "prompt",
                                                 "origin": {"kind": "human"}, "humanTurn": True}}


def invocation(args):
    return {"type": "user", "origin": {"kind": "human"},
            "message": {"role": "user", "content":
                        "<command-message>kensei-toolkit:ticket</command-message>\n"
                        "<command-name>/kensei-toolkit:ticket</command-name>\n"
                        f"<command-args>{args}</command-args>"}}


def notification(text):
    return {"type": "user", "origin": {"kind": "task-notification"}, "promptSource": "system",
            "message": {"role": "user", "content": text}}


def wakeup(text):
    return {"type": "user", "origin": None, "promptSource": "system", "isMeta": True,
            "message": {"role": "user", "content": text}}


def assistant(text="ok"):
    return {"type": "assistant", "message": {"role": "assistant",
                                             "content": [{"type": "text", "text": text}]}}


_ids = iter(range(10_000))


def call(name, inp):
    """An executed tool call: the assistant tool_use plus its result."""
    i = f"t{next(_ids)}"
    return [{"type": "assistant", "message": {"role": "assistant", "content": [
                {"type": "tool_use", "id": i, "name": name, "input": inp}]}},
            {"type": "user", "message": {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": i, "content": "done"}]}}]


def denied_call(name, inp):
    i = f"t{next(_ids)}"
    return [{"type": "assistant", "message": {"role": "assistant", "content": [
                {"type": "tool_use", "id": i, "name": name, "input": inp}]}},
            {"type": "user", "message": {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": i, "is_error": True,
                 "content": "PreToolUse:Bash hook error: [ticket guard] Blocked."}]}}]


def answer(question, options, picked, multi=False, annotations=None, **extra):
    """options: list of (label, preview-or-None)"""
    opts = [{"label": l, "description": ""} | ({"preview": p} if p else {}) for l, p in options]
    return {"type": "user", "origin": None,
            "message": {"role": "user", "content": [{"type": "tool_result",
                                                     "tool_use_id": "q", "content": "answered"}]},
            "toolUseResult": {"questions": [{"question": question, "header": "h",
                                             "options": opts, "multiSelect": multi}],
                              "answers": {question: picked}, "annotations": annotations or {},
                              **extra}}


class Transcript:
    def __init__(self, entries):
        fd, self.path = tempfile.mkstemp(suffix=".jsonl")
        with os.fdopen(fd, "w") as f:
            for e in entries:
                f.write(json.dumps(e) + "\n")  # ASCII-escaped, as real transcripts store it

    def __enter__(self):
        return self.path

    def __exit__(self, *a):
        os.unlink(self.path)


def run_hook(tool_name, tool_input, entries, cwd=None, mode="--main", session=None, agent=None):
    with Transcript(entries) as path:
        payload = {"tool_name": tool_name, "tool_input": tool_input, "transcript_path": path,
                   "cwd": cwd or TASKREPO, "hook_event_name": "PreToolUse"}
        if session:
            payload["session_id"] = session
        if agent:
            payload["agent_id"], payload["agent_type"] = agent, "general-purpose"
        out = subprocess.run([sys.executable, os.path.join(HERE, "guard.py"), mode],
                             input=json.dumps(payload), capture_output=True, text=True,
                             env=dict(os.environ, HOME=HOME))
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)["hookSpecificOutput"]["permissionDecisionReason"] \
        if out.stdout.strip() else None


def bash(cmd):
    return ("Bash", {"command": cmd})


def flat(*parts):
    out = []
    for p in parts:
        out += p if isinstance(p, list) else [p]
    return out


# --- typed text ---------------------------------------------------------------------------

class DetectTest(unittest.TestCase):
    def cases(self, action, yes, no):
        for t in yes:
            self.assertIn(action, guard.detect(t), t)
        for t in no:
            self.assertNotIn(action, guard.detect(t), t)

    def test_commit(self):
        self.cases("commit",
                   ["закоммить", "Закоммить и запушь", "коммить, пушь", "коммитни это",
                    "схлопни в один коммит и залей на ветку", "сделай коммит",
                    "пиши коммент на clickup, коммить, пушь", "ок, commit it", "please commit",
                    "commit and push", "commit & push", "go ahead and commit", "lgtm, коммить",
                    "можешь закоммитить?", "не забудь закоммитить", "git commit это",
                    "пушить не надо, только закоммить", "закоммить, но не пушь",
                    "коммит и пуш", "коммит + пуш", "если что — закоммить", "закоммить, ок?",
                    "закомить", "закоммить, потом запушь"],
                   ["не коммить", "без коммита", "не надо коммитить", "покажи коммит",
                    "ты закоммитил?", "закоммитишь?", "the last commit is broken",
                    "без моей команды не коммитить, не пушить", "потом закоммитим",
                    "если тесты зелёные — закоммить", "закоммить, если тесты зелёные",
                    "перед тем как закоммитить, покажи дифф", "do not commit yet",
                    "don't commit", "а скилл сам коммитит?", "коммит и пуш отменяются",
                    "последний коммит и пуш сломали CI", "коммит и пуш не нужны",
                    "не надо: коммит и пуш", "позже закоммить", "commit message is wrong",
                    "https://www.notion.so/acme/Fix-commit-hook-crash-1a2b3c fix",
                    "коммит?", "закоммить или подожди", "закоммить, только позже",
                    "закоммить, но пока не надо", "commit/push flow is broken",
                    "ENG-7 крашится в Scripts/Merge", "github.com/acme/app/commit/abc1234"])

    def test_push(self):
        self.cases("push",
                   ["запушь", "пушь", "залей на ветку", "закоммить и запушь", "go push",
                    "commit & push", "пуш", "commit/push", "коммит/пуш", "запуш", "залей в ветку"],
                   ["не пушь", "без пуша", "он пушит?", "push notification settings",
                    "https://linear.app/acme/issue/ENG-123/fix-push-notifications fix",
                    "Баг: push-уведомления дублируются", "пушить не надо, только закоммить",
                    "закоммить, но не пушь", "залей билд на телефон", "создай PR",
                    "86abc баг в Assets/Scripts/Push/PushService.cs", "86abc падает src/notifications/push",
                    "push/pull не работает, глянь логи", "запушь, но не сейчас", "push, but not yet",
                    "запушь потом", "пушь в main", "пуш сломали CI"])

    def test_tracker(self):
        self.cases("tracker",
                   ["переведи задачу в ревью", "переведи в ревью", "смени статус на done",
                    "поставь статус in review", "задачу в ревью", "в ревью", "move it to review",
                    "закрой задачу", "закоммить, запушь и переведи задачу в ревью",
                    "возьми задачу в работу", "в работу", "86abc fix в работу"],
                   ["переведи текст на английский", "переведи описание задачи на русский",
                    "не переводи статус", "в ревью не переводи", "статус не трогай",
                    "какой статус?", "отдай на ревью агенту", "кидать на ревью коммент",
                    "в ревью нашли баг", "в работу не бери"])

    def test_other_actions(self):
        self.cases("delete", ["удали коммент", "удали последний коммент", "delete that comment",
                              "чет ты не то написал. Удали коммент"],
                   ["не удаляй коммент", "удали файл", "убери лишние комментарии в коде",
                    "удали из коммента строку про ветку", "удали строку из коммента",
                    "удали лишние комментарии из GuardService.cs", "remove the comment on line 40"])
        self.cases("pr", ["создай PR", "открой pr", "open a PR", "запушь и открой PR"], ["запушь"])
        self.assertTrue({"commit", "history"} <= guard.detect("схлопни в один коммит"))
        self.cases("merge", ["смержи PR", "merge the pr"], ["смержи main в ветку"])
        self.assertIn("commit", guard.detect("смержи main в ветку"))
        self.cases("force", ["форс-пушь", "force push", "пушь в main"], ["не форсь"])
        self.cases("history", ["сбрось ветку", "подтяни main"], ["не сбрасывай"])
        self.cases("destructive", ["удали задачу"], ["удали коммент"])


class SplitMultiTest(unittest.TestCase):
    def test_cli_format(self):
        self.assertEqual(guard.split_multi("A, B"), ["A", "B"])
        self.assertEqual(guard.split_multi('"Коммит, как есть [commit]", Push [push]'),
                         ["Коммит, как есть [commit]", "Push [push]"])
        self.assertEqual(guard.split_multi("single"), ["single"])


# --- what a call does ---------------------------------------------------------------------

class ClassifyTest(unittest.TestCase):
    def kinds(self, cmd, tool="Bash", cwd=None):
        return sorted({g[0] for g in guard.classify(tool, {"command": cmd}, cwd or TASKREPO)})

    def test_git(self):
        k = self.kinds
        self.assertEqual(k("git commit -m x"), ["commit"])
        self.assertEqual(k("git -C /tmp -c user.name=x commit --amend --no-edit"), ["commit"])
        self.assertEqual(k("cd sub && GIT_INDEX_FILE=/x git add a && git commit -m y"), ["commit"])
        self.assertEqual(k("git status; git push -u origin task/1-x"), ["push"])
        self.assertEqual(k("bash -c 'git commit -m z'"), ["commit"])
        self.assertEqual(k("bash -lc 'git commit -m z'"), ["commit"])
        self.assertEqual(k("zsh -lc 'git push'"), ["push"])
        self.assertEqual(k("echo $(git commit -m q)"), ["commit"])
        self.assertEqual(k("timeout 10 git push"), ["push"])
        self.assertEqual(k("if git diff --quiet; then echo n; else git commit -m f; fi"), ["commit"])
        self.assertEqual(k("{ git push -u origin task/1; } 2>&1 | tail -3"), ["push"])
        self.assertEqual(k("! git push"), ["push"])
        self.assertEqual(k("for r in a b; do git -C $r push; done"), ["push"])
        self.assertEqual(k("git -C /repo \\\n  commit -m x"), ["commit"])
        self.assertEqual(k("GIT push"), ["push"])
        self.assertEqual(k("sudo -u me git push"), ["push"])
        self.assertEqual(k("caffeinate -i git push"), ["push"])
        self.assertEqual(k("env -S 'git push'"), ["push"])
        self.assertEqual(k("find . -name x -exec git commit -m y \\;"), ["commit"])
        self.assertEqual(k("echo a | xargs git commit -m"), ["commit"])
        self.assertEqual(k("git submodule foreach git push"), ["push"])
        self.assertEqual(k("git -c alias.pp=push pp"), ["push"])
        self.assertEqual(k("echo 'git push' | sh"), ["push"])
        self.assertEqual(k("sh <<< 'git push'"), ["push"])
        self.assertEqual(k("bash <<EOF\ngit push\nEOF"), ["push"])
        self.assertEqual(k('git commit -m "$(cat <<\'EOF\'\nfix: don\'t crash\nEOF\n)"'), ["commit"])
        self.assertEqual(k("gh pr create --body-file - <<'EOF'\nIt's a fix\nEOF"), ["pr"])
        self.assertEqual(k("python3 - <<'EOF'\nprint(\"git push is not run here, it's text\")\nEOF"),
                         [])
        self.assertEqual(k("git log | grep \"don't\""), [])
        self.assertEqual(k("git status && echo \"it's fine"), [])  # unbalanced, no git write
        self.assertEqual(k("git merge --abort"), [])
        self.assertEqual(k("git commit --dry-run"), [])
        self.assertEqual(k("git push --dry-run"), [])
        self.assertEqual(k("git log --grep commit && git diff --stat"), [])
        self.assertEqual(k("git merge-base HEAD main"), [])
        self.assertEqual(k("echo 'git commit' > notes.txt"), [])
        self.assertEqual(k("git rebase -i main"), ["commit"])
        self.assertEqual(k("git cherry-pick -n abc"), [])
        self.assertEqual(k("git stash push -m 'ticket 1'"), [])
        self.assertEqual(k("git fetch && git branch -a && git remote -v"), [])
        self.assertEqual(k("git submodule foreach 'git push'"), ["push"])
        self.assertEqual(k("find . -exec sh -c 'cd {} && git push' \\;"), ["push"])
        self.assertEqual(k("cat <<EO-F\nx\nEO-F\ngit push"), ["push"])
        self.assertEqual(k("cat <<END\nnever closed\ngit push"), ["push"])
        self.assertEqual(k("cat <<'EOF' | sh\ngit push\nEOF"), ["push"])
        self.assertEqual(k("git commit -m a && git commit -m b"), ["commit", "repeat"])
        self.assertEqual(k("git commit -m a && git push"), ["commit", "push"])

    def test_push_kinds(self):
        k = self.kinds
        self.assertEqual(k("git push --force"), ["force"])
        self.assertEqual(k("git push --force-with-lease origin task/1"), ["force"])
        self.assertEqual(k("git push origin HEAD:main"), ["force"])
        self.assertEqual(k("git push origin +task/1"), ["force"])
        self.assertEqual(k("git push origin --delete task/1"), ["force"])
        self.assertEqual(k("git pull"), ["history"])
        self.assertEqual(k("git reset --hard HEAD~1"), ["history"])
        self.assertEqual(k("git reset -- file.txt"), [])
        self.assertEqual(k("git branch -D task/1"), ["history"])
        self.assertEqual(k("git stash drop"), ["history"])
        self.assertEqual(k("git subtree push --prefix x origin y"), ["push"])
        self.assertEqual(k("git push", cwd=MAINREPO), ["force"])
        self.assertEqual(k("git push -u origin HEAD", cwd=MAINREPO), ["force"])
        self.assertEqual(k("git push -u origin HEAD"), ["push"])

    def test_gh(self):
        k = self.kinds
        self.assertEqual(k("gh pr create --fill"), ["pr"])
        self.assertEqual(k("gh pr merge 3 --squash"), ["merge"])
        self.assertEqual(k("gh issue view 3 --comments"), [])
        self.assertEqual(k("gh pr view 3 && gh pr diff 3 && gh pr checks 3"), [])
        self.assertEqual(k("gh issue comment 3 --body hi"), ["comment"])
        self.assertEqual(k("gh issue close 3"), ["tracker"])
        self.assertEqual(k("gh issue close 3 --comment done"), ["comment", "tracker"])
        self.assertEqual(k("gh issue delete 3"), ["destructive"])
        self.assertEqual(k("gh api repos/o/r/issues/3/comments -f body=hi"), ["comment"])
        self.assertEqual(k("gh api -XDELETE repos/o/r/issues/comments/9"), ["delete"])
        self.assertEqual(k("gh api repos/o/r/issues/3"), [])
        self.assertEqual(k("gh api -X GET repos/o/r/issues"), [])
        self.assertEqual(k("gh api graphql -f query='{ viewer { login } }'"), [])
        self.assertEqual(k("gh api graphql -f query='mutation{addComment(input:{}){x}}'"),
                         ["comment"])
        self.assertEqual(k("gh release create v1"), ["push"])
        self.assertEqual(k("curl -X POST https://api.clickup.com/api/v2/task/1/comment -d x"),
                         ["comment"])
        self.assertEqual(k("curl -X PUT https://api.clickup.com/api/v2/task/1 -d x"), ["tracker"])
        self.assertEqual(k("curl https://api.clickup.com/api/v2/task/1"), [])

    def test_monitor(self):
        self.assertEqual(self.kinds("git push", tool="Monitor"), ["push"])

    def test_mcp(self):
        k = lambda name, inp=None: sorted({g[0] for g in guard.classify(name, inp or {}, TASKREPO)})
        self.assertEqual(k("mcp__clickup__clickup_get_task"), [])
        self.assertEqual(k("mcp__clickup__clickup_get_task_comments"), [])
        self.assertEqual(k("mcp__clickup__clickup_get_chat_channel_messages"), [])
        self.assertEqual(k("mcp__clickup__clickup_resolve_assignees"), [])
        self.assertEqual(k("mcp__clickup__clickup_get_task_time_in_status"), [])
        self.assertEqual(k("mcp__clickup__clickup_find_member_by_name"), [])
        self.assertEqual(k("mcp__clickup__clickup_get_workspace_hierarchy"), [])
        self.assertEqual(k("mcp__clickup__clickup_update_task", {"status": "review"}), ["tracker"])
        self.assertEqual(k("mcp__clickup__clickup_create_comment", {"comment_text": "hi"}),
                         ["comment"])
        self.assertEqual(k("mcp__clickup__clickup_send_chat_message", {"content": "hi"}),
                         ["comment"])
        self.assertEqual(k("mcp__clickup__clickup_update_comment", {"resolved": True}), ["tracker"])
        self.assertEqual(k("mcp__clickup__clickup_delete_comment"), ["delete"])
        self.assertEqual(k("mcp__clickup__clickup_delete_task"), ["destructive"])
        self.assertEqual(k("mcp__clickup__clickup_merge_tasks"), ["destructive"])
        self.assertEqual(k("mcp__clickup__clickup_execute_operator"), ["tracker"])
        self.assertEqual(k("mcp__unity-perfectwar__write_asset"), [])
        self.assertEqual(k("mcp__claude_ai_Asana__authenticate"), [])
        self.assertEqual(k("mcp__atlassian__getJiraIssue"), [])
        self.assertEqual(k("mcp__atlassian__searchJiraIssuesUsingJql"), [])
        self.assertEqual(k("mcp__atlassian__atlassianUserInfo"), [])
        self.assertEqual(k("mcp__atlassian__addCommentToJiraIssue", {"commentBody": "x"}),
                         ["comment"])
        self.assertEqual(k("mcp__atlassian__transitionJiraIssue"), ["tracker"])
        self.assertEqual(k("mcp__notion__notion-create-comment",
                           {"rich_text": [{"text": {"content": "hi"}}]}), ["comment"])
        self.assertEqual(k("mcp__github__create_pull_request"), ["pr"])
        self.assertEqual(k("mcp__github__create_pull_request_review", {"body": "lgtm"}), ["comment"])
        self.assertEqual(k("mcp__gitlab__get_merge_request"), [])
        self.assertEqual(k("mcp__gitlab__list_merge_requests"), [])
        self.assertEqual(k("mcp__gitlab__create_merge_request"), ["pr"])
        self.assertEqual(k("mcp__gitlab__merge_merge_request"), ["merge"])
        self.assertEqual(k("mcp__clickup__clickup_remove_tag_from_task"), ["tracker"])
        self.assertEqual(k("mcp__github__merge_pull_request"), ["merge"])
        self.assertEqual(k("mcp__github__get_pull_request"), [])
        self.assertEqual(k("mcp__github__pull_request_read"), [])
        self.assertEqual(k("mcp__github__resolve_review_thread"), ["tracker"])
        self.assertEqual(k("mcp__git__git_commit"), ["commit"])
        self.assertEqual(k("mcp__git__git_status"), [])

    def test_notion_shapes(self):
        txt = "Сделано: AC1 ok"
        for shape in [{"text": {"content": txt}}, {"type": "text", "text": {"content": txt}},
                      {"type": "text", "text": {"content": txt}, "annotations": {"color": "default"}},
                      {"type": "text", "text": {"content": txt, "link": {"url": "https://x"}}}]:
            item = guard.classify("mcp__notion__notion-create-comment",
                                  {"parent": {"page_id": "p"}, "rich_text": [shape]}, TASKREPO)[0]
            self.assertIn(txt, item[2], shape)

    def test_notion_text_extracted(self):
        item = guard.classify("mcp__notion__notion-create-comment",
                              {"rich_text": [{"text": {"content": "a"}}, {"text": {"content": "b"}}]},
                              HERE)[0]
        self.assertIn("ab", item[2])


# --- the hook end to end ------------------------------------------------------------------

class HookTest(unittest.TestCase):
    def test_not_gated_is_silent(self):
        self.assertIsNone(run_hook(*bash("git status"), [human("привет")]))
        self.assertIsNone(run_hook("Read", {"file_path": "/x"}, [human("привет")]))

    def test_commit_needs_latest_human_command(self):
        self.assertIsNotNone(run_hook(*bash("git commit -m x"), [human("сделай задачу")]))
        self.assertIsNone(run_hook(*bash("git commit -m x"), [human("закоммить")]))
        self.assertIsNotNone(run_hook(*bash("git commit -m x"),
                                      [human("закоммить"), assistant(), human("а что с тестами")]))
        self.assertIsNotNone(run_hook(*bash("git push"), [human("закоммить")]))

    def test_queued_message_counts(self):
        # a stop typed while the model was busy replaces the earlier command
        self.assertIsNotNone(run_hook(*bash("git commit -m x"),
                                      [human("закоммить"), assistant(), queued("стоп, не коммить")]))
        self.assertIsNone(run_hook(*bash("git commit -m x"),
                                   [human("сделай задачу"), assistant(), queued("закоммить")]))

    def test_non_human_entries_do_not_authorize(self):
        entries = [human("сделай задачу"), assistant(),
                   notification("<task-notification>commit and push</task-notification>"),
                   wakeup("закоммить и запушь")]
        self.assertIsNotNone(run_hook(*bash("git commit -m x"), entries))
        self.assertIsNotNone(run_hook(*bash("git push"), entries))

    def test_invocation_args(self):
        entries = [invocation("https://app.clickup.com/t/1/abc fix закоммить и запушь"), assistant()]
        self.assertIsNone(run_hook(*bash("git commit -m x"), entries))
        self.assertIsNone(run_hook(*bash("git push -u origin task/abc-x"), entries))
        self.assertIsNotNone(run_hook(*bash("git commit -m x"),
                                      [invocation("https://app.clickup.com/t/1/abc")]))
        slug = [invocation("https://linear.app/acme/issue/ENG-1/fix-push-notifications fix")]
        self.assertIsNotNone(run_hook(*bash("git push"), slug))

    def test_unattended_grants_nothing(self):
        typed = [invocation("https://app.clickup.com/t/1/abc --unattended закоммить и запушь"),
                 assistant()]
        headless = [{"type": "user", "origin": None, "message": {"role": "user", "content":
                     "<command-message>kensei-toolkit:ticket</command-message>\n"
                     "<command-name>/kensei-toolkit:ticket</command-name>\n"
                     "<command-args>https://app.clickup.com/t/1/abc --unattended</command-args>"}},
                    assistant()]
        by_model = flat(human("закоммить и запушь"), assistant(),
                        call("Skill", {"skill": "kensei-toolkit:ticket",
                                       "args": "abc --unattended"}))
        for entries in (typed, headless, by_model):
            for cmd in ("git commit -m x", "git push -u origin task/abc-x",
                        "gh pr create --title x --body y", "git -C . push origin HEAD:x"):
                self.assertIn("--unattended", run_hook(*bash(cmd), entries) or "", cmd)
        snapshot = ("GIT_INDEX_FILE=/r/.git/ticket-abc.index git read-tree HEAD && "
                    "GIT_INDEX_FILE=/r/.git/ticket-abc.index git add -- a.txt && "
                    "GIT_INDEX_FILE=/r/.git/ticket-abc.index git write-tree")
        self.assertIsNone(run_hook(*bash(snapshot), headless))
        # a message typed after the run is an ordinary command again
        self.assertIsNone(run_hook(*bash("git commit -m x"), typed + [human("закоммить")]))
        self.assertIsNone(run_hook(*bash("git commit -m x"),
                                   [invocation("abc --unattendedly закоммить"), assistant()]))

    def test_model_invoked_skill_voids_earlier_typing(self):
        self.assertIsNotNone(run_hook(*bash("git commit -m x"),
                                      flat(human("закоммить"), assistant(),
                                           call("Skill", {"skill": "kensei-toolkit:ticket"}))))

    def test_command_is_used_up(self):
        base = [human("закоммить и запушь"), assistant()]
        once = base + call("Bash", {"command": "git commit -m x"})
        self.assertIsNotNone(run_hook(*bash("git commit --amend --no-edit"), once))
        self.assertIsNone(run_hook(*bash("git push -u origin task/1"), once))
        both = once + call("Bash", {"command": "git push -u origin task/1"})
        self.assertIsNotNone(run_hook(*bash("git push"), both))
        # a call the guard itself denied did not use anything up
        self.assertIsNone(run_hook(*bash("git commit -m x"),
                                   base + denied_call("Bash", {"command": "git commit -m x"})))
        # a later explicit pick grants it again
        again = once + [answer("Ещё раз?", [("Коммит [commit]", None), ("Нет", None)],
                               "Коммит [commit]")]
        self.assertIsNone(run_hook(*bash("git commit --amend --no-edit"), again))

    def test_tags_authorize(self):  # noqa: C901
        q = "Что сделать?"
        opts = [("Коммит в task/1 [commit]", None), ("Push [push]", None),
                ("Статус → In Review [status]", None), ("Ничего", None)]
        picked = [human("готово?"), assistant(),
                  answer(q, opts, "Коммит в task/1 [commit], Push [push]", multi=True)]
        self.assertIsNone(run_hook(*bash("git commit -m x"), picked))
        self.assertIsNone(run_hook(*bash("git push"), picked))
        self.assertIsNotNone(run_hook("mcp__clickup__clickup_update_task", {"status": "x"}, picked))
        none = [human("готово?"), assistant(), answer(q, opts, "Ничего")]
        self.assertIsNotNone(run_hook(*bash("git commit -m x"), none))
        # untagged labels grant nothing, however they are worded
        for label in ["Коммит + push", "Отменить коммит", "Да, коммит", "Skip commit"]:
            entries = [human("?"), assistant(), answer(q, [(label, None), ("Нет", None)], label)]
            self.assertIsNotNone(run_hook(*bash("git commit -m x"), entries), label)
        # a pick with notes grants nothing by itself; the notes are read as typed text
        noted = [human("?"), assistant(),
                 answer(q, opts, "Коммит в task/1 [commit], Push [push]", multi=True,
                        annotations={q: {"notes": "пуш пока не надо"}})]
        self.assertIsNotNone(run_hook(*bash("git push"), noted))
        self.assertIsNotNone(run_hook(*bash("git commit -m x"), noted))
        afk = [human("?"), assistant(), answer(q, opts, "Push [push]", afkTimeoutMs=60000)]
        self.assertIsNotNone(run_hook(*bash("git push"), afk))
        # free text in "Other" is read as typed text
        other = [human("?"), assistant(), answer(q, opts, "закоммить и запушь")]
        self.assertIsNone(run_hook(*bash("git push"), other))
        # an answer before the latest human message does not count
        self.assertIsNotNone(run_hook(*bash("git commit -m x"),
                                      [answer(q, opts, "Коммит в task/1 [commit]"), human("стоп")]))

    def test_comment_needs_approved_preview(self):
        text = "accepted: AC1 proven by test\nbranch task/1-x"
        post = ("mcp__clickup__clickup_create_comment", {"entity_id": "1", "comment_text": text})
        q = "Отправить?"
        opts = [("Отправить как есть [post]", "```\n" + text + "\n```"),
                ("Поправлю сам", None), ("Не отправлять", None)]
        self.assertIsNotNone(run_hook(*post, [human("оставь коммент в задаче")]))
        ok = [human("оставь коммент"), assistant(text), answer(q, opts, "Отправить как есть [post]")]
        self.assertIsNone(run_hook(*post, ok))
        changed = ("mcp__clickup__clickup_create_comment",
                   {"entity_id": "1", "comment_text": text + "\nи ещё строка"})
        self.assertIsNotNone(run_hook(*changed, ok))
        declined = ok[:-1] + [answer(q, opts, "Не отправлять")]
        self.assertIsNotNone(run_hook(*post, declined))
        # the preview must have been shown: printed in full, or displayed by the dialog
        unseen = [human("оставь коммент"), assistant("вот черновик"),
                  answer(q, opts, "Отправить как есть [post]")]
        self.assertIsNotNone(run_hook(*post, unseen))
        dialog = [human("оставь коммент"), assistant("вот черновик"),
                  answer(q, opts, "Отправить как есть [post]",
                         annotations={q: {"preview": opts[0][1]}})]
        self.assertIsNone(run_hook(*post, dialog))
        # a [post] option whose preview is not unique approves nothing
        dup = [human("x"), assistant(text),
               answer(q, [("Отправить [post]", text), ("Не отправлять", text)], "Отправить [post]")]
        self.assertIsNotNone(run_hook(*post, dup))
        # posted once — the same text cannot be posted again
        twice = ok + call(*post)
        self.assertIn("already posted", run_hook(*post, twice))

    def test_gh_comment_body_file(self):
        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as f:
            f.write("report text\n")
        try:
            ok = [human("отпишись"), assistant("report text"),
                  answer("Отправить?", [("post as is [post]", "report text"), ("no", None)],
                         "post as is [post]")]
            self.assertIsNone(run_hook(*bash(f"gh issue comment 3 --body-file {f.name}"), ok))
            self.assertIsNotNone(run_hook(*bash("gh issue comment 3 --body-file -"), ok))
        finally:
            os.unlink(f.name)

    def test_status_and_delete(self):
        upd = ("mcp__clickup__clickup_update_task", {"task_id": "1", "status": "in review"})
        self.assertIsNotNone(run_hook(*upd, [human("оставь коммент")]))
        self.assertIsNone(run_hook(*upd, [human("переведи задачу в ревью")]))
        dele = ("mcp__clickup__clickup_delete_comment", {"comment_id": "9"})
        self.assertIsNotNone(run_hook(*dele, [human("что-то не то")]))
        self.assertIsNone(run_hook(*dele, [human("чет ты не то написал. Удали коммент")]))

    def test_consumption_edges(self):
        base = [human("закоммить"), assistant()]
        # a successful call whose output merely mentions the guard is still used up
        i = "x1"
        echoed = base + [
            {"type": "assistant", "message": {"content": [
                {"type": "tool_use", "id": i, "name": "Bash",
                 "input": {"command": "git commit -m 'fix [ticket guard] Blocked text'"}}]}},
            {"type": "user", "message": {"content": [
                {"type": "tool_result", "tool_use_id": i,
                 "content": "[task/1 abc] fix [ticket guard] Blocked text"}]}}]
        self.assertIsNotNone(run_hook(*bash("git commit --amend --no-edit"), echoed))
        # a call the user rejected at the prompt did not run
        j = "x2"
        rejected = base + [
            {"type": "assistant", "message": {"content": [
                {"type": "tool_use", "id": j, "name": "Bash", "input": {"command": "git commit -m a"}}]}},
            {"type": "user", "message": {"content": [
                {"type": "tool_result", "tool_use_id": j, "is_error": True,
                 "content": "The user doesn't want to proceed with this tool use."}]}}]
        self.assertIsNone(run_hook(*bash("git commit -m a"), rejected))
        # one command, one action — even inside one call
        self.assertIn("one command is one action",
                      run_hook(*bash("git commit -m a && git commit --amend"), base))
        # a status command is used up by one write
        upd = ("mcp__clickup__clickup_update_task", {"task_id": "1", "status": "in review"})
        once = [human("переведи в ревью"), assistant()] + call(*upd)
        self.assertIsNotNone(run_hook("mcp__clickup__clickup_update_task",
                                      {"task_id": "1", "assignees": ["me"]}, once))

    def test_pr_and_push_are_separate(self):
        both = [human("запушь и открой PR"), assistant()] + \
            call("Bash", {"command": "git push -u origin task/1"})
        self.assertIsNone(run_hook(*bash("gh pr create --fill"), both))
        self.assertIsNotNone(run_hook(*bash("git push -u origin task/1"),
                                      [human("открой PR"), assistant()]))

    def test_base_branch_push(self):
        self.assertIsNotNone(run_hook(*bash("git push"), [human("запушь")], cwd=MAINREPO))
        self.assertIsNone(run_hook(*bash("git push"), [human("запушь в main")], cwd=MAINREPO))

    def test_comment_display(self):
        text = "line one\nline two"
        post = ("mcp__clickup__clickup_create_comment", {"comment_text": text})
        q = "Отправить?"
        opts = [("Отправить [post]", text), ("Нет", None)]
        quoted = [human("отпишись"), assistant("> line one\n> line two"),
                  answer(q, opts, "Отправить [post]")]
        self.assertIsNone(run_hook(*post, quoted))
        hidden = [human("отпишись"), assistant("черновик выше"), answer(q, opts, "Отправить [post]")]
        self.assertIn("never shown in full", run_hook(*post, hidden))

    def test_misread_hint(self):
        self.assertIn("mentions it", run_hook(*bash("git push"), [human("запушь, но не сейчас")]))

    def test_force_needs_its_own_command(self):
        self.assertIsNotNone(run_hook(*bash("git push --force"), [human("запушь")]))
        self.assertIsNone(run_hook(*bash("git push --force-with-lease"), [human("форс-пушь")]))
        self.assertIsNotNone(run_hook(*bash("gh pr merge 3"), [human("запушь")]))

    def test_tamper(self):
        sess = "abcdef12-3456"
        entries = [human("закоммить")]
        self.assertIn("off limits", run_hook(
            *bash(f"echo x >> ~/.claude/projects/p/{sess}.jsonl"), entries, session=sess))
        self.assertIn("off limits", run_hook(
            *bash("rm ~/.claude/task-runs/.guard/zz"), entries, session=sess))
        self.assertIn("off limits", run_hook(
            *bash("rm -rf ~/.claude/task-runs"), entries, session=sess))
        self.assertIsNone(run_hook(
            "Write", {"file_path": "/Users/k/.claude/task-runs/PerfectWar/1/RUN.md",
                      "content": "step: rm nothing"}, entries, session=sess))
        self.assertIn("off limits", run_hook(
            "Write", {"file_path": f"/x/{sess}.jsonl", "content": "{}"}, entries, session=sess))
        self.assertIsNone(run_hook("Write", {"file_path": "/x/notes.md", "content": "hi"},
                                   entries, session=sess))

    def test_subagents(self):
        entries = [human("закоммить и запушь")]
        commit = bash("git commit -m x")
        self.assertIsNone(run_hook(*commit, entries, mode="--subagent", session="s-unmarked",
                                   agent="a1"))
        self.assertIsNone(run_hook(*bash("git status"), entries, session="s-ticket"))
        self.assertTrue(os.path.exists(os.path.join(HOME, ".claude/task-runs/.guard/s-ticket")))
        reason = run_hook(*commit, entries, mode="--subagent", session="s-ticket", agent="a1")
        self.assertIn("subagents never commit", reason)
        self.assertIsNotNone(run_hook("mcp__clickup__clickup_update_task", {"status": "x"},
                                      entries, mode="--subagent", session="s-ticket", agent="a1"))
        self.assertIsNotNone(run_hook(*bash("rm ~/.claude/task-runs/.guard/s-ticket"), entries,
                                      mode="--subagent", session="s-ticket", agent="a1"))
        self.assertIsNone(run_hook(*bash("git diff --stat"), entries, mode="--subagent",
                                   session="s-ticket", agent="a1"))
        self.assertIsNone(run_hook(*commit, [human("сделай задачу")], mode="--subagent",
                                   session="s-ticket"))

    def test_fail_closed(self):
        self.assertIn("transcript", run_hook(*bash("git commit -m x"), []) or "")
        run = lambda payload: subprocess.run(
            [sys.executable, os.path.join(HERE, "guard.py")], input=payload,
            capture_output=True, text=True, env=dict(os.environ, HOME=HOME)).stdout
        self.assertIn("deny", run('{"tool_name": "Bash", "tool_input": {"command": "git commit"},'
                                  ' "transcript_path": "/nonexistent.jsonl"}'))
        self.assertIn("deny", run("not json but git commit"))
        self.assertEqual(run("not json at all").strip(), "")

    def test_unrecognized_format(self):
        old = {"type": "user", "message": {"role": "user", "content": "закоммить"}}
        self.assertIn("no message typed by the user", run_hook(*bash("git commit -m x"), [old]))

    def test_output_is_ascii_safe(self):
        reason = run_hook(*bash("git push"), [human("тест \udc80 закоммить")])
        self.assertIsNotNone(reason)


class WrapperTest(unittest.TestCase):
    """The sh wrapper in hooks/hooks.json."""

    def run_wrapper(self, payload, root):
        cmd = json.load(open(os.path.join(HERE, "..", "..", "hooks", "hooks.json")))[
            "hooks"]["PreToolUse"][0]["hooks"][0]["command"]
        return subprocess.run(["sh", "-c", cmd], input=json.dumps(payload), capture_output=True,
                              text=True, env=dict(os.environ, HOME=HOME, CLAUDE_PLUGIN_ROOT=root))

    def test_wrapper(self):
        root = os.path.abspath(os.path.join(HERE, "..", ".."))
        os.makedirs(os.path.join(HOME, ".claude/task-runs/.guard"), exist_ok=True)
        open(os.path.join(HOME, ".claude/task-runs/.guard/w-sess"), "w").close()
        commit = {"tool_name": "Bash", "tool_input": {"command": "git commit -m x"},
                  "session_id": "w-sess"}
        out = self.run_wrapper(commit, root)
        self.assertEqual((out.returncode, out.stdout), (0, ""))  # main-session call: skipped
        out = self.run_wrapper(dict(commit, agent_id="a1"), root)
        self.assertIn("deny", out.stdout)
        out = self.run_wrapper(dict(commit, agent_id="a1", session_id="other"), root)
        self.assertEqual(out.stdout, "")  # unmarked session
        out = self.run_wrapper(dict(commit, agent_id="a1"), "/nonexistent")
        self.assertEqual((out.returncode, out.stdout), (0, ""))  # guard.py missing: no breakage


if __name__ == "__main__":
    unittest.main(verbosity=1)
