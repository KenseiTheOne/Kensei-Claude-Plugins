---
description: unity-review 2.0.0 takes the mode from its arguments (no blocking question), stays read-only, and reports findings with a location and a failure scenario.
expected_outcome: No AskUserQuestion, no Edit or Write; the report names the per-frame allocation in EnemySpawner.Update with a path:line and a failure scenario.
tags: [unity-review]
max_turns: 30
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep, Skill, Agent, AskUserQuestion, Bash, Write, Edit]
---

/kensei-toolkit:unity-review perf
