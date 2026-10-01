---
description: Resumes a /ticket run stopped at the publish gate (fixture.sh builds the repo and the run dir, history.jsonl the conversation) and gives the commit command. Covers the commit path (12.3) — run notes stay out of the commit — which no other case reaches.
expected_outcome: Exactly one commit, on task/LOCAL-17-discount-range, holding src/pricing.py and tests/test_pricing.py only; nothing from the run dir staged or committed; no push, no merge, no amend.
tags: [ticket, gate]
max_turns: 30
timeout_seconds: 600
allowed_tools: [Read, Glob, Grep, Skill, AskUserQuestion, TodoWrite, Bash, Write, Edit]
---

закоммить
