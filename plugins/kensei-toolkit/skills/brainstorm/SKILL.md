---
name: brainstorm
description: Collaborative design dialogue before implementation — turns an idea into a validated design through one-at-a-time questions, honest challenge, approach exploration, and incremental validation. Use when the user explicitly asks to brainstorm or design together — "brainstorm", "let's brainstorm", "help me design", "explore options for", "давай обсудим идею", "помоги спроектировать", "продумай со мной". Not for routine implementation requests or quick questions.
argument-hint: "[topic or idea]"
---

# Brainstorm — turn an idea into a design through dialogue

Collaborative and conversational. The deliverable is a validated design captured in a brainstorm doc; implementation is a separate decision at the end. If `$ARGUMENTS` is non-empty, it's the topic — start from it instead of asking what to brainstorm.

## Custom rules

If `.claude/brainstorm-rules.md` exists in the project, Read it before starting. Its content (design preferences, technology constraints, conventions) supplements this skill's process — it refines the dialogue, never replaces the phases. If the file doesn't exist, proceed silently.

## Scale check

Gauge the size before committing to the full process:

- **Small** — a utility, a single component, an isolated tweak. Compress: quick context check, at most one clarifying question, one recommended approach with an alternative mentioned in passing, design in a single message. No brainstorm doc unless the user asks. Don't ceremony a 20-line change.
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

1. Write the brainstorm doc to `docs/brainstorms/YYYY-MM-DD-<slug>.md` (use the project's established docs location if it has one):
   - problem statement and constraints
   - chosen approach and why
   - rejected alternatives with one-line reasons
   - the validated design (sections from Phase 4)
   - open questions
   The doc must survive the session regardless of what happens next.
2. Then ask via AskUserQuestion — "Design is captured. What's next?":
   - **Plan mode** — EnterPlanMode for structured implementation planning
   - **Start now** — implement directly; fine for small scope
   - **Stop here** — the doc is saved; the user returns to it later

## Early exit

If mid-process the user says "enough, just do it" or clearly wants to move on: summarize the decisions made so far in 3–5 bullets, write the brainstorm doc from what's known, and proceed to their requested action. Don't force the remaining phases.

## Key principles

- One question at a time — never stack questions in one message.
- Multiple choice over open-ended whenever options are enumerable.
- YAGNI ruthlessly — strip everything the problem doesn't demand; keep scope minimal.
- Lead with a recommendation and reasoning; the user decides.
- Duplication vs abstraction: when repetition appears in a design, present both options with trade-offs and let the user choose.
- Honest challenge beats polite agreement — the user came for thinking, not validation.

## Language

Run the dialogue and write the brainstorm doc in the language the user is using in the session.
