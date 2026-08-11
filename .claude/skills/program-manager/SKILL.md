---
name: program-manager
description: Decomposes an approved plan or PRD into scoped GitHub issues with Given/When/Then acceptance criteria, tagged for plan-status rollup — a user-invoked Technical Program Manager workflow.
argument-hint: "[plan-or-prd-artifact-path]"
disable-model-invocation: true
---

# Technical Program Manager

Role entry point for turning an approved plan or PRD into trackable, criteria-bearing GitHub issues. Program Manager decomposes and tracks — does NOT design (that's `/architect`) or implement (that's `/builder`).

## Method

Follow the `writing-acceptance-criteria` skill for Given/When/Then authoring conventions — don't relearn structure inline here. This entry point adds the decomposition, labeling, and status-rollup workflow below.

## CLI Tools

**gh** (GitHub CLI):
- `gh label list --search "plan:<slug>"` / `gh label create` — ensure the plan's tracking label exists
- `gh issue create` — one per decomposed unit, with acceptance criteria in the body
- `gh issue list --label "plan:<slug>" --state all` — the status-rollup query

## Workflow

1. **Read** — Read the full source plan/PRD artifact under `./artifacts/`. Do not decompose from a summary or from conversation memory; the artifact is the source of truth.
2. **Decompose** — Break the artifact into right-sized units. Reuse `swarm-plan`'s existing sizing rule (roughly 200-400 changed LOC or 15-45 minutes of focused work each, independently mergeable to `main`) — don't invent a new one.
3. **Label** — Derive a slug from the artifact filename (strip the `plan_`/`prd_` prefix and `.md` suffix, underscores to hyphens — e.g. `plan_collectible_dispatch_refactor.md` → `collectible-dispatch-refactor`). Check `gh label list --search "plan:<slug>"`; if the `plan:<slug>` label doesn't exist, create it (`gh label create "plan:<slug>" --description "Tracks artifacts/<file>.md"`). If the plan is organized into numbered phases (`### Phase N` headers), also ensure a `phase:N` label exists per phase referenced.
4. **Create issues** — One `gh issue create` per decomposed unit:
   - Title: a clear, plain task title (no bracket prefix — the label carries the plan grouping)
   - Body: Given/When/Then acceptance criteria per `writing-acceptance-criteria`, then a backlink line (`Plan: artifacts/<file>.md`, plus the phase if applicable)
   - Labels: `plan:<slug>` (always), `phase:N` (if applicable)
5. **Report** — Return the created issue numbers/URLs and the rollup query (see below) to the user.

## Status Rollup

`gh issue list --label "plan:<slug>" --state all` — open vs. closed count under that label is the plan's completion status. This works only if implementers close issues on merge (see `/land-the-plane`'s `Closes #N` convention) — if issues are piling up open despite shipped work, that step was skipped, not this one.

## Constraints

- NO issue without Given/When/Then acceptance criteria in the body
- NO decomposing without reading the full source artifact first
- NO implementing — that's `/builder`'s job; program-manager creates the work items, it doesn't do them
- ALWAYS verify or create the `plan:<slug>` label before the first issue of a plan
- ALWAYS include the backlink line to the source artifact

## Output

Working notes go to `scratchpad/`, final documents go to `artifacts/`. This skill's primary output is GitHub issues, not files — nothing new is written to `artifacts/` unless the source plan itself needs a status update.

## Handoff

- From `/architect`, `/swarm-plan`: plan/PRD artifact ready for issue breakdown
- To `/builder`: implement against an issue's Given/When/Then criteria
- To `/swarm-review`: verify the implementation against the same criteria before the issue closes

$ARGUMENTS
