#!/usr/bin/env python3
"""Tests for statusline.py, the wrapper and setup.py — run: python3 statusline_test.py"""

import atexit
import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.error
from datetime import datetime
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "statusline.py")
WRAPPER = os.path.join(HERE, "kensei-statusline-wrapper.py")
SETUP = os.path.join(HERE, "..", "skills", "setup", "setup.py")
sys.path.insert(0, HERE)
# Every temp dir of the run (tempfile.mkdtemp() included) lives under one root removed at exit.
tempfile.tempdir = tempfile.mkdtemp(prefix="statusline-test-")
atexit.register(shutil.rmtree, tempfile.tempdir, True)
os.environ["CLAUDE_CONFIG_DIR"] = tempfile.mkdtemp()  # caches go here, not to ~/.claude
os.environ["KENSEI_STATUSLINE_NO_USAGE_FETCH"] = "1"
import statusline  # noqa: E402


def write_jsonl(path, entries):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for e in entries:
            f.write(json.dumps(e) + "\n")


def assistant(model, inp=0, out=0, write=0, write_1h=0, read=0, content=None):
    usage = {"input_tokens": inp, "output_tokens": out,
             "cache_creation_input_tokens": write, "cache_read_input_tokens": read}
    if write_1h is not None:
        usage["cache_creation"] = {"ephemeral_5m_input_tokens": write - write_1h,
                                   "ephemeral_1h_input_tokens": write_1h}
    return {"type": "assistant",
            "message": {"model": model, "usage": usage, "content": content or []}}


def git(repo, *args):
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t",
                    "-c", "commit.gpgsign=false", *args], cwd=repo, check=True,
                   capture_output=True)


def strip_ansi(text):
    import re
    return re.sub(r"\033\[[0-9;]*m", "", text)


class Pricing(unittest.TestCase):
    def test_versions_are_priced_separately(self):
        self.assertEqual(statusline.get_pricing("claude-opus-5-5")["input"], 4.0)
        self.assertEqual(statusline.get_pricing("claude-opus-5")["input"], 5.0)
        self.assertEqual(statusline.get_pricing("claude-fable-5-1")["cache_read"], 0.25)
        self.assertEqual(statusline.get_pricing("claude-fable-5")["cache_read"], 1.0)
        self.assertEqual(statusline.get_pricing("claude-sonnet-5-5")["output"], 10.0)

    def test_id_spellings(self):
        for mid in ("claude-opus-5-5[1m]", "CLAUDE-OPUS-5-5", "anthropic.claude-opus-5-5",
                    "us.anthropic.claude-opus-5-5", "global.anthropic.claude-opus-5-5-v1"):
            self.assertEqual(statusline.get_pricing(mid)["input"], 4.0, mid)
        for mid in ("claude-haiku-4-5-20251001", "claude-haiku-4-5@20251001",
                    "us.anthropic.claude-haiku-4-5-20251001-v1:0"):
            self.assertEqual(statusline.get_pricing(mid)["input"], 1.0, mid)

    def test_bedrock_regional_prefixes_and_arns(self):
        for mid in ("us-gov.anthropic.claude-sonnet-5-5-v1:0",
                    "apac.anthropic.claude-sonnet-5-5-v1:0",
                    "arn:aws:bedrock:us-east-1::foundation-model/anthropic.claude-sonnet-5-5-v1:0",
                    "arn:aws:bedrock:us-gov-west-1:123456789012:inference-profile/"
                    "us-gov.anthropic.claude-sonnet-5-5-20260101-v1:0"):
            self.assertEqual(statusline.normalize_model_id(mid), "claude-sonnet-5-5", mid)
        # an application inference profile names no model: unknown, not guessed
        self.assertIsNone(statusline.get_pricing(
            "arn:aws:bedrock:us-east-1:123456789012:application-inference-profile/abc123"))

    def test_cache_write_multipliers(self):
        p = statusline.get_pricing("claude-opus-5-5")
        self.assertEqual(p["cache_write"], 5.0)
        self.assertEqual(p["cache_write_1h"], 8.0)

    def test_unknown_model_has_no_price(self):
        for mid in ("claude-opus-6", "claude-sonnet-5-7", "gpt-5", "unknown", "<synthetic>"):
            self.assertIsNone(statusline.get_pricing(mid), mid)

    def test_cost_splits_5m_and_1h_writes(self):
        models = {}
        statusline.add_usage(models, assistant("claude-opus-5-5", inp=1_000_000, out=1_000_000,
                                               write=2_000_000, write_1h=1_000_000,
                                               read=1_000_000)["message"])
        cost, unknown = statusline.calc_cost_from_models(models)
        self.assertFalse(unknown)
        self.assertAlmostEqual(cost, 4 + 20 + 5 + 8 + 0.2)

    def test_usage_without_split_counts_as_5m(self):
        models = {}
        statusline.add_usage(models, assistant("claude-opus-5-5", write=1_000_000,
                                               write_1h=None)["message"])
        self.assertEqual(models["claude-opus-5-5"]["cache_write"], 1_000_000)
        self.assertAlmostEqual(statusline.calc_cost_from_models(models)[0], 5.0)

    def test_unknown_model_is_reported_not_guessed(self):
        models = {"claude-opus-9": dict(statusline.empty_tokens(), output=1000)}
        self.assertEqual(statusline.calc_cost_from_models(models), (0.0, True))
        self.assertIn("n/a", strip_ansi(statusline.fmt_cost({}, models)))
        self.assertNotIn("~$0", strip_ansi(statusline.fmt_cost({}, models)))

    def test_partly_unknown_shows_known_part_and_na(self):
        models = {"claude-opus-9": dict(statusline.empty_tokens(), output=1000),
                  "claude-opus-5-5": dict(statusline.empty_tokens(), output=1_000_000)}
        self.assertEqual(strip_ansi(statusline.fmt_cost({}, models)), "~$20.0 + n/a")

    def test_synthetic_model_without_tokens_is_ignored(self):
        models = {"<synthetic>": statusline.empty_tokens(),
                  "claude-sonnet-5-5": dict(statusline.empty_tokens(), output=100_000)}
        self.assertEqual(strip_ansi(statusline.fmt_cost({}, models)), "~$1.00")

    def test_fast_mode_is_not_priced_at_standard_rates(self):
        models = {}
        msg = assistant("claude-opus-5-5", out=1_000_000)["message"]
        msg["usage"]["speed"] = "fast"
        statusline.add_usage(models, msg)
        statusline.add_usage(models, assistant("claude-opus-5-5", out=1_000_000)["message"])
        self.assertEqual(strip_ansi(statusline.fmt_cost({}, models)), "~$20.0 + n/a")

    def test_reported_cost_wins(self):
        models = {"claude-opus-9": dict(statusline.empty_tokens(), output=1000)}
        self.assertEqual(strip_ansi(statusline.fmt_cost({"cost": {"total_cost_usd": 3.5}}, models)),
                         "$3.50")


