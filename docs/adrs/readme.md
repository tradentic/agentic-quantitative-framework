# Architecture Decision Records (ADR)

This directory holds **Architecture Decision Records** for `next-ai-presets`.

## Why ADRs?
ADRs capture significant technical decisions, the context that led to them, and their consequences. They create a durable trail of **why** the system looks the way it does—useful for maintainers, contributors, and future you.

## Conventions
- **Location:** `adr/`
- **Naming:** `NNNN-title-with-dashes.md` (zero‑padded incremental number)
- **Status values:** `Proposed`, `Accepted`, `Superseded`, `Deprecated`.
- **Tone:** concise, factual, link to deeper docs when helpful.

## Template
Copy this into a new file (e.g., `adr/0002-some-decision.md`):

```md
# ADR NNNN — Title

- **Status:** Proposed | Accepted | Superseded | Deprecated  
- **Date:** YYYY-MM-DD  
- **Owner:** <maintainer or team>  
- **Decision type:** Architecture | Process | Tooling

## Context
<What problem are we solving? What constraints and options are relevant?>

## Decision
<The decision we made. List the key points clearly.>

## Rationale
<Why this option? Contrast with alternatives.>

## Options considered
- Option A — pros/cons
- Option B — pros/cons
- Option C — pros/cons

## Consequences
- Positive
- Negative / Costs

## Implementation sketch
<High-level notes: repo layout, APIs, workflows, migration/rollout>

## Security & safety notes
<Secrets, permissions, guardrails>

## Test strategy
<How we’ll validate the decision continues to hold>

## Rollback plan
<What we’ll do if this turns out wrong>

## Links
- Related docs / PRs / issues
```

## Index
- [0001 — CLI & TUI share a single Core (spec‑first)](./0001-cli-and-tui-shared-core.md)

---

*Add your next ADR with `0002-...` and update the index above.*

