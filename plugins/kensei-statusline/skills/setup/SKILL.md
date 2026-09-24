---
name: setup
description: Configure the kensei-statusline in your Claude Code settings
trigger: Use when the user wants to set up, reconfigure, or reinstall the statusline plugin
---

# Statusline Setup

Configure the kensei-statusline plugin as the active Claude Code statusline.

## Step 1 — Create wrapper script

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

def version_key(name: str) -> tuple:
    # 1.10.0 must beat 1.4.0 — a plain string sort would not
    return tuple(int(p) if p.isdigit() else -1 for p in name.split("."))


if os.path.isdir(CACHE):
    versions = sorted(os.listdir(CACHE), key=version_key)
    if versions:
        script = os.path.join(CACHE, versions[-1], "scripts", "statusline.py")
        if os.path.isfile(script):
            runpy.run_path(script, run_name="__main__")
            sys.exit(0)

print("...")
```

## Step 2 — Update settings.json

Read `~/.claude/settings.json`. Determine the absolute path to the wrapper using the user's home directory (e.g., `C:/Users/Username/.claude/scripts/kensei-statusline.py` on Windows, `/home/username/.claude/scripts/kensei-statusline.py` on Linux/macOS).

Add or replace the `statusLine` key:

```json
"statusLine": {
  "type": "command",
  "command": "python3 \"<absolute-path-to-wrapper>\""
}
```

Use the Edit tool to modify the file. If `statusLine` already exists, replace it.

Also remove the dismiss marker `~/.claude/.statusline-no-setup` if it exists (user is explicitly re-running setup).

If `~/.claude/scripts/kensei-statusline.py` already exists from an earlier install, overwrite it:
older wrappers picked the plugin version by string order and would run 1.4.0 instead of 1.10.0.

## Step 3 — Confirm

Tell the user the statusline is configured. They need to restart Claude Code (`/exit` and start a new session) for it to take effect.