class Subagents(unittest.TestCase):
    def test_glob_finds_workflow_subagents(self):
        root = tempfile.mkdtemp()
        transcript = os.path.join(root, "sess.jsonl")
        write_jsonl(transcript, [])
        sub = os.path.join(root, "sess", "subagents")
        write_jsonl(os.path.join(sub, "agent-a1.jsonl"), [assistant("claude-opus-5-5", out=10)])
        write_jsonl(os.path.join(sub, "workflows", "wf_1", "agent-b2.jsonl"),
                    [assistant("claude-opus-5-5", out=100), assistant("claude-haiku-4-5", out=5)])
        write_jsonl(os.path.join(sub, "workflows", "wf_1", "journal.jsonl"),
                    [assistant("claude-opus-5-5", out=1000)])
        write_jsonl(os.path.join(sub, "agent-acompact-x.jsonl"),
                    [assistant("claude-opus-5-5", out=10000)])
        found = [os.path.relpath(p, sub) for p in statusline.subagent_transcripts(transcript)]
        self.assertEqual(sorted(found), ["agent-a1.jsonl",
                                         os.path.join("workflows", "wf_1", "agent-b2.jsonl")])
        tokens = statusline.get_subagent_tokens(transcript)
        self.assertEqual(tokens["claude-opus-5-5"]["output"], 110)
        self.assertEqual(tokens["claude-haiku-4-5"]["output"], 5)

    def test_no_subagent_dir(self):
        self.assertEqual(statusline.get_subagent_tokens("/nonexistent/sess.jsonl"), {})


class ProjectStats(unittest.TestCase):
    def setUp(self):
        self.repo = tempfile.mkdtemp()
        git(self.repo, "init", "-q", "-b", "main")
        with open(os.path.join(self.repo, "a.txt"), "w") as f:
            f.write("1\n2\n3\n")
        git(self.repo, "add", "a.txt")
        git(self.repo, "commit", "-q", "-m", "init")

    def test_head_sha_and_cache(self):
        line, head = statusline.get_git_info(self.repo)
        self.assertIn("main", strip_ansi(line))
        self.assertRegex(head, r"^[0-9a-f]{40}$")
        self.assertEqual(statusline.get_project_stats(self.repo, head), "1 files 3 loc")
        real = statusline.count_project
        statusline.count_project = lambda cwd: self.fail("cache miss for a known HEAD")
        try:
            self.assertEqual(statusline.get_project_stats(self.repo, head), "1 files 3 loc")
        finally:
            statusline.count_project = real

    def test_unborn_branch(self):
        repo = tempfile.mkdtemp()
        git(repo, "init", "-q", "-b", "main")
        line, head = statusline.get_git_info(repo)
        self.assertIn("main", strip_ansi(line))
        self.assertIsNone(head)
        self.assertIsNone(statusline.get_project_stats(repo, head))


