#!/usr/bin/env python3
"""SessionStart hook: offer statusline setup if no statusline is configured yet."""
from __future__ import annotations

import json
import os
import sys

config_dir = os.environ.get("CLAUDE_CONFIG_DIR") or os.path.join(os.path.expanduser("~"), ".claude")
dismiss_path = os.path.join(config_dir, ".statusline-no-setup")

# User explicitly dismissed setup
if os.path.exists(dismiss_path):
    sys.exit(0)

# A statusline set in either user settings file counts as configured
for name in ("settings.json", "settings.local.json"):
    try:
        with open(os.path.join(config_dir, name), "r", encoding="utf-8") as f:
            settings = json.load(f)
        if isinstance(settings, dict) and "statusLine" in settings:
            sys.exit(0)
    except (OSError, json.JSONDecodeError, ValueError):
        pass

# Not configured — tell Claude to offer setup
print(
    "[statusline-plugin] The kensei-statusline plugin is enabled but no statusLine is configured "
    "in the user settings. Ask the user, in their language, whether to set up the custom "
    "statusline (model, context, tokens, cost, usage limits, git info). Mention that it reads "
    "Claude Code's OAuth token to fetch subscription usage meters from api.anthropic.com. "
    "If yes, run /kensei-statusline:setup. If the user declines, create the empty file "
    f'"{dismiss_path}" so they are not asked again.'
)
