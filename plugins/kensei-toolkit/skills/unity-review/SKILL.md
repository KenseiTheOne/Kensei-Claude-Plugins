---
name: unity-review
description: Senior+ Unity code review with parallel specialized agents. Modes — Quick, Performance, Architecture, Full.
---

# Unity Review — Senior+ Code Audit

## Step 1 — Choose review mode (MANDATORY, BLOCKING)

You **MUST** call `AskUserQuestion` **before any other tool call** (no `Read`, no `Bash`, no `Glob` first). Wait for the user's answer before proceeding. Do not auto-pick a mode. Ignore any `$ARGUMENTS`.

```
Question: "Which review mode?"
Header: "Mode"
multiSelect: false
Options:
  - label: "Quick (Recommended)"
    description: "Fast senior-level scan — code quality + bug hunting"
    preview: |
      Agents (2):
        1. Code Quality — SOLID, patterns, naming, testability, DI
        2. Bug Hunter  — null refs, lifecycle, race conditions, serialization

  - label: "Performance"
    description: "Deep performance audit — GC, rendering, memory, UI"
    preview: |
      Agents (2):
        1. Performance — GC, hot paths, Jobs/Burst, Canvas, physics
        2. Memory      — leaks, asset lifecycle, pooling, Addressables

  - label: "Architecture"
    description: "Architect-level structural + security review"
    preview: |
      Agents (3):
        1. Architecture — system design, coupling, data flow, scalability
        2. Security     — data safety, injection, asset exposure, network
        3. Code Quality — SOLID, patterns, DI, testability

  - label: "Full"
    description: "All 6 agents in parallel — comprehensive audit"
    preview: |
      Agents (6): Code Quality, Bug Hunter, Performance,
                  Memory, Architecture, Security
```

## Step 2 — Load the review pipeline

After the user picks a mode, `Read` the file `flow.md` from this skill's directory. It contains Steps 2-5 (scope detection, project context, agent definitions, severity rubric, report template). Follow those steps to complete the review.