class Render(unittest.TestCase):
    def test_smoke(self):
        root = tempfile.mkdtemp()
        repo = os.path.join(root, "repo")
        os.makedirs(repo)
        git(repo, "init", "-q", "-b", "feature")
        transcript = os.path.join(root, "sess.jsonl")
        write_jsonl(transcript, [
            assistant("claude-opus-5-5", inp=10, out=1000, write=5000, write_1h=5000, read=20000,
                      content=[{"type": "tool_use", "name": "Agent", "id": "t1",
                                "input": {"subagent_type": "Explore"}}]),
            {"type": "assistant", "message": {"model": "<synthetic>", "content": []}},
        ])
        write_jsonl(os.path.join(root, "sess", "subagents", "workflows", "wf", "agent-x.jsonl"),
                    [assistant("claude-sonnet-5-5", out=2000)])
        stdin = {"model": {"id": "claude-opus-5-5", "display_name": "Opus 5.5"},
                 "context_window": {"used_percentage": 42},
                 "transcript_path": transcript, "cwd": repo,
                 "cost": {"total_lines_added": 3, "total_lines_removed": 1},
                 "rate_limits": {"five_hour": {"used_percentage": 24, "resets_at": 4102444800},
                                 "seven_day": {"used_percentage": 41}}}
        out = subprocess.run([sys.executable, SCRIPT], input=json.dumps(stdin),
                             capture_output=True, text=True, timeout=20)
        self.assertEqual(out.returncode, 0, out.stderr)
        lines = strip_ansi(out.stdout).splitlines()
        self.assertEqual(len(lines), 3, out.stdout)
        self.assertTrue(lines[0].startswith("Opus 5.5 │"), lines[0])
        self.assertIn("42%", lines[0])
        self.assertIn("↑25.0K", lines[0])        # last call's input + cache write + cache read
        self.assertIn("↓3.0K", lines[0])          # main + workflow subagent output
        self.assertIn("~$0.", lines[0])
        self.assertIn("1 agent (Explore)", lines[0])
        self.assertIn("5h 24%", lines[1])
        self.assertIn("7d 41%", lines[1])
        self.assertTrue(lines[2].startswith("feature"), lines[2])
        self.assertIn("+3 -1", lines[2])

    def test_bad_stdin(self):
        out = subprocess.run([sys.executable, SCRIPT], input="not json",
                             capture_output=True, text=True, timeout=10)
        self.assertEqual(out.stdout.strip(), "...")

    def render(self, stdin):
        """main() in-process, so its lines count in coverage; returns the plain output lines."""
        with mock.patch.object(sys, "stdin", io.StringIO(json.dumps(stdin))), \
                mock.patch("sys.stdout", new_callable=io.StringIO) as out:
            statusline.main()
        return strip_ansi(out.getvalue()).splitlines()

    def test_in_process_render_with_background_agents(self):
        root = tempfile.mkdtemp()
        repo = os.path.join(root, "repo")
        os.makedirs(repo)
        git(repo, "init", "-q", "-b", "main")
        with open(os.path.join(repo, "a.txt"), "w") as f:
            f.write("x\n")
        git(repo, "add", "a.txt")
        git(repo, "commit", "-q", "-m", "init")
        with open(os.path.join(repo, "a.txt"), "a") as f:
            f.write("y\n")
        open(os.path.join(repo, "new.txt"), "w").close()
        agent = lambda tid, kind: {"type": "tool_use", "name": "Agent", "id": tid,  # noqa: E731
                                   "input": {"subagent_type": kind}}
        transcript = os.path.join(root, "sess.jsonl")
        write_jsonl(transcript, [
            assistant("claude-opus-5-5", inp=1000, out=500, content=[
                agent("fg", "Explore"), agent("bg1", "Plan"), agent("bg2", "Plan"),
                agent("done", "Review")]),
            {"type": "user", "message": {"content": [
                {"type": "tool_result", "tool_use_id": "bg1",
                 "content": [{"type": "text", "text": "Async agent launched"}]},
                {"type": "tool_result", "tool_use_id": "bg2", "content": "Async agent launched"},
                {"type": "tool_result", "tool_use_id": "done", "content": "finished"},
                {"type": "tool_result", "tool_use_id": "other", "content": "x"}]}},
            {"type": "user", "message": "plain text"},
            {"type": "queue-operation", "content": "<tool-use-id>bg2</tool-use-id> completed"},
        ])
        with open(transcript, "a") as f:
            f.write("{not json\n")
        lines = self.render({"model": {"display_name": "Opus 5.5"},
                             "context_window": {"used_percentage": 90},
                             "transcript_path": transcript, "workspace": {"current_dir": repo},
                             "cost": {"total_cost_usd": 12.34}})
        self.assertEqual(len(lines), 2, lines)  # no rate_limits, no usage cache: no limits line
        self.assertIn("$12.3", lines[0])
        self.assertIn("2 agents (Explore, Plan)", lines[0])
        self.assertTrue(lines[1].startswith("main │ +1 ?1 │ 1 files 1 loc"), lines[1])

    def test_in_process_render_minimal(self):
        self.assertEqual(self.render({}), ["? │ ░░░░░░░░░░ 0% │ ↑0 ↓0 │ ~$0.00"])


