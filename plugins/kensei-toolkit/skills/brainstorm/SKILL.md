---
name: brainstorm
description: Collaborative design dialogue before implementation — turns an idea into a validated design through one-at-a-time questions, honest challenge, approach exploration, and incremental validation. Use when the user explicitly asks to brainstorm or design together — "brainstorm", "let's brainstorm", "help me design", "explore options for", "давай обсудим идею", "помоги спроектировать", "продумай со мной". Not for routine implementation requests or quick questions.
argument-hint: "[topic or idea]"
---

# Brainstorm — turn an idea into a design through dialogue

Collaborative and conversational. The deliverable is a validated design captured in a brainstorm doc plus a standalone implementation plan; implementation is a separate decision at the end, made by the user. If `$ARGUMENTS` is non-empty, it's the topic — start from it instead of asking what to brainstorm.

## Custom rules

If `.claude/brainstorm-rules.md` exists in the project, Read it before starting. Its content (design preferences, technology constraints, conventions) supplements this skill's process — it refines the dialogue, never replaces the phases. If the file doesn't exist, proceed silently.

## Scale check

Gauge the size before committing to the full process:

- **Small** — a utility, a single component, an isolated tweak. Compress: quick context check, at most one clarifying question, one recommended approach with an alternative mentioned in passing, design in a single message. No brainstorm doc or plan file unless the user asks. Don't ceremony a 20-line change — but still end by asking whether to implement now, not by implementing.
- **Large** — a feature, a system, an architectural decision. Full process below.

When genuinely unsure, ask the user which depth they want.

## Phase 1 — Understand

1. Gather context first: relevant files, docs, recent commits (`git log --oneline -15`). In a large or unfamiliar codebase, delegate the sweep to an Explore agent and keep only its conclusions.
2. Then ask questions **one at a time**. Use AskUserQuestion with concrete options whenever the choices are enumerable; fall back to free-form only when the answer space is open.
3. Cover: purpose (what problem this solves), constraints, success criteria, integration points.

Stop asking when you can state the problem back in two sentences and the user confirms it.

## Phase 2 — Challenge

Before designing, stress-test the idea:

- What assumptions is it standing on, and which are unverified?
- What's the simplest thing that could work instead — including "do nothing" or an existing tool?
- What's the riskiest part, and what breaks if it's wrong?

Share findings briefly and honestly. If the idea isn't worth building or a far simpler path exists, say so directly with reasoning — "don't build it" is a legitimate brainstorm outcome. If the user decides to proceed anyway, that's their call; continue without relitigating.

## Phase 3 — Explore approaches

Propose 2–3 genuinely different approaches with trade-offs. Lead with the recommended one and explain why. Keep it conversational, not a formal document:

```
I see three approaches:

**Option A: [name]** (recommended)
- how it works: ...
- pros: ...
- cons: ...

**Option B: [name]**
- ...

Which direction appeals to you?
```

The user picks before you move on.

## Phase 4 — Design in sections

Present the design in sections of 200–300 words; after each, confirm it looks right before continuing. Never dump the full design at once — incremental validation catches misunderstandings while they're cheap.

Choose sections that fit the topic instead of forcing one template:

- **Code / system**: architecture, components, data flow, error handling, testing
- **Gameplay feature**: mechanics, data/config, player-facing behavior, edge cases, tuning knobs
- **UX / UI**: flows, states, components, feedback

Backtrack freely when something doesn't hold up — a wrong turn discovered in section 2 costs minutes, in implementation it costs days.

## Phase 5 — Capture and hand off

The brainstorm ends with two files on disk and a question — never with implementation already running. Do not call EnterPlanMode and do not start editing code on your own: a plan that lives only in this session dies with it, and the user may want to run it later, in another terminal, worktree or machine.

1. Write the brainstorm doc to `docs/brainstorms/YYYY-MM-DD-<slug>.md` (use the project's established docs location if it has one):
   - problem statement and constraints
   - chosen approach and why
   - rejected alternatives with one-line reasons
   - the validated design (sections from Phase 4)
   - open questions
2. Write the implementation plan next to it — `docs/brainstorms/YYYY-MM-DD-<slug>-plan.md`. Its reader is a fresh session with no memory of this dialogue, so it must stand on its own:
   - a link to the brainstorm doc and a 2–3 sentence goal
   - context the executor would otherwise have to rediscover: repo/project path, key files and entry points, conventions that matter
   - ordered steps; each names the files it touches and how to verify it is done (a command, a test, an observable behavior)
   - acceptance criteria for the whole change
   - out of scope — what was deliberately left out, so the executor doesn't "helpfully" add it
   - open questions the executor must ask the user about rather than decide
   Concrete over generic: real paths, real names, real commands. No step that just says "implement X".
3. Show both paths and the ready-to-paste launch line, using the plan's absolute path:
   ```
   claude "Implement the plan in /abs/path/to/…-plan.md — read it and the brainstorm doc it links first"
   ```
4. Ask via AskUserQuestion — "Design and plan are saved. What's next?":
   - **Save only** — stop here; the user picks the plan up whenever and wherever it suits them
   - **Start here** — implement in this session, following the plan file step by step
   - **Revise the plan** — adjust the plan file first, then ask again

   Start implementation only on an explicit **Start here**.

## Early exit

If mid-process the user says "enough, just do it" or clearly wants to move on: summarize the decisions made so far in 3–5 bullets, write the brainstorm doc and the plan from what's known, and proceed to their requested action. Don't force the remaining phases. An explicit "just do it" counts as **Start here**; "enough" alone does not — save and ask.

## Key principles

- One question at a time — never stack questions in one message.
- Multiple choice over open-ended whenever options are enumerable.
- YAGNI ruthlessly — strip everything the problem doesn't demand; keep scope minimal.
- Lead with a recommendation and reasoning; the user decides.
- Duplication vs abstraction: when repetition appears in a design, present both options with trade-offs and let the user choose.
- Honest challenge beats polite agreement — the user came for thinking, not validation.

## Language

Run the dialogue and write the brainstorm doc in the language the user is using in the session.
