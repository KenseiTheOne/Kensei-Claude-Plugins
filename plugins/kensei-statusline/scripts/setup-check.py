#!/usr/bin/env python3
"""SessionStart hook: prompt statusline setup if not configured yet."""
from __future__ import annotations

import json
import os
import sys

home = os.path.expanduser("~")
settings_path = os.path.join(home, ".claude", "settings.json")
dismiss_path = os.path.join(home, ".claude", ".statusline-no-setup")

# User explicitly dismissed setup
if os.path.exists(dismiss_path):
    sys.exit(0)

# Check if statusLine is already configured
try:
    with open(settings_path, "r", encoding="utf-8") as f:
        settings = json.load(f)
    if "statusLine" in settings:
        sys.exit(0)
except (OSError, json.JSONDecodeError, ValueError):
    pass

# Not configured — tell Claude to offer setup
print(
    "[statusline-plugin] The kensei-statusline plugin is enabled but statusLine "
    "is not configured in settings.json. Ask the user if they'd like to set up "
    "the custom statusline (shows model, context, tokens, cost, git info). "
    "If yes, run /kensei-statusline:setup. If the user declines, create the file "
    f'"{dismiss_path}" so they are not asked again.'
)
