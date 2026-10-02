---
description: svg-diagram and codex-img both answer «сделай картинкой»; a diagram from a README must go to svg-diagram, not to the raster image skill that spends Codex image quota.
expected_outcome: Claude invokes kensei-toolkit:svg-diagram for the README's ASCII diagram and never invokes kensei-toolkit:codex-img.
tags: [smoke, svg-diagram]
max_turns: 8
timeout_seconds: 240
allowed_tools: [Read, Glob, Grep, Skill]
---

Сделай картинкой схему из README.
