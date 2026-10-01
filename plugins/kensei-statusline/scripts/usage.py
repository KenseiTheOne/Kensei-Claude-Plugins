#!/usr/bin/env python3
"""Kensei Statusline — subscription usage rows fetched from the claude.ai usage endpoint.

Claude Code hands the statusline only the five_hour / seven_day windows. Every other meter — a
separate weekly Fable limit, or whatever the server adds next — exists only in the rows
(`limits[]`) of the usage endpoint that /usage renders. statusline.py reads them from a small
cache (load_usage_cache) and calls maybe_refresh_usage, which starts this file detached with
--refresh-usage, so rendering never waits on the network.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import time
import unicodedata

USAGE_URL = "https://api.anthropic.com/api/oauth/usage"
CONFIG_DIR = os.environ.get("CLAUDE_CONFIG_DIR") or os.path.join(os.path.expanduser("~"), ".claude")
USAGE_CACHE = os.path.join(CONFIG_DIR, "cache", "kensei-statusline", "usage.json")
USAGE_TTL = 180            # seconds between refreshes
USAGE_MAX_AGE = 3600       # rows older than this are not shown
REFRESH_DEADLINE = 30      # a refresh child exits after this, whatever it is waiting on
REFRESH_LOCK_TTL = 60      # a lock older than this belongs to a dead refresh
ERROR_BACKOFF = 300
BACKOFF = {401: 600, 403: 3600, 429: 900}


def keychain_service() -> str:
    """The keychain item Claude Code keeps its login in: suffixed per config dir when
    CLAUDE_CONFIG_DIR (or CLAUDE_SECURESTORAGE_CONFIG_DIR) is set, as Claude Code does."""
    secure = os.environ.get("CLAUDE_SECURESTORAGE_CONFIG_DIR")
    if secure is not None:
        default, base = not secure, secure
    else:
        default, base = not os.environ.get("CLAUDE_CONFIG_DIR"), os.environ.get("CLAUDE_CONFIG_DIR", "")
    if default:
        return "Claude Code-credentials"
    digest = hashlib.sha256(unicodedata.normalize("NFC", base).encode()).hexdigest()[:8]
    return f"Claude Code-credentials-{digest}"


def read_oauth_token() -> str | None:
    """The OAuth access token, read where Claude Code keeps it. Never refreshed here: a refresh
    rotates the refresh token and would log Claude Code itself out. An expired token is skipped —
    Claude Code renews it on its next request."""
    raw = None
    if sys.platform == "darwin":
        try:
            out = subprocess.run(["/usr/bin/security", "find-generic-password", "-s",
                                  keychain_service(), "-w"],
                                 capture_output=True, text=True, timeout=3)
            raw = out.stdout.strip() if out.returncode == 0 else None
        except (OSError, subprocess.SubprocessError):
            raw = None
    if not raw:
        try:
            with open(os.path.join(CONFIG_DIR, ".credentials.json"), encoding="utf-8") as f:
                raw = f.read()
        except OSError:
            return None
    try:
        oauth = json.loads(raw).get("claudeAiOauth")
    except (ValueError, AttributeError):
        return None
    if not isinstance(oauth, dict):
        return None
    token, expires = oauth.get("accessToken"), oauth.get("expiresAt")
    if not isinstance(token, str) or not token:
        return None
    if isinstance(expires, (int, float)) and expires / 1000 < time.time() + 60:
        return None
    return token


def load_usage_cache() -> dict:
    try:
        with open(USAGE_CACHE, encoding="utf-8") as f:
            cache = json.load(f)
    except (OSError, ValueError):
        return {}
    if not isinstance(cache, dict):
        return {}
    limit = time.time() + max(BACKOFF.values())
    for key in ("fetched_at", "next_try"):  # a hand edit or a clock jump must not wedge it
        if not isinstance(cache.get(key), (int, float)) or cache[key] > limit:
            cache.pop(key, None)
    if not isinstance(cache.get("rows"), list):
        cache.pop("rows", None)
    return cache


def save_usage_cache(cache: dict) -> None:
    os.makedirs(os.path.dirname(USAGE_CACHE), exist_ok=True)
    tmp = f"{USAGE_CACHE}.{os.getpid()}.tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(cache, f)
        os.replace(tmp, USAGE_CACHE)
    except OSError:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def refresh_usage() -> None:
    """Runs detached (--refresh-usage): fetch the usage rows once and rewrite the cache. The next
    attempt is pushed back before the request goes out, so a crash, a hang or a kill cannot turn
    into a request per render; the last good rows survive an error."""
    import threading
    import urllib.error
    import urllib.request

    timer = threading.Timer(REFRESH_DEADLINE, os._exit, (1,))
    timer.daemon = True
    timer.start()
    lock = USAGE_CACHE + ".lock"
    try:
        cache, now = load_usage_cache(), time.time()
        if now < (cache.get("next_try") or 0):
            return  # another refresh got here first
        cache.update(next_try=now + ERROR_BACKOFF, error="interrupted")
        save_usage_cache(cache)
        token = read_oauth_token()
        if not token:
            # logged out, or another account: its rows must not stay next to this one's
            cache.update(next_try=now + BACKOFF[401], error="no valid token", rows=[])
            return

        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, *args, **kwargs):
                return None  # the token goes to api.anthropic.com and nowhere else

        req = urllib.request.Request(USAGE_URL, headers={
            "Authorization": f"Bearer {token}", "anthropic-beta": "oauth-2025-04-20",
            "Content-Type": "application/json", "User-Agent": "kensei-statusline"})
        try:
            with urllib.request.build_opener(NoRedirect).open(req, timeout=8) as resp:
                body = json.load(resp)
        except urllib.error.HTTPError as e:
            cache.update(next_try=now + BACKOFF.get(e.code, ERROR_BACKOFF), error=f"HTTP {e.code}")
            return
        except Exception as e:  # noqa: BLE001 — only the type name is kept, never the text
            cache.update(next_try=now + ERROR_BACKOFF, error=type(e).__name__)
            return
        rows = body.get("limits") if isinstance(body, dict) else None
        cache = {"fetched_at": now, "next_try": now + USAGE_TTL,
                 "rows": [r for r in rows if isinstance(r, dict)] if isinstance(rows, list) else []}
    except Exception as e:  # noqa: BLE001
        cache = locals().get("cache") or {}
        cache.update(next_try=time.time() + ERROR_BACKOFF, error=type(e).__name__)
    finally:
        try:
            save_usage_cache(cache)
        except (OSError, NameError):
            pass
        finally:
            timer.cancel()  # in-process callers (the tests) outlive the deadline
            try:
                os.unlink(lock)
            except OSError:
                pass


def maybe_refresh_usage(cache: dict) -> None:
    """Start a detached refresh when the cache is due and none is running."""
    now = time.time()
    if os.environ.get("KENSEI_STATUSLINE_NO_USAGE_FETCH") or now < (cache.get("next_try") or 0):
        return
    lock = USAGE_CACHE + ".lock"
    try:
        os.makedirs(os.path.dirname(USAGE_CACHE), exist_ok=True)
        try:
            fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            if now - os.path.getmtime(lock) < REFRESH_LOCK_TTL:
                return
            os.unlink(lock)
            fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.close(fd)
        detach = ({"creationflags": 0x00000008 | 0x00000200} if sys.platform == "win32"
                  else {"start_new_session": True})
        subprocess.Popen([sys.executable, os.path.abspath(__file__), "--refresh-usage"],
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, **detach)
    except OSError:
        pass


if __name__ == "__main__":
    if sys.argv[1:] == ["--refresh-usage"]:
        refresh_usage()
