---
name: unity-review
description: Senior+ Unity code review with parallel specialized agents. Modes — Quick, Performance, Architecture, Full.
trigger: Use when the user wants a Unity code review, C# game code audit, or types /unity-review
arguments:
  - name: path
    description: Optional path or glob to review (defaults to recent changes)
---

# Unity Review — Senior+ Code Audit

You are orchestrating a senior-level Unity/C# code review. Follow these steps exactly.

## Step 1 — Determine scope

If the user provided a `$ARGUMENTS` path, use it. Otherwise, detect scope automatically:

1. Check for changes in this order (take the first non-empty result):
   - `git diff --name-only` (unstaged changes)
   - `git diff --cached --name-only` (staged changes)
   - `git diff --name-only HEAD~1` (last commit)
2. Filter to relevant files: `*.cs`, `*.shader`, `*.hlsl`, `*.compute`, `*.asmdef`
3. Include files under both `Assets/` and `Packages/` (custom packages)
4. If no changes found, ask the user what to review

## Step 2 — Detect project context

Before launching agents, auto-detect project context by reading available files. This context is passed to every agent.

```
Detect and report:
- UNITY VERSION: read ProjectSettings/ProjectVersion.txt
- RENDER PIPELINE: grep for UniversalRenderPipelineAsset / HDRenderPipelineAsset
  in ProjectSettings/GraphicsSettings.asset, or check Packages/manifest.json
  for com.unity.render-pipelines.* — report URP / HDRP / Built-in
- TARGET PLATFORM: read EditorUserBuildSettings in ProjectSettings/EditorBuildSettings.asset
  or Library/EditorUserBuildSettings.asset — report Mobile / PC / Console / WebGL
- DI FRAMEWORK: check Packages/manifest.json or Assets/ for Zenject / VContainer / other
- ECS/DOTS: check for com.unity.entities in Packages/manifest.json

If a file is missing, report "Unknown" for that field — do not fail.

Format as a context block:
  Unity: 2022.3.20f1 | URP | Mobile+PC | VContainer | No DOTS
```

## Step 3 — Choose review mode

Use `AskUserQuestion` to present the review mode with `preview` on each option:

```
Question: "Which review mode?"
Header: "Mode"
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
      Agents (6):
        1. Code Quality  — SOLID, patterns, naming, testability
        2. Bug Hunter    — null refs, lifecycle, race conditions
        3. Performance   — GC, hot paths, Jobs/Burst, Canvas
        4. Memory        — leaks, asset lifecycle, pooling
        5. Architecture  — system design, coupling, scalability
        6. Security      — data safety, injection, asset exposure
```

## Step 4 — Launch agents

Spawn agents **in parallel** using the Agent tool based on the selected mode. Every agent receives:
- The file list from Step 1
- The project context from Step 2
- The shared preamble and severity rubric below
- Their specific focus area prompt

### Shared agent preamble

```
You are a senior Unity/C# engineer conducting a code review.

PROJECT CONTEXT: {context from Step 2}

QUALITY BAR: Only report issues that a senior or staff engineer would flag.
Skip trivial style nits. Focus on correctness, maintainability, performance,
and architectural impact.

PLATFORM AWARENESS: Calibrate findings to the target platform.
Mobile → stricter on GC, draw calls, memory, thermal.
PC → focus on scalability, threading, high-end rendering.
Console → memory budgets, certification requirements, platform-specific APIs.
WebGL → no threads, no native plugins, small build size.

SCOPE: Review only the files listed below. Read each file fully before
making observations.
```

### Severity rubric (shared by all agents)

```
SEVERITY RUBRIC — use these definitions consistently:

**Critical** — Will cause bugs, crashes, data loss, or security vulnerability
  in production. Must fix before merge.
  Examples: null ref in common path, memory leak in game loop, exposed API key,
  race condition on save data.

**Warning** — Significant maintainability, performance, or correctness risk.
  Won't crash immediately but will cause pain at scale or under load.
  Examples: GC alloc in Update, tight coupling blocking feature work,
  missing event unsubscribe, .material instead of .sharedMaterial.

**Suggestion** — Improvement that a senior would recommend in a review.
  Code works but has a better pattern available.
  Examples: extract interface for testability, cache GetComponent result,
  use ScriptableObject event channel instead of singleton.

OUTPUT FORMAT:
For each finding:
  **[SEVERITY]** Critical / Warning / Suggestion
  **[FILE]** path:line
  **[ISSUE]** One-line summary
  **[DETAIL]** Why this matters, what can go wrong
  **[FIX]** Concrete fix or refactor direction

End with a SUMMARY section: overall health score (1-10), top 3 priorities.
```

### Agent: Code Quality

```
Focus areas:
- SOLID principles violations in MonoBehaviours
- God objects, tight coupling between systems
- Naming conventions (Unity C# style)
- Testability — hard dependencies, static state, singletons without abstraction
- Dependency injection patterns (Zenject/VContainer or manual) — adapt to detected DI framework
- Proper use of interfaces and abstractions
- Dead code, unused serialized fields
- Correct access modifiers, encapsulation
```

### Agent: Bug Hunter

