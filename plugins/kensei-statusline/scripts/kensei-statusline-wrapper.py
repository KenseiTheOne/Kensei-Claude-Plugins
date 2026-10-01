#!/usr/bin/env python3
"""Kensei Statusline wrapper: runs statusline.py from the installed copy of the plugin.

The setup skill copies this file to <config dir>/scripts/kensei-statusline.py, a path that does
not change between plugin versions, and points settings.json at it. On every render it asks
Claude Code which copy is installed (plugins/installed_plugins.json) instead of guessing from the
cache directory: the cache also holds older and orphaned versions (marked with .orphaned_at),
and the highest version number there is not always the installed one.
"""
from __future__ import annotations

import json
import os
import runpy
import sys

PLUGIN_KEY = "kensei-statusline@kensei-claude-plugins"
CONFIG_DIR = os.environ.get("CLAUDE_CONFIG_DIR") or os.path.join(os.path.expanduser("~"), ".claude")
SCRIPT = os.path.join("scripts", "statusline.py")


def usable(install_path: object) -> str | None:
    """The statusline script inside an install dir, unless the dir is gone or orphaned."""
    if not isinstance(install_path, str) or not install_path:
        return None
    if os.path.exists(os.path.join(install_path, ".orphaned_at")):
        return None
    script = os.path.join(install_path, SCRIPT)
    return script if os.path.isfile(script) else None


def within(path: str, root: str) -> bool:
    try:
        return os.path.commonpath([os.path.realpath(path), os.path.realpath(root)]) == os.path.realpath(root)
    except ValueError:
        return False


def from_installed_plugins(cwd: str) -> str | None:
    """The installed copy: a project or local install for the current project wins over a user
    install, as in Claude Code itself."""
    try:
        with open(os.path.join(CONFIG_DIR, "plugins", "installed_plugins.json"), encoding="utf-8") as f:
            entries = json.load(f).get("plugins", {}).get(PLUGIN_KEY) or []
    except (OSError, ValueError, AttributeError):
        return None
    if not isinstance(entries, list):
        return None
    entries = [e for e in entries if isinstance(e, dict)]
    project = [e for e in entries if e.get("scope") in ("project", "local")
               and isinstance(e.get("projectPath"), str) and within(cwd, e["projectPath"])]
    project.sort(key=lambda e: len(e["projectPath"]), reverse=True)  # the nearest project first
    user = [e for e in entries if e.get("scope") not in ("project", "local")]
    for entry in project + user:
        script = usable(entry.get("installPath"))
        if script:
            return script
    return None


def version_key(name: str) -> tuple:
    # 1.10.0 must beat 1.4.0 — a plain string sort would not
    return tuple(int(p) if p.isdigit() else -1 for p in name.split("."))


def from_cache() -> str | None:
    """Fallback when installed_plugins.json is missing or unreadable: the highest cached version
    that is not orphaned."""
    cache = os.path.join(CONFIG_DIR, "plugins", "cache", "kensei-claude-plugins", "kensei-statusline")
    try:
        versions = sorted(os.listdir(cache), key=version_key, reverse=True)
    except OSError:
        return None
    for version in versions:
        script = usable(os.path.join(cache, version))
        if script:
            return script
    return None


def main() -> None:
    script = from_installed_plugins(os.getcwd()) or from_cache()
    if not script:
        print("kensei-statusline: plugin not installed")
        return
    sys.argv[0] = script
    runpy.run_path(script, run_name="__main__")


if __name__ == "__main__":
    main()