class Formatting(unittest.TestCase):
    def test_parse_reset(self):
        self.assertAlmostEqual(  # nine fractional digits: more than Python 3.9 parses
            statusline.parse_reset("2026-10-01T12:00:00.123456789Z").timestamp(),
            statusline.parse_reset(1790856000.123456).timestamp(), places=5)
        self.assertIsNotNone(statusline.parse_reset("2026-10-01T12:00:00+03:00"))
        for bad in ("soon", None, 10 ** 20, [1]):
            self.assertIsNone(statusline.parse_reset(bad), bad)

    def test_tokens_bar_and_colors(self):
        self.assertEqual(statusline.fmt_tokens(2_500_000), "2.5M")
        self.assertEqual(statusline.fmt_tokens(999), "999")
        self.assertEqual(statusline.make_bar(150, 4), "▓▓▓▓")
        self.assertEqual(statusline.make_bar(-5, 4), "░░░░")
        self.assertEqual([statusline.pct_color(p) for p in (10, 50, 80)],
                         ["\033[32m", "\033[33m", "\033[31m"])


# --- Usage limits: OAuth token, detached refresh, backoff, server rows ------------------------

FUTURE = 4102444800  # 2100-01-01


def fable_row(pct=11, severity=None, resets_at=FUTURE):
    return {"kind": "weekly_model", "group": "weekly", "percent": pct, "resets_at": resets_at,
            "severity": severity, "scope": {"model": {"display_name": "Fable"}}}


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


class UsageBase(unittest.TestCase):
    """Each test gets its own cache file; the fetch switch the rest of the suite sets is off."""

    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.cache = os.path.join(self.dir, "cache", "kensei-statusline", "usage.json")
        self.lock = self.cache + ".lock"
        for patch in (mock.patch.object(statusline, "USAGE_CACHE", self.cache),
                      mock.patch.object(statusline, "CONFIG_DIR", self.dir),
                      mock.patch.dict(os.environ)):
            patch.start()
            self.addCleanup(patch.stop)
        for key in ("KENSEI_STATUSLINE_NO_USAGE_FETCH", "CLAUDE_CONFIG_DIR",
                    "CLAUDE_SECURESTORAGE_CONFIG_DIR", *statusline.THIRD_PARTY):
            os.environ.pop(key, None)

    def write_cache(self, cache):
        os.makedirs(os.path.dirname(self.cache), exist_ok=True)
        with open(self.cache, "w") as f:
            json.dump(cache, f)

    def read_cache(self):
        with open(self.cache) as f:
            return json.load(f)


class OAuthToken(UsageBase):
    def keychain(self, stdout, code=0):
        return mock.patch.object(statusline.subprocess, "run", return_value=subprocess.CompletedProcess(
            [], code, stdout=stdout, stderr=""))

    @staticmethod
    def creds(token="tok", expires_in=3600):
        return json.dumps({"claudeAiOauth": {"accessToken": token,
                                             "expiresAt": (time.time() + expires_in) * 1000}})

    def test_keychain_service_name(self):
        self.assertEqual(statusline.keychain_service(), "Claude Code-credentials")
        os.environ["CLAUDE_CONFIG_DIR"] = "/x/cfg"
        digest = hashlib.sha256(b"/x/cfg").hexdigest()[:8]
        self.assertEqual(statusline.keychain_service(), f"Claude Code-credentials-{digest}")
        os.environ["CLAUDE_SECURESTORAGE_CONFIG_DIR"] = ""  # set but empty: the default item
        self.assertEqual(statusline.keychain_service(), "Claude Code-credentials")

    def test_keychain_token(self):
        with mock.patch.object(sys, "platform", "darwin"), self.keychain(self.creds()) as run:
            self.assertEqual(statusline.read_oauth_token(), "tok")
        self.assertIn("Claude Code-credentials", run.call_args[0][0])

    def test_expired_or_malformed_token_is_skipped(self):
        for raw in (self.creds(expires_in=30), self.creds(token=""), "{bad",
                    json.dumps({"claudeAiOauth": "x"}), json.dumps([1])):
            with mock.patch.object(sys, "platform", "darwin"), self.keychain(raw):
                self.assertIsNone(statusline.read_oauth_token(), raw)

    def test_credentials_file_when_keychain_has_nothing(self):
        with mock.patch.object(sys, "platform", "darwin"), self.keychain("", code=44):
            self.assertIsNone(statusline.read_oauth_token())  # no file either
            with open(os.path.join(self.dir, ".credentials.json"), "w") as f:
                f.write(self.creds(token="from-file"))
            self.assertEqual(statusline.read_oauth_token(), "from-file")
        with mock.patch.object(sys, "platform", "darwin"), \
                mock.patch.object(statusline.subprocess, "run", side_effect=OSError):
            self.assertEqual(statusline.read_oauth_token(), "from-file")
        with mock.patch.object(sys, "platform", "linux"), \
                mock.patch.object(statusline.subprocess, "run") as run:
            self.assertEqual(statusline.read_oauth_token(), "from-file")
        run.assert_not_called()


