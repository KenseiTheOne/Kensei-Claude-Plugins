---
name: setup
description: Configure the kensei-statusline in your Claude Code settings
trigger: Use when the user wants to set up, reconfigure, or reinstall the statusline plugin
---

# Statusline Setup

Configure the kensei-statusline plugin as the active Claude Code statusline.

## Step 1 — Confirm with user

Ask the user if they want to install kensei-statusline as their Claude Code statusline. Briefly explain what it shows:
- Model name, context usage bar with color coding
- Token counts (input/output) with cache breakdown
- Estimated API cost (exact when reported by Claude Code, estimated otherwise)
- Active subagent count and types
- Git branch, staged/modified/untracked counts, ahead/behind
- Project file count and lines of code

If the user **declines**: create a marker file at `~/.claude/.statusline-no-setup` (so they won't be asked again on session start) and stop.

## Step 2 — Create wrapper script

Create the directory `~/.claude/scripts/` if it doesn't exist.

Write this wrapper to `~/.claude/scripts/kensei-statusline.py`:

```python
#!/usr/bin/env python3
"""Kensei Statusline wrapper — resolves plugin cache version dynamically."""
from __future__ import annotations

import os
import sys
import runpy

CACHE = os.path.join(
    os.path.expanduser("~"), ".claude", "plugins", "cache",
    "kensei-claude-plugins", "kensei-statusline",
)

if os.path.isdir(CACHE):
    versions = sorted(os.listdir(CACHE))
    if versions:
        script = os.path.join(CACHE, versions[-1], "scripts", "statusline.py")
        if os.path.isfile(script):
            runpy.run_path(script, run_name="__main__")
            sys.exit(0)

print("...")
```

## Step 3 — Update settings.json

Read `~/.claude/settings.json`. Determine the absolute path to the wrapper using the user's home directory (e.g., `C:/Users/Username/.claude/scripts/kensei-statusline.py` on Windows, `/home/username/.claude/scripts/kensei-statusline.py` on Linux/macOS).

Add or replace the `statusLine` key:

```json
"statusLine": {
  "type": "command",
  "command": "python \"<absolute-path-to-wrapper>\""
}
```

Use the Edit tool to modify the file. If `statusLine` already exists, replace it.

Also remove the dismiss marker `~/.claude/.statusline-no-setup` if it exists (user is explicitly re-running setup).

## Step 4 — Confirm

Tell the user the statusline is configured. They need to restart Claude Code (`/exit` and start a new session) for it to take effect.
