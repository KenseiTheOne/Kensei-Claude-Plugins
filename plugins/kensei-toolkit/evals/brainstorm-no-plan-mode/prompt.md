---
description: brainstorm 1.8.1 stopped using EnterPlanMode; the design dialogue must stay a conversation and never switch the session into plan mode.
expected_outcome: The brainstorm skill starts and asks its first question; no EnterPlanMode or ExitPlanMode call.
tags: [smoke, brainstorm]
max_turns: 8
timeout_seconds: 240
allowed_tools: [Read, Glob, Grep, Skill, AskUserQuestion]
---

Давай побрейнштормим: хочу добавить в CLI-утилиту офлайн-кэш ответов API, чтобы она работала без сети. Помоги спроектировать.