class UsageCache(UsageBase):
    def test_missing_broken_or_odd_cache_reads_empty(self):
        self.assertEqual(statusline.load_usage_cache(), {})
        os.makedirs(os.path.dirname(self.cache))
        with open(self.cache, "w") as f:
            f.write("{bad")
        self.assertEqual(statusline.load_usage_cache(), {})
        self.write_cache([1, 2])
        self.assertEqual(statusline.load_usage_cache(), {})

    def test_far_future_times_and_bad_rows_are_dropped(self):
        now = time.time()
        self.write_cache({"fetched_at": now + 10 ** 6, "next_try": "soon", "rows": {"a": 1}})
        self.assertEqual(statusline.load_usage_cache(), {})
        self.write_cache({"fetched_at": now, "next_try": now + 600, "rows": []})
        self.assertEqual(statusline.load_usage_cache(),
                         {"fetched_at": now, "next_try": now + 600, "rows": []})

    def test_save_leaves_no_temp_file_on_error(self):
        statusline.save_usage_cache({"rows": []})
        self.assertEqual(self.read_cache(), {"rows": []})
        with mock.patch.object(statusline.os, "replace", side_effect=OSError("disk")):
            with self.assertRaises(OSError):
                statusline.save_usage_cache({"rows": [1]})
        self.assertEqual(os.listdir(os.path.dirname(self.cache)), ["usage.json"])


class RefreshUsage(UsageBase):
    """refresh_usage() with the keychain and urllib stubbed: what lands in the cache, and when the
    next attempt is allowed."""

    def setUp(self):
        super().setUp()
        self.now = 1_800_000_000.0
        for patch in (mock.patch.object(statusline.time, "time", return_value=self.now),
                      mock.patch.object(statusline, "read_oauth_token", return_value="tok")):
            patch.start()
            self.addCleanup(patch.stop)
        self.old_rows = [fable_row(5)]
        self.write_cache({"fetched_at": self.now - 400, "next_try": self.now - 1,
                          "rows": self.old_rows})
        open(self.lock, "w").close()  # maybe_refresh_usage takes it before spawning a refresh
        timer = mock.patch("threading.Timer")  # refresh_usage imports threading lazily
        self.timer = timer.start()
        self.addCleanup(timer.stop)
        self.addCleanup(self.check_deadline_timer)  # cleanups run last-in first-out: before stop

    def check_deadline_timer(self):
        """Every refresh arms the os._exit deadline and disarms it on the way out."""
        runs = self.timer.call_count
        self.assertGreater(runs, 0)
        self.timer.assert_called_with(statusline.REFRESH_DEADLINE, os._exit, (1,))
        self.assertEqual(self.timer.return_value.start.call_count, runs)
        self.assertEqual(self.timer.return_value.cancel.call_count, runs)

    def refresh(self, response=None, error=None):
        """Run one refresh; the opener returns `response` (a JSON body) or raises `error`."""
        seen = {}

        def open_(req, timeout):
            seen["request"], seen["cache_during"] = req, self.read_cache()
            if error:
                raise error
            return FakeResponse(json.dumps(response).encode())

        def build_opener(*handlers):
            seen["handlers"] = handlers
            return mock.Mock(open=open_)

        with mock.patch("urllib.request.build_opener", side_effect=build_opener):
            statusline.refresh_usage()
        self.assertFalse(os.path.exists(self.lock), "the lock is released")
        return seen, self.read_cache()

    def http_error(self, code):
        return urllib.error.HTTPError(statusline.USAGE_URL, code, "x", {}, None)

    def test_success_replaces_rows(self):
        seen, cache = self.refresh({"limits": [fable_row(11), "junk", None]})
        self.assertEqual(cache, {"fetched_at": self.now, "next_try": self.now + statusline.USAGE_TTL,
                                 "rows": [fable_row(11)]})
        req = seen["request"]
        self.assertEqual(req.full_url, statusline.USAGE_URL)
        self.assertEqual(req.get_header("Authorization"), "Bearer tok")
        # the next attempt is pushed back before the request goes out
        self.assertEqual(seen["cache_during"]["next_try"], self.now + statusline.ERROR_BACKOFF)
        self.assertEqual(seen["cache_during"]["error"], "interrupted")
        # redirects are refused, so the token never leaves api.anthropic.com
        handler = seen["handlers"][0]()
        self.assertIsNone(handler.redirect_request(req, None, 302, "Found", {}, "https://evil/"))

    def test_body_without_limits_clears_rows(self):
        for body in ({"other": 1}, ["x"]):
            self.write_cache({"next_try": 0, "rows": self.old_rows})
            _, cache = self.refresh(body)
            self.assertEqual(cache["rows"], [], body)

    def test_backoff_per_http_code(self):
        for code, wait in ((401, 600), (403, 3600), (429, 900), (500, statusline.ERROR_BACKOFF)):
            self.write_cache({"fetched_at": self.now - 400, "next_try": 0, "rows": self.old_rows})
            _, cache = self.refresh(error=self.http_error(code))
            self.assertEqual(cache["next_try"], self.now + wait, code)
            self.assertEqual(cache["error"], f"HTTP {code}")
            self.assertEqual(cache["rows"], self.old_rows, "the last good rows survive an error")
            self.assertEqual(cache["fetched_at"], self.now - 400)

    def test_network_error_keeps_only_the_type_name(self):
        _, cache = self.refresh(error=urllib.error.URLError("secret detail"))
        self.assertEqual(cache["error"], "URLError")
        self.assertEqual(cache["next_try"], self.now + statusline.ERROR_BACKOFF)
        self.assertEqual(cache["rows"], self.old_rows)

    def test_bad_json_body(self):
        def open_(req, timeout):
            return FakeResponse(b"<html>")
        with mock.patch("urllib.request.build_opener", return_value=mock.Mock(open=open_)):
            statusline.refresh_usage()
        cache = self.read_cache()
        self.assertEqual(cache["error"], "JSONDecodeError")
        self.assertEqual(cache["rows"], self.old_rows)

    def test_no_token_drops_rows(self):
        with mock.patch.object(statusline, "read_oauth_token", return_value=None):
            seen, cache = self.refresh({"limits": []})
        self.assertNotIn("request", seen)
        self.assertEqual(cache["rows"], [])
        self.assertEqual(cache["error"], "no valid token")
        self.assertEqual(cache["next_try"], self.now + statusline.BACKOFF[401])

    def test_not_due_yet_sends_nothing(self):
        self.write_cache({"next_try": self.now + 100, "rows": self.old_rows})
        seen, cache = self.refresh({"limits": []})
        self.assertNotIn("request", seen)
        self.assertEqual(cache, {"next_try": self.now + 100, "rows": self.old_rows})

    def test_unexpected_failure_still_backs_off(self):
        with mock.patch.object(statusline, "read_oauth_token", side_effect=RuntimeError("boom")):
            statusline.refresh_usage()
        cache = self.read_cache()
        self.assertEqual(cache["error"], "RuntimeError")
        self.assertEqual(cache["next_try"], self.now + statusline.ERROR_BACKOFF)
        self.assertFalse(os.path.exists(self.lock))


