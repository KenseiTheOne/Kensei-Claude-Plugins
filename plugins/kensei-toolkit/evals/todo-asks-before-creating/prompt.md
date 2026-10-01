---
description: todo 2.0.0 drafts loose ends with evidence, asks before creating anything, and does not fall back to writing a TODO.md.
expected_outcome: Drafts with an evidence line each, grouped by destination; an AskUserQuestion; no task created and no file written.
tags: [capture]
max_turns: 16
timeout_seconds: 420
allowed_tools: [Read, Glob, Grep, Skill, AskUserQuestion, Bash, Write, Edit]
---

/kensei-toolkit:todo

Итог сессии: починили парсер дат в CLI. Пустую строку в parse_date пока не обрабатываем —
сделаем потом. Ещё надо будет добавить тест на часовые пояса. И напомни мне продлить домен
до 15 ноября.