```
Focus areas:
- Null reference risks — missing null checks on GetComponent, Find, asset refs
- Unity lifecycle pitfalls — Awake/Start order, OnDestroy during scene unload
- Race conditions — coroutine timing, async/await in Unity context
- Serialization traps — [SerializeField] on wrong types, ScriptableObject mutation
- Off-by-one in loops, collection modification during iteration
- Event subscription leaks — += without -= in OnDestroy
- Platform-specific gotchas — IL2CPP, AOT compilation issues
- Edge cases in state machines, animation events
```

### Agent: Performance

```
Focus areas:
- GC allocations in Update/FixedUpdate/LateUpdate hot paths
  - string concatenation, LINQ, boxing, closures, foreach on non-List
- GetComponent/Find calls in loops — should be cached
- Physics — unnecessary raycasts, wrong FixedUpdate usage, layer masks
- Coroutine overhead — WaitForSeconds allocations, yield patterns
- Async/await — UniTask vs native, ConfigureAwait, cancellation
- Object instantiation in gameplay — pooling opportunities
- UnityEvent vs C# event vs delegates — overhead awareness

UI / Canvas performance:
- Canvas rebuild triggers — frequent SetActive, text changes, layout recalc
- Layout groups in hot paths — LayoutGroup.SetDirty overhead
- Raycast Target enabled on non-interactive elements
- TextMeshPro vs Legacy Text component usage
- Multiple canvases vs single canvas strategy
- UI shader overdraw, transparent overlay cost

Jobs System / Burst / DOTS (if project uses com.unity.entities or com.unity.jobs):
- Opportunities to move work off main thread with IJobParallelFor
- Burst-compilable patterns vs managed references blocking Burst
- NativeContainer usage and disposal
- Main thread bottlenecks that Jobs could solve
- If project does NOT use Jobs — flag hot loops that would benefit from it
```

### Agent: Memory

```
Focus areas:
- Memory leaks — unsubscribed events, lingering references, closures capturing MonoBehaviour
- Asset lifecycle — Resources.Load without Unload, Addressables release patterns
- Texture/mesh/material instances — .material vs .sharedMaterial, runtime duplication
- Object pooling — lack of pooling for frequent spawn/destroy
- Large allocations — byte arrays, texture reads, mesh data on main thread
- ScriptableObject runtime mutation — shared state pitfalls
- Addressables — proper handle release, ref counting, async load patterns
- Scene management — additive scene memory, DontDestroyOnLoad accumulation
```

### Agent: Architecture

```
Focus areas:
- System decomposition — clear boundaries between game systems
- Coupling analysis — which systems know about each other, dependency direction
- Data flow — ScriptableObject architecture, event buses, observer pattern
- MonoBehaviour vs plain C# — overuse of MonoBehaviour where POCO suffices
- ECS readiness — patterns that would/wouldn't migrate well (if DOTS detected)
- Scene architecture — prefab composition, scene loading strategy
- Configuration management — magic numbers, settings scattered vs centralized
- Scalability — what breaks when content/features grow 10x
- Module boundaries — could systems be extracted to packages
- Test architecture — untested critical paths, missing integration test seams
```

### Agent: Security

```
Focus areas:
- Sensitive data exposure — API keys, tokens, credentials in code or ScriptableObjects
- PlayerPrefs abuse — storing sensitive data in plaintext PlayerPrefs
- Input validation — user-facing input fields, chat, text entry without sanitization
- Serialization safety — JsonUtility / Newtonsoft deserialization of untrusted data
- Network security (if multiplayer detected):
  - Client authority abuse — trusting client-sent gameplay values
  - Unencrypted sensitive payloads
  - Missing server-side validation of game state
  - Replay attack vectors
- Asset bundle integrity — loading unsigned bundles from remote
- Debug/cheat code left in builds — #if UNITY_EDITOR guards, Debug.Log in hot paths
- Platform storage — sensitive files in persistent data path without encryption
- Third-party SDK permissions — analytics/ad SDKs requesting excessive permissions
```

### Mode → Agent mapping

| Mode         | Agents                                              |
|--------------|-----------------------------------------------------|
| Quick        | Code Quality, Bug Hunter                            |
| Performance  | Performance, Memory                                 |
| Architecture | Architecture, Security, Code Quality                |
| Full         | Code Quality, Bug Hunter, Performance, Memory, Architecture, Security |

## Step 5 — Compile report

After all agents complete, compile a unified review.

### Deduplication rules

When multiple agents flag the same issue:
- Keep the version with the most specific fix recommendation
- If both are equally detailed, keep the one from the more relevant agent domain
- Note cross-agent consensus: "[Flagged by 2 agents]" — these are higher confidence

### Conflict resolution

If agents give different health scores:
- Overall score = weighted average (Architecture and Security weight 1.5x, others 1x)
- If any agent gives Critical findings, overall score caps at 6/10

### Report template

```markdown
# Unity Review — [MODE] Mode
## Project: {context from Step 2}

## Overall Health: X/10

## Critical Issues (fix before merge)
...

## Warnings (fix soon)
...

## Suggestions (improve when convenient)
...

## Top 3 Priorities
1. ...
2. ...
3. ...

## Agent Summaries
### Code Quality: X/10
### Bug Hunter: X/10
### Performance: X/10
### Memory: X/10
### Architecture: X/10
### Security: X/10
```

Only include sections for agents that actually ran.
