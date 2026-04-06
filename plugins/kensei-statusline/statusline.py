#!/usr/bin/env python3
"""Kensei Statusline — model, context, tokens, estimated API cost, git info."""
import sys
import os
import json
import subprocess

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


def calc_cost(data: dict) -> float:
    """Calculate estimated API cost from token counts."""
    reported = (data.get("cost") or {}).get("total_cost_usd")
    if reported and reported > 0:
        return reported

    ctx = data.get("context_window") or {}
    model_id = (data.get("model") or {}).get("id", "")
    p = get_pricing(model_id)

    in_tok = int(ctx.get("total_input_tokens") or 0)
    out_tok = int(ctx.get("total_output_tokens") or 0)

    # Use cache breakdown if available
    cur = ctx.get("current_usage") or {}
    cache_write = int(cur.get("cache_creation_input_tokens") or 0)
    cache_read = int(cur.get("cache_read_input_tokens") or 0)

    if cache_write or cache_read:
        regular_in = max(0, in_tok - cache_write - cache_read)
        cost = (
            regular_in * p["input"]
            + cache_write * p["cache_write"]
            + cache_read * p["cache_read"]
            + out_tok * p["output"]
        ) / 1_000_000
    else:
        cost = (in_tok * p["input"] + out_tok * p["output"]) / 1_000_000

    return cost


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
            changes.append(f"\033[32m●{staged}{rst}")
        if modified:
            changes.append(f"\033[33m+{modified}{rst}")
        if untracked:
            changes.append(f"\033[2m?{untracked}{rst}")

        if changes:
            parts.append(" ".join(changes))
        else:
            parts.append(f"\033[32m✓{rst}")

        sync = []
        if ahead:
            sync.append(f"\033[36m⇡{ahead}{rst}")
        if behind:
            sync.append(f"\033[35m⇣{behind}{rst}")
        if sync:
            parts.append("".join(sync))

        return f" {dim}│{rst} ".join(parts)

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
    in_tok = int(ctx.get("total_input_tokens") or 0)
    out_tok = int(ctx.get("total_output_tokens") or 0)
    cost = calc_cost(data)

    bar = colorize_bar(make_bar(pct), pct)
    cost_str = f"${cost:.2f}" if cost < 10 else f"${cost:.1f}"

    dim = "\033[2m"
    reset = "\033[0m"

    # Line 1: model, context, tokens, cost
    print(
        f"{model} {dim}│{reset} {bar} {pct}% "
        f"{dim}│{reset} \033[36m↑{reset}{fmt_tokens(in_tok)} \033[35m↓{reset}{fmt_tokens(out_tok)} "
        f"{dim}│{reset} ~{cost_str}"
    )

    # Line 2: git info
    cwd = data.get("cwd") or data.get("workspace", {}).get("current_dir", "")
    if cwd:
        git_line = get_git_info(cwd)
        if git_line:
            print(git_line)


if __name__ == "__main__":
    main()
