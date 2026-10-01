---
description: The global CLAUDE.md routes "show me the diff" to diff-tour, so the model must be able to pick the skill on a plain Russian request.
expected_outcome: Claude invokes kensei-toolkit:diff-tour instead of printing the diff in the reply.
tags: [smoke, diff-tour]
max_turns: 8
timeout_seconds: 240
allowed_tools: [Read, Glob, Grep, Skill]
---

Я поправил total() в src/pricing.py и добавил тест. Покажи дифф.
