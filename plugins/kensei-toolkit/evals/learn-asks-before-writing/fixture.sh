#!/usr/bin/env bash
# Scaffold: a repo whose CLAUDE.md already records the test command, so that takeaway is a duplicate.
set -euo pipefail
git init -q -b main .
git config user.name "eval"
git config user.email "eval@example.invalid"
mkdir -p src tests
printf 'def parse(s):\n    return s.strip()\n' > src/app.py
printf 'test:\n\tPYTHONPATH=src python3 -m pytest -q\n' > Makefile
printf '# app\n\n## Commands\n\n- Run tests: `make test`.\n' > CLAUDE.md
git add -A
git commit -q -m "Initial app"