class MaybeRefresh(UsageBase):
    def setUp(self):
        super().setUp()
        patch = mock.patch.object(statusline.subprocess, "Popen")
        self.popen = patch.start()
        self.addCleanup(patch.stop)

    def test_due_cache_spawns_one_detached_refresh(self):
        statusline.maybe_refresh_usage({})
        self.popen.assert_called_once()
        args, kwargs = self.popen.call_args
        self.assertEqual(args[0][1:], [os.path.abspath(statusline.__file__), "--refresh-usage"])
        self.assertTrue(kwargs.get("start_new_session") or kwargs.get("creationflags"))
        self.assertTrue(os.path.exists(self.lock))
        statusline.maybe_refresh_usage({})  # a second render while it runs: the lock holds
        self.popen.assert_called_once()

    def test_stale_lock_is_taken_over(self):
        os.makedirs(os.path.dirname(self.lock))
        open(self.lock, "w").close()
        old = time.time() - statusline.REFRESH_LOCK_TTL - 5
        os.utime(self.lock, (old, old))
        statusline.maybe_refresh_usage({})
        self.popen.assert_called_once()
        self.assertGreater(os.path.getmtime(self.lock), old + 1)

    def test_not_due_or_switched_off(self):
        statusline.maybe_refresh_usage({"next_try": time.time() + 60})
        os.environ["KENSEI_STATUSLINE_NO_USAGE_FETCH"] = "1"
        statusline.maybe_refresh_usage({})
        self.popen.assert_not_called()
        self.assertFalse(os.path.exists(self.lock))

    def test_spawn_failure_is_silent(self):
        self.popen.side_effect = OSError("no exec")
        statusline.maybe_refresh_usage({})


