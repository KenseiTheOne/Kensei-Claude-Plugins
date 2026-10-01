---
description: Interactive ticket run up to the single confirmation (Step 5). Covers the context agent writing 01-context.md and the publish rules (no commit, no push, nothing from the run dir in the repo).
expected_outcome: Context agent dispatched as general-purpose with 01-context.md as its output; acceptance criteria drafted and put to the user; no edits to src/, no commit, no push, no .task-runs in the repo.
tags: [ticket]
max_turns: 40
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep, Skill, Agent, AskUserQuestion, TodoWrite, Bash, Write, Edit]
---

/kensei-toolkit:ticket LOCAL-17 fix

Трекера нет — вот текст задачи целиком:

LOCAL-17 · total() принимает скидку больше 100%

`total([10, 20], discount=1.5)` возвращает -15. Скидка вне диапазона 0..1 должна
отклоняться с ValueError, а сумма — округляться до копеек. Существующий тест
`tests/test_pricing.py` должен остаться зелёным.
