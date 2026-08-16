# Plan: Program Manager Role

<!--
Implementation Plan
Filename: artifacts/plan_program_manager_role.md
Owner: Engineering (framework tooling, not app code)
Handoff to: Engineering (implementation), /code-check (review), /swarm-review (audit)
Related Skills: swarm-plan, swarm-review, planning-artifacts
-->

## Overview

**Status:** Complete (Phases 1-3; Phase 4 remains optional/deferred per Scope)
**Author:** Claude (session), reviewed with Jamie Witt
**Date:** 2026-08-10
**Tracking Issue:** N/A — create once this plan is approved
**Related PRD:** N/A — Small Feature per `swarm-plan`'s own Artifact Requirements tier (describable in a few sentences; plan-only)
**Related ADR:** N/A

## Objective

Add a `program-manager` role to this project's `.claude/` agentic framework: a user-invoked skill (`/program-manager`) that decomposes an approved plan or PRD into scoped GitHub issues, each carrying Given/When/Then acceptance criteria and tagged so a plan's overall status (open vs. closed issues) is queryable directly from `gh issue list`. Wire it into the existing planning → build → review pipeline so `/swarm-review` (or any reviewer) verifies implementations against the same acceptance criteria the issues were created with.

## Scope

### In Scope

- New top-level role-command skill: `.claude/skills/program-manager/SKILL.md`
- New supporting/library skill, new `delivery/` category: `.claude/skills/delivery/writing-acceptance-criteria/SKILL.md`
- Handoff wiring: `swarm-plan.md`, `swarm-review.md`, `planning-artifacts/SKILL.md` (cross-reference), `CLAUDE.md` Commands table
- A corrective note in `swarm-plan.md` next to its `TaskCreate`/`TaskUpdate` references, redirecting durable tracking to `/program-manager`
- Dry-run verification against the real `artifacts/plan_collectible_dispatch_refactor.md` (dogfooding — its Phases 1-3 are marked done but were never issue-tracked)

### Out of Scope

