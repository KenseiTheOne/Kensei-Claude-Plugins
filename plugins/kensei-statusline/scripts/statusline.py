#!/usr/bin/env python3
"""Kensei Statusline — model, context, tokens, estimated API cost, git info."""
from __future__ import annotations

import sys
import os
import json
import re
import time
import subprocess
import glob as glob_mod

# Force UTF-8 output on Windows
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")

# Anthropic API pricing (USD per 1M tokens), May 2025
PRICING = {
    "opus":   {"input": 15.0, "output": 75.0, "cache_write": 18.75, "cache_read": 1.875},
    "sonnet": {"input": 3.0,  "output": 15.0, "cache_write": 3.75,  "cache_read": 0.375},
    "haiku":  {"input": 1.0,  "output": 5.0,  "cache_write": 1.25,  "cache_read": 0.10},
}

ACTIVE_AGENT_THRESHOLD_S = 30  # seconds since last write = "active"


def get_pricing(model_id: str) -> dict:
    mid = model_id.lower()
    for key in PRICING:
        if key in mid:
            return PRICING[key]
    return PRICING["sonnet"]


def fmt_tokens(n: int) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)


def make_bar(pct: int, width: int = 10) -> str:
    filled = max(0, min(width, pct * width // 100))
    return "\u2593" * filled + "\u2591" * (width - filled)


def colorize_bar(bar: str, pct: int) -> str:
    if pct >= 80:
        return f"\033[31m{bar}\033[0m"   # red
    if pct >= 50:
        return f"\033[33m{bar}\033[0m"   # yellow
    return f"\033[32m{bar}\033[0m"        # green


def parse_transcript(filepath: str) -> dict[str, dict]:
    """Parse a JSONL transcript, sum token usage per model.
    Returns { model_id: { input, output, cache_write, cache_read } }."""
    models: dict[str, dict] = {}
    try:
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                if '"assistant"' not in line:
                    continue
                try:
                    entry = json.loads(line)
                except (json.JSONDecodeError, ValueError):
                    continue
                if entry.get("type") != "assistant":
                    continue
                msg = entry.get("message") or {}
                usage = msg.get("usage")
                if not usage:
                    continue
                model = msg.get("model") or "unknown"
                if model not in models:
                    models[model] = {"input": 0, "output": 0, "cache_write": 0, "cache_read": 0}
                m = models[model]
                m["input"] += usage.get("input_tokens") or 0
                m["output"] += usage.get("output_tokens") or 0
                m["cache_write"] += usage.get("cache_creation_input_tokens") or 0
                m["cache_read"] += usage.get("cache_read_input_tokens") or 0
    except OSError:
        pass
    return models


def get_subagents(transcript_path: str) -> tuple[list[str], dict[str, dict]]:
    """Discover subagent transcripts, detect active agents, sum tokens.
    Returns (active_agent_types, models_dict)."""
    # Derive subagents dir: /path/to/session_id.jsonl -> /path/to/session_id/subagents/
    base = transcript_path.rsplit(".", 1)[0]  # strip .jsonl
    subagent_dir = os.path.join(base, "subagents")

    if not os.path.isdir(subagent_dir):
        return [], {}

    now = time.time()

    active_types: list[str] = []
    all_models: dict[str, dict] = {}

    for jsonl_path in glob_mod.glob(os.path.join(subagent_dir, "agent-*.jsonl")):
        fname = os.path.basename(jsonl_path)
        # Skip compaction files
        if "acompact" in fname:
            continue

        # Check if active (recently modified)
        try:
            mtime = os.path.getmtime(jsonl_path)
            is_active = (now - mtime) < ACTIVE_AGENT_THRESHOLD_S
        except OSError:
            is_active = False

        if is_active:
            # Read agent type from .meta.json
            meta_path = jsonl_path.replace(".jsonl", ".meta.json")
            agent_type = "?"
            try:
                with open(meta_path, "r", encoding="utf-8") as f:
                    meta = json.load(f)
                agent_type = meta.get("agentType") or "?"
            except (OSError, json.JSONDecodeError, ValueError):
                pass
            active_types.append(agent_type)

        # Parse tokens from transcript
        agent_models = parse_transcript(jsonl_path)
        for model_id, tokens in agent_models.items():
            if model_id not in all_models:
                all_models[model_id] = {"input": 0, "output": 0, "cache_write": 0, "cache_read": 0}
            m = all_models[model_id]
            for k in ("input", "output", "cache_write", "cache_read"):
                m[k] += tokens[k]

    return active_types, all_models


def calc_cost_from_models(models: dict[str, dict]) -> float:
    """Calculate cost from per-model token dicts with cache breakdowns."""
    cost = 0.0
    for model_id, tokens in models.items():
        p = get_pricing(model_id)
        cost += (
            tokens["input"] * p["input"]
            + tokens["cache_write"] * p["cache_write"]
            + tokens["cache_read"] * p["cache_read"]
            + tokens["output"] * p["output"]
        ) / 1_000_000
    return cost


def merge_models(a: dict[str, dict], b: dict[str, dict]) -> dict[str, dict]:
    """Merge two model token dicts."""
    result = {}
    for model_id in set(list(a.keys()) + list(b.keys())):
        result[model_id] = {}
        for k in ("input", "output", "cache_write", "cache_read"):
            result[model_id][k] = a.get(model_id, {}).get(k, 0) + b.get(model_id, {}).get(k, 0)
    return result


def fmt_lines_changed(data: dict) -> str | None:
    """Format lines added/removed in session."""
    cost_data = data.get("cost") or {}
    added = int(cost_data.get("total_lines_added") or 0)
    removed = int(cost_data.get("total_lines_removed") or 0)
    if not added and not removed:
        return None
    return f"\033[32m+{added}\033[0m \033[31m-{removed}\033[0m"


def get_project_stats(cwd: str) -> str | None:
    """Get project file count and lines of code."""
    try:
        empty = subprocess.run(
            ["git", "hash-object", "-t", "tree", "--stdin"],
            capture_output=True, text=True, timeout=2, cwd=cwd, input="",
        )
        if empty.returncode != 0:
            return None
        empty_tree = empty.stdout.strip()

        stat = subprocess.run(
            ["git", "diff", "--shortstat", empty_tree, "HEAD"],
            capture_output=True, text=True, timeout=3, cwd=cwd,
        )
        if stat.returncode != 0 or not stat.stdout.strip():
            return None

        line = stat.stdout.strip()
        files_m = re.search(r"(\d+) file", line)
        ins_m = re.search(r"(\d+) insertion", line)
        files = int(files_m.group(1)) if files_m else 0
        loc = int(ins_m.group(1)) if ins_m else 0

        if loc:
            return f"{files} files {fmt_tokens(loc)} loc"
        return f"{files} files" if files else None
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return None


def get_git_info(cwd: str) -> str | None:
    """Get git branch, file changes, and ahead/behind from cwd."""
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain=v2", "--branch"],
            capture_output=True, text=True, timeout=2, cwd=cwd,
        )
        if result.returncode != 0:
            return None

        branch = ""
        ahead = behind = 0
        staged = modified = untracked = 0

        for line in result.stdout.splitlines():
            if line.startswith("# branch.head "):
                branch = line.split(" ", 2)[2]
            elif line.startswith("# branch.ab "):
                parts = line.split()
                ahead = int(parts[2].lstrip("+"))
                behind = abs(int(parts[3]))
            elif line.startswith("1 ") or line.startswith("2 "):
                xy = line.split(" ")[1]
                if xy[0] != ".":
                    staged += 1
                if xy[1] != ".":
                    modified += 1
            elif line.startswith("? "):
                untracked += 1

        if not branch:
            return None

        dim = "\033[2m"
        rst = "\033[0m"
        parts = [f"\033[1m\033[34m{branch}{rst}"]

        changes = []
        if staged:
            changes.append(f"\033[32m\u25cf{staged}{rst}")
        if modified:
            changes.append(f"\033[33m+{modified}{rst}")
        if untracked:
            changes.append(f"\033[2m?{untracked}{rst}")

        if changes:
            parts.append(" ".join(changes))
        else:
            parts.append(f"\033[32m\u2713{rst}")

        sync = []
        if ahead:
            sync.append(f"\033[36m\u21e1{ahead}{rst}")
        if behind:
            sync.append(f"\033[35m\u21e3{behind}{rst}")
        if sync:
            parts.append("".join(sync))

        return f" {dim}\u2502{rst} ".join(parts)

    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return None


def main():
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError, ValueError):
        print("...")
        return

    model = (data.get("model") or {}).get("display_name", "?")
    ctx = data.get("context_window") or {}
    pct = int(ctx.get("used_percentage") or 0)

    # Parse main transcript for accurate cumulative tokens
    transcript_path = data.get("transcript_path") or ""
    main_models = parse_transcript(transcript_path) if transcript_path else {}

    # Parse subagent transcripts
    active_types, sub_models = (
        get_subagents(transcript_path) if transcript_path else ([], {})
    )

    # Merge all models for total tokens and cost
    all_models = merge_models(main_models, sub_models)

    # Sum tokens for display
    total_in = sum(
        m["input"] + m["cache_write"] + m["cache_read"]
        for m in all_models.values()
    )
    total_out = sum(m["output"] for m in all_models.values())

    # Cost: prefer Claude Code's reported cost, fall back to our calculation
    reported_cost = (data.get("cost") or {}).get("total_cost_usd")
    has_reported_cost = reported_cost and reported_cost > 0
    if has_reported_cost:
        cost = reported_cost
    else:
        cost = calc_cost_from_models(all_models)

    cost_prefix = "" if has_reported_cost else "~"
    cost_str = f"{cost_prefix}${cost:.2f}" if cost < 10 else f"{cost_prefix}${cost:.1f}"

    bar = colorize_bar(make_bar(pct), pct)
    dim = "\033[2m"
    rst = "\033[0m"

    # Active agents display
    agents_part = ""
    if active_types:
        count = len(active_types)
        types: dict[str, int] = {}
        for t in active_types:
            types[t] = types.get(t, 0) + 1
        agents_part = f" {dim}\u2502{rst} \033[95m{count} agent{'s' if count != 1 else ''}{rst}"
        type_parts = []
        for t, c in sorted(types.items(), key=lambda x: -x[1]):
            type_parts.append(f"{t}x{c}" if c > 1 else t)
        if type_parts:
            agents_part += f" \033[2m({', '.join(type_parts)}){rst}"

    # Line 1: model, context, tokens, cost, agents
    print(
        f"{model} {dim}\u2502{rst} {bar} {pct}% "
        f"{dim}\u2502{rst} \033[36m\u2191{rst}{fmt_tokens(total_in)} \033[35m\u2193{rst}{fmt_tokens(total_out)} "
        f"{dim}\u2502{rst} {cost_str}"
        f"{agents_part}"
    )

    # Line 2: git info + lines changed + project stats
    cwd = data.get("cwd") or data.get("workspace", {}).get("current_dir", "")
    if cwd:
        git_line = get_git_info(cwd)
        if git_line:
            lines = fmt_lines_changed(data)
            if lines:
                git_line += f" {dim}\u2502{rst} {lines}"
            proj_stats = get_project_stats(cwd)
            if proj_stats:
                git_line += f" {dim}\u2502{rst} \033[2m{proj_stats}{rst}"
            print(git_line)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print("...")
