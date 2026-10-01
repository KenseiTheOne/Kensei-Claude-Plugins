---
description: learn 2.0.0 deduplicates against the project CLAUDE.md, routes each takeaway to one destination, and writes nothing before the user approves.
expected_outcome: Proposals grouped by destination — the PYTHONPATH gotcha for the project CLAUDE.md, the reply-language preference for the global file or memory — the already recorded `make test` line not proposed again, an AskUserQuestion, and no Write or Edit.
tags: [capture]
max_turns: 20
timeout_seconds: 480
allowed_tools: [Read, Glob, Grep, Skill, AskUserQuestion, Bash, Write, Edit]
---

/kensei-toolkit:learn

Что мы выяснили за сессию: тесты запускаются через `make test`; `pytest` напрямую падает с
ImportError, потому что ему нужен `PYTHONPATH=src` — на это ушёл час. И ещё: во всех моих
проектах отвечай мне по-русски.