- Rewriting/removing the `TaskCreate`/`TaskUpdate` references throughout `swarm-plan.md`/`swarm-execute.md` wholesale — flagged via the corrective note above, not fixed beyond it. This is a separate, pre-existing framework defect (confirmed via direct `ToolSearch`: those tools don't exist in this environment), independent of adding this role.
- `swarm-execute.md` accepting a GitHub issue number/URL directly as its `argument-hint` input (it currently reads `[plan-artifact-or-task-id]`) — captured as an optional Phase 4 below, not required for this role to be usable.
- A formal eval suite (`evals/evals.json`) for the new skill — this framework applies evals selectively today (5 of ~17 existing skills have them, none of the role-commands like `/architect`/`/builder`/`/qa-engineer` do), so it's not a baseline requirement. Can be added later per the eval-first policy in `CONTRIBUTING.md` if this role sees real usage.
- Any change to `AGENTS.md` — its "Task Tracking" section is already tool-agnostic and correctly describes the target state (GitHub Issues as the durable Tier-1 record) without naming a Claude-Code-specific command. Nothing to fix there.
- Upstreaming this role to `dralgorhythm/claude-agentic-framework` — a separate decision for later, not part of this plan.

## Technical Approach

### Architecture Changes

Two new skill files plus surgical edits to four existing files. No application code or runtime changes — this is `.claude/` config and docs only, consistent with everything else in this framework.

```
.claude/skills/
├── program-manager/SKILL.md          [NEW — top-level role command]
└── delivery/                          [NEW category]
    └── writing-acceptance-criteria/
        └── SKILL.md                   [NEW — supporting/library skill]
```

### Key Decisions

| Decision | Rationale |
|----------|-----------|
| Name: `program-manager`, not "product lead" | The role decomposes plans into trackable, criteria-bearing work items — a Technical Program Manager function, not product strategy/discovery (already `product/planning-artifacts`' territory, and the only thing third-party "product manager" marketplace packs actually offer — checked `pmprompt/claude-plugin-product-management` in full: OKRs, growth loops, JTBD, pricing, none of it this). Keeps `product/` from being overloaded with a different discipline. |
| Location: top-level `.claude/skills/program-manager/SKILL.md`, not nested under a category | `.claude/templates/skill.template.md` states command-style (slash-invoked, `disable-model-invocation: true`) skills live at the top level. Verified empirically, not just from the doc comment: all 12 existing role-commands (`architect`, `builder`, `qa-engineer`, `security-auditor`, `ui-ux-designer`, `code-check`, `land-the-plane`, `tailor`, `swarm-plan`, `swarm-execute`, `swarm-review`, `swarm-research`) are top-level with directory name == frontmatter `name`, zero exceptions. Category subdirectories (`product/`, `architecture/`, `security/`, `operations/`, `core-engineering/`) are reserved for auto-discovered supporting/library skills (no `argument-hint`/`disable-model-invocation`). |
| New `delivery/` category for a *supporting* skill, not the role itself | Matches the existing pattern: `/architect` (top-level) is supported by `architecture/designing-systems` and `architecture/writing-adrs`. `/program-manager` (top-level) gets `delivery/writing-acceptance-criteria` as its supporting skill — reusable by `/builder`, `/swarm-review`, and `planning-artifacts`' PRD-writing without any of them needing to invoke the full role. |
| Status rollup via a `plan:<slug>` GitHub label | This repo's own two-tier convention (`AGENTS.md`, `swarm-coordination`) already names GitHub Issues as the durable Tier-1 record. A label makes "which issues belong to plan X" and "is plan X done" answerable with one command — `gh issue list --label "plan:<slug>" --state all` — no new infrastructure needed. |
| Label/backlink/rollup convention lives directly in `program-manager.md`, not a second `delivery/` skill | Unlike Given/When/Then authoring, this convention is specific to program-manager's own job; no other role independently needs it. A second library skill here would be premature fragmentation. |
| Corrective note (not a rewrite) in `swarm-plan.md` | `TaskCreate`/`TaskUpdate` don't exist as real tools — confirmed directly via `ToolSearch`, not assumed from the docs. But rewriting that whole apparatus is a separate, pre-existing defect; a clear note redirecting to `/program-manager` is enough to stop the two descriptions from silently contradicting each other. |

## Implementation Steps

### Phase 1: Core role skill

- [ ] **Step 1.1:** Create `.claude/skills/program-manager/SKILL.md`
  - Files: `.claude/skills/program-manager/SKILL.md`
  - Frontmatter: `name: program-manager`; `description` (≤500 chars, third person; no "Use when" required since `disable-model-invocation: true` waives it); `argument-hint: "[plan-or-prd-artifact-path]"`; `disable-model-invocation: true`
  - Body sections, matching the existing role-command pattern (see `architect`/`builder`/`qa-engineer`):
    - **Method** — defers to `writing-acceptance-criteria` for GWT conventions (don't relearn structure inline)
    - **CLI Tools** — `gh issue create`, `gh label create`/`gh label list`, `gh issue list` (matches the `gh` section style already used in `swarm-review.md`)
    - **Workflow** — (1) read the source plan/PRD artifact; (2) decompose into right-sized units reusing `swarm-plan`'s existing 200-400 LOC / 15-45 min sizing rule (don't invent a new one); (3) ensure the `plan:<slug>` label exists, creating it if not (`gh label list --search` then `gh label create` if missing); (4) per unit, `gh issue create` with: title, Given/When/Then acceptance criteria in the body, a backlink line (`Plan: artifacts/<file>.md`, plus phase if applicable), the `plan:<slug>` label (and a `phase:N` label if the source plan has numbered phases); (5) report the rollup query back to the user
    - **Status Rollup** — document `gh issue list --label "plan:<slug>" --state all`; open vs. closed count = plan completion
    - **Constraints** — NO issue without GWT acceptance criteria; NO decomposition without reading the source artifact first; NO implementing (handoff to `/builder`); ALWAYS verify/create the plan label before the first issue; ALWAYS include the backlink line
    - **Output** / **Handoff** — From: `/architect`, `/swarm-plan` (plan/PRD ready); To: `/builder` (implement against an issue's GWT), `/swarm-review` (verify against the same GWT before closing)

### Phase 2: Supporting skill

- [ ] **Step 2.1:** Create `.claude/skills/delivery/writing-acceptance-criteria/SKILL.md`
  - Files: `.claude/skills/delivery/writing-acceptance-criteria/SKILL.md`
  - Auto-discoverable (no `argument-hint`/`disable-model-invocation`); description must contain "Use when" per the ungated-skill CI rule
  - Content: what makes a testable Given/When/Then (one behavior per criterion, no implementation detail, no vague outcomes like "works correctly"); granularity guidance distinguishing story-level (PRD, `planning-artifacts`) from task-level (issue, `program-manager`); 2-3 good/bad examples

### Phase 3: Wire up handoffs

- [ ] **Step 3.1:** `CLAUDE.md` — add `/program-manager` row to the Commands table, positioned after `/architect` (Role: "Technical Program Manager"; Use: "Plan/PRD → tracked GitHub issues with acceptance criteria")
- [ ] **Step 3.2:** `.claude/skills/swarm-plan/SKILL.md` —
  - Add a corrective note directly beside the existing "Task Creation" section: `TaskCreate`/`TaskUpdate` are not available tools in this environment; hand off to `/program-manager` for durable, queryable tracking instead
  - Update step 5 ("Track") to read: hand off to `/program-manager` to translate the plan into tracked, criteria-bearing GitHub issues
  - Add a Handoff line: "To `/program-manager`: Plan/PRD artifact ready for issue breakdown"
- [ ] **Step 3.3:** `.claude/skills/swarm-review/SKILL.md` — add a check to the Review Workflow/Adversarial Questions: when a diff closes a GitHub issue created via `/program-manager` (identifiable by its `plan:*` label and Given/When/Then body), verify each acceptance criterion explicitly, not just general code quality
- [ ] **Step 3.4:** `.claude/skills/product/planning-artifacts/SKILL.md` — light-touch: point the PRD Essentials line at `writing-acceptance-criteria` for the authoring convention, instead of relying only on the inline template example
- [ ] **Step 3.5:** `.claude/skills/builder/SKILL.md` — two fixes, found by checking (not assuming) whether this skill can actually consume program-manager's output:
  - Its "MCP Tools: GitHub" section names a GitHub MCP server that does not exist — confirmed via `.mcp.json` (only `sequential-thinking`, `chrome-devtools`, `filesystem`, `context7` are configured). Replace with a "CLI Tools: gh (GitHub CLI)" section matching the real, working pattern already used in `swarm-review.md` (`gh issue view <N>`, `gh pr view`).
  - Independent of that fix: nothing in the Implementation Workflow reads an issue's body at all — issues are only used for status/dependency bookkeeping. Add a step: when the task originates from a `/program-manager`-created GitHub issue, fetch its Given/When/Then via `gh issue view <N>` and treat it as the "done when" the red-green-observe loop (step 5, already present) requires — not a new concept, just wiring the existing one to the right source.
  - Add "From: `/program-manager` (issue with acceptance criteria) or a plan artifact" to Handoff, and note the issue number should be carried forward to `/land-the-plane` so it can close the loop (see Step 3.6).
- [ ] **Step 3.6:** `.claude/skills/land-the-plane/SKILL.md` — Step 5 ("Handoff") currently opens a PR with no link back to any originating issue. Add: when the landed work closes a `/program-manager`-created issue, include `Closes #N` in the PR body so GitHub auto-closes it on merge. Without this, the `plan:<slug>` label rollup (open vs. closed = plan status) never reflects real progress — issues would stay open regardless of shipped work. This is the load-bearing fix that makes the whole design's stated purpose ("look through open and closed issues to determine plan status") actually true.

### Phase 4: Optional, not blocking

- [ ] **Step 4.1:** `.claude/skills/swarm-execute/SKILL.md` — accept a GitHub issue number/URL in its `argument-hint`, resolving acceptance criteria from the issue body as an alternative to a plan artifact. This is the parallel-execution path's equivalent of Step 3.5 — `worker-builder.md` itself needs no change (checked: it's deliberately stateless per `agent-constraints.md`'s no-shared-state rule, so acceptance criteria would need to be fetched by the orchestrator and forwarded into each worker's prompt, not fetched by the worker itself). Kept optional/deferred since single-agent `/builder` (Step 3.5) is the primary path; swarm parallelism is secondary usage.

## Files to Modify

| File | Action | Description |
|------|--------|-------------|
| `.claude/skills/program-manager/SKILL.md` | Create | New role-command skill |
| `.claude/skills/delivery/writing-acceptance-criteria/SKILL.md` | Create | New supporting skill, new `delivery/` category |
| `CLAUDE.md` | Modify | Add `/program-manager` to Commands table |
| `.claude/skills/swarm-plan/SKILL.md` | Modify | Corrective `TaskCreate` note, Track step, Handoff line |
| `.claude/skills/swarm-review/SKILL.md` | Modify | GWT-verification check in review workflow |
| `.claude/skills/product/planning-artifacts/SKILL.md` | Modify | Cross-reference `writing-acceptance-criteria` |
| `.claude/skills/builder/SKILL.md` | Modify | Fix non-existent "GitHub MCP" reference → real `gh` CLI; consume an issue's GWT as the implementation's "done when"; Handoff update |
| `.claude/skills/land-the-plane/SKILL.md` | Modify | `Closes #N` in PR body when landing work that closes a `/program-manager` issue — closes the status-rollup loop |
| `.claude/skills/swarm-execute/SKILL.md` | Modify (Phase 4, optional) | Accept a GitHub issue as input |

## Dependencies

### Code Dependencies

None — config/docs only, no application code touched.

### Service Dependencies

| Service | Status | Notes |
|---------|--------|-------|
| `gh` CLI, authenticated | Available | Confirmed working this session (used to create issues #102-109) |

## Testing Strategy

No automated test suite applies — this is prompt/config content, not application code. Verification is manual:

### Manual Testing

- [x] Dry run: manually walked `program-manager.md`'s own documented Workflow steps against `artifacts/plan_collectible_dispatch_refactor.md` (couldn't literally invoke `/program-manager` from within the same session that just created it — the skill didn't exist yet when this session started). Created `plan:collectible-dispatch-refactor` + `phase:1`/`phase:2`/`phase:3` labels, then 3 representative issues (#110, #111, #112 on `wittjr/gameworn`) with real Given/When/Then criteria checkable against the actual Phase 1-3 diffs. Label creation, backlink line, and GWT formatting all correct.
- [x] Confirmed `gh issue list --label "plan:collectible-dispatch-refactor" --state all` returns exactly #110/#111/#112 and nothing else. Deliberately left all 3 **open** rather than closing them — the collectible-dispatch work is fully implemented and reviewed but still uncommitted/unpushed in this session (nothing was ever committed per "only commit when asked"), so closing them would misrepresent reality. This is itself a correct demonstration of Step 3.6's mechanism: the rollup will flip to closed only once that work is actually landed with `Closes #N` in the PR, not before.
- [ ] (Deferred, not blocking) Author `evals/evals.json` later per the eval-first policy, if/when this role sees enough real usage to warrant formalizing confidence in it.

## Rollback Plan

1. `git checkout` the 4-5 modified existing files
2. `rm -rf .claude/skills/program-manager .claude/skills/delivery`
3. No data/schema impact — purely additive/doc changes with surgical edits, nothing to migrate back

## Risks

| Risk | Mitigation |
|------|------------|
| GH label proliferation (`plan:<slug>` per plan, growing unbounded) | Acceptable — labels are cheap and filterable; note that stale plan labels can be deleted once fully closed, if desired |
| `program-manager` decomposing too coarsely or too finely | Reuse `swarm-plan`'s already-calibrated 200-400 LOC / 15-45 min sizing rule rather than inventing a new one |
| Two contradictory "how tasks get tracked" descriptions left in the framework | Make the corrective note in `swarm-plan.md` explicit and placed directly beside the existing "Task Creation" section header, not buried elsewhere |
| Issues never auto-close, so the status rollup silently stops reflecting reality | This is why Step 3.6 (`land-the-plane` → `Closes #N`) is treated as required, not optional — without it, the design's stated purpose doesn't hold even though the label/backlink mechanics work correctly |
| A third "references a tool that doesn't exist" instance (`/builder`'s "GitHub MCP") found only because this question prompted checking a consumer skill directly | Suggests other skills may reference tools not actually wired up in this environment. Worth a dedicated sweep (`grep -rn "MCP" .claude/skills/*/SKILL.md` cross-checked against `.mcp.json` and `ToolSearch`) as separate follow-up — out of scope for this plan, but flagged so it isn't lost |

## Checklist

### Before Starting

- [x] Plan reviewed with user (this document)
- [ ] User approves proceeding with implementation

### Before Treating the Role as Ready to Use

- [x] All Phase 1-3 files created/edited
- [x] Dry run against `plan_collectible_dispatch_refactor.md` completed and resulting issues manually verified
- [x] `gh issue list --label` rollup query confirmed working end to end

## Notes

This plan is an instance of what it describes. Once implemented, running `/program-manager` against this very artifact (`plan_program_manager_role.md`) is the natural first dogfooding pass, alongside the dry run against the collectible-dispatch plan.

---

## Progress Log

| Date | Update |
|------|--------|
| 2026-08-10 | Plan drafted: researched upstream `dralgorhythm/claude-agentic-framework` (no product-lead/PM role exists, current as of v5.0.0) and third-party marketplaces (none fit — all are product-strategy content, not delivery tracking); settled naming (`program-manager` over "product lead") and category placement (top-level role + new `delivery/` supporting category) with user. |
| 2026-08-10 | Added Steps 3.5/3.6 after checking whether `/builder`/`/land-the-plane` could actually consume program-manager's output: found `/builder` references a non-existent "GitHub MCP" (confirmed via `.mcp.json` — third instance of this class of bug, after `TaskCreate`/`TaskUpdate`) and never reads issue acceptance criteria at all; found `/land-the-plane` never links a PR back to an issue, meaning the status-rollup mechanism would silently never update without it. Elevated the `land-the-plane` fix to required (moved out of "optional") since the design's stated purpose depends on it. |
| 2026-08-10 | Implemented Phases 1-3: created `program-manager/SKILL.md` and `delivery/writing-acceptance-criteria/SKILL.md`; edited `CLAUDE.md`, `swarm-plan.md`, `swarm-review.md`, `planning-artifacts/SKILL.md`, `builder/SKILL.md`, `land-the-plane/SKILL.md` per Steps 3.1-3.6. Dry-ran the documented workflow by hand against `plan_collectible_dispatch_refactor.md`: created `plan:collectible-dispatch-refactor` + 3 phase labels and issues #110-112 with real, verifiable GWT criteria. Rollup query (`gh issue list --label ... --state all`) confirmed correct (3 open, 0 closed, no leakage). Left issues open rather than closing them, since the underlying work is implemented/reviewed but not yet committed or pushed — correctly reflecting real state rather than performing a hollow test. Phase 4 (`swarm-execute` GH-issue input) remains deferred, as scoped. |