class ServerRows(UsageBase):
    """The limits line: Claude Code's 5h / 7d windows plus the rows from the usage cache."""

    def setUp(self):
        super().setUp()
        patch = mock.patch.object(statusline.subprocess, "Popen")
        self.popen = patch.start()
        self.addCleanup(patch.stop)
        self.stdin = {"rate_limits": {"five_hour": {"used_percentage": 24, "resets_at": FUTURE},
                                      "seven_day": {"used_percentage": 41}}}

    def rows(self, *rows, age=10):
        self.write_cache({"fetched_at": time.time() - age, "next_try": time.time() + 60,
                          "rows": list(rows)})

    def line(self, data=None):
        out = statusline.fmt_rate_limits(self.stdin if data is None else data)
        return out if out is None else strip_ansi(out)

    def test_fable_row_follows_the_stdin_windows(self):
        self.rows({"kind": "session", "group": "session", "percent": 99},
                  {"kind": "weekly_all", "percent": 99}, fable_row(11))
        self.assertRegex(self.line(), r"^5h 24% ↻ \d\d:\d\d · 7d 41% · Fable 11% ↻ \d\d\.\d\d$")

    def test_server_severity_colours_the_row(self):
        self.rows(fable_row(30, severity="critical"))
        raw = statusline.fmt_rate_limits(self.stdin)
        self.assertIn("\033[31m30%", raw)  # red although 30% alone would be green
        self.rows(fable_row(30))
        self.assertIn("\033[32m30%", statusline.fmt_rate_limits(self.stdin))

    def test_cache_fills_in_windows_stdin_lacks(self):
        self.rows({"kind": "session", "group": "session", "percent": 7, "resets_at": FUTURE},
                  fable_row(11))
        self.stdin["rate_limits"].pop("five_hour")
        self.assertRegex(self.line(), r"^5h 7% ↻ \d\d:\d\d · 7d 41% · Fable 11%")

    def test_stale_cache_is_not_shown(self):
        self.rows(fable_row(11), age=statusline.USAGE_MAX_AGE + 1)
        self.assertEqual(self.line(), "5h 24% ↻ " + datetime.fromtimestamp(FUTURE).strftime("%H:%M")
                         + " · 7d 41%")
        self.rows(fable_row(11), age=-120)  # fetched "in the future": a clock jump
        self.assertNotIn("Fable", self.line())

    def test_odd_rows_are_skipped_not_fatal(self):
        self.rows(fable_row(float("nan")), fable_row(50, resets_at=1),  # NaN; window already reset
                  {"kind": "weekly_x", "percent": 3, "resets_at": "garbage",
                   "scope": {"surface": {"display_name": "Code"}}},
                  {"kind": "weird", "percent": 1, "scope": "not a dict"},
                  {"percent": 2}, "junk")
        with mock.patch.object(statusline, "fmt_usage_row",
                               side_effect=[None, None, "A", RuntimeError, "B"]):
            self.assertTrue(self.line().endswith("· A · B"))
        line = self.line()
        self.assertNotIn("Fable", line)
        self.assertIn("Code 3%", line)
        self.assertIn("weird 1%", line)
        self.assertIn("? 2%", line)

    def test_due_cache_starts_a_refresh_for_subscribers_only(self):
        self.write_cache({"fetched_at": time.time() - 500, "next_try": time.time() - 1, "rows": []})
        self.line()
        self.popen.assert_called_once()
        os.unlink(self.lock)
        self.popen.reset_mock()
        # before the first response nobody knows the plan: rows are read, nothing is fetched
        self.rows(fable_row(11))
        self.assertEqual(self.line({}), "Fable 11% ↻ "
                         + datetime.fromtimestamp(FUTURE).strftime("%d.%m"))
        self.popen.assert_not_called()

    def test_api_key_and_third_party_sessions_show_nothing(self):
        self.rows(fable_row(11))
        self.assertIsNone(self.line({"cost": {"total_api_duration_ms": 1200}}))
        os.environ["CLAUDE_CODE_USE_BEDROCK"] = "1"
        self.assertIsNone(self.line({}))
        self.popen.assert_not_called()

    def test_broken_server_rows_never_lose_the_line(self):
        with mock.patch.object(statusline, "server_rows", side_effect=RuntimeError):
            self.assertRegex(self.line(), r"^5h 24% ↻ \d\d:\d\d · 7d 41%$")


def make_install(cache, version, orphaned=False, marker="ok"):
    d = os.path.join(cache, version)
    os.makedirs(os.path.join(d, "scripts"), exist_ok=True)
    with open(os.path.join(d, "scripts", "statusline.py"), "w") as f:
        f.write(f"print({marker!r})\n")
    if orphaned:
        open(os.path.join(d, ".orphaned_at"), "w").close()
    return d


class Wrapper(unittest.TestCase):
    def run_wrapper(self, config, cwd=None):
        env = dict(os.environ, CLAUDE_CONFIG_DIR=config)
        return subprocess.run([sys.executable, WRAPPER], input="{}", capture_output=True,
                              text=True, env=env, cwd=cwd or config, timeout=10).stdout.strip()

    def test_installed_plugins_wins_over_highest_cache_version(self):
        config = tempfile.mkdtemp()
        cache = os.path.join(config, "plugins", "cache", "kensei-claude-plugins", "kensei-statusline")
        installed = make_install(cache, "1.5.0", marker="installed")
        make_install(cache, "1.10.0", marker="stray")
        with open(os.path.join(config, "plugins", "installed_plugins.json"), "w") as f:
            json.dump({"version": 2, "plugins": {"kensei-statusline@kensei-claude-plugins": [
                {"scope": "user", "installPath": installed, "version": "1.5.0"}]}}, f)
        self.assertEqual(self.run_wrapper(config), "installed")

    def test_project_install_for_this_project_first(self):
        config, project = tempfile.mkdtemp(), tempfile.mkdtemp()
        cache = os.path.join(config, "plugins", "cache", "kensei-claude-plugins", "kensei-statusline")
        user = make_install(cache, "1.5.0", marker="user")
        proj = make_install(cache, "1.6.0", marker="project")
        with open(os.path.join(config, "plugins", "installed_plugins.json"), "w") as f:
            json.dump({"plugins": {"kensei-statusline@kensei-claude-plugins": [
                {"scope": "user", "installPath": user},
                {"scope": "project", "installPath": proj, "projectPath": project}]}}, f)
        self.assertEqual(self.run_wrapper(config), "user")
        self.assertEqual(self.run_wrapper(config, cwd=project), "project")

    def test_orphaned_copies_are_skipped(self):
        config = tempfile.mkdtemp()
        cache = os.path.join(config, "plugins", "cache", "kensei-claude-plugins", "kensei-statusline")
        orphan = make_install(cache, "1.8.1", orphaned=True, marker="orphan")
        make_install(cache, "1.4.0", marker="fallback")
        with open(os.path.join(config, "plugins", "installed_plugins.json"), "w") as f:
            json.dump({"plugins": {"kensei-statusline@kensei-claude-plugins": [
                {"scope": "user", "installPath": orphan}]}}, f)
        self.assertEqual(self.run_wrapper(config), "fallback")

    def test_not_installed(self):
        self.assertIn("not installed", self.run_wrapper(tempfile.mkdtemp()))


class Setup(unittest.TestCase):
    def run_setup(self, config, *args):
        env = dict(os.environ, CLAUDE_CONFIG_DIR=config)
        out = subprocess.run([sys.executable, SETUP, *args], capture_output=True, text=True,
                             env=env, timeout=10)
        return out.returncode, json.loads(out.stdout)

    def test_keeps_user_fields_and_backs_up(self):
        config = tempfile.mkdtemp()
        settings = {"model": "opus", "statusLine": {"type": "command", "command": "old",
                                                    "refreshInterval": 5, "padding": 1}}
        path = os.path.join(config, "settings.json")
        with open(path, "w") as f:
            json.dump(settings, f)
        open(os.path.join(config, ".statusline-no-setup"), "w").close()

        code, dry = self.run_setup(config, "--dry-run")
        self.assertEqual(code, 0)
        with open(path) as f:
            self.assertEqual(json.load(f), settings)  # a dry run touches nothing
        self.assertFalse(os.path.exists(os.path.join(config, "scripts")))

        code, report = self.run_setup(config)
        self.assertEqual(code, 0)
        with open(path) as f:
            new = json.load(f)
        self.assertEqual(new["model"], "opus")
        self.assertEqual(new["statusLine"]["refreshInterval"], 5)
        self.assertEqual(new["statusLine"]["padding"], 1)
        self.assertIn("kensei-statusline.py", new["statusLine"]["command"])
        with open(report["backup"]) as f:
            self.assertEqual(json.load(f), settings)
        self.assertTrue(os.path.isfile(os.path.join(config, "scripts", "kensei-statusline.py")))
        self.assertFalse(os.path.exists(os.path.join(config, ".statusline-no-setup")))

        code, again = self.run_setup(config)  # nothing changes, so no second backup
        self.assertIsNone(again["backup"])

    def test_symlinked_settings_is_written_through(self):
        root = tempfile.mkdtemp()
        config, dot = os.path.join(root, "config"), os.path.join(root, "dot")
        os.makedirs(config)
        os.makedirs(dot)
        target = os.path.join(dot, "settings.json")
        with open(target, "w") as f:
            json.dump({"model": "opus"}, f)
        os.chmod(target, 0o600)
        link = os.path.join(config, "settings.json")
        os.symlink(os.path.join("..", "dot", "settings.json"), link)

        code, report = self.run_setup(config)
        self.assertEqual(code, 0)
        self.assertTrue(os.path.islink(link))
        with open(target) as f:
            new = json.load(f)
        self.assertEqual(new["model"], "opus")
        self.assertIn("kensei-statusline.py", new["statusLine"]["command"])
        self.assertEqual(os.stat(target).st_mode & 0o777, 0o600)
        for d in (config, dot):  # no stray temp file left behind
            self.assertFalse([n for n in os.listdir(d) if n.endswith(".tmp")], d)

    def test_reports_local_override(self):
        config = tempfile.mkdtemp()
        with open(os.path.join(config, "settings.local.json"), "w") as f:
            json.dump({"statusLine": {"type": "command", "command": "other"}}, f)
        code, report = self.run_setup(config, "--dry-run")
        self.assertEqual(code, 0)
        self.assertEqual(report["local_override_status_line"]["command"], "other")

        config = tempfile.mkdtemp()
        code, report = self.run_setup(config, "--dry-run")
        self.assertIsNone(report["local_override_status_line"])

    def test_no_settings_file(self):
        config = tempfile.mkdtemp()
        code, report = self.run_setup(config)
        self.assertEqual(code, 0)
        self.assertIsNone(report["backup"])
        with open(os.path.join(config, "settings.json")) as f:
            self.assertEqual(json.load(f)["statusLine"]["type"], "command")

    def test_invalid_settings_is_left_alone(self):
        config = tempfile.mkdtemp()
        with open(os.path.join(config, "settings.json"), "w") as f:
            f.write("{broken")
        code, report = self.run_setup(config)
        self.assertEqual(code, 1)
        self.assertIn("error", report)
        with open(os.path.join(config, "settings.json")) as f:
            self.assertEqual(f.read(), "{broken")


if __name__ == "__main__":
    unittest.main(verbosity=1)
