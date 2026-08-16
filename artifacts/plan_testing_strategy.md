# Testing Strategy Plan — Gameworn

**Type:** Plan (QA strategy audit)
**Scope:** `memorabilia/`, `django_flowbite_widgets/`, CI/CD pipeline, database backends
**Deployment flow considered:** local (SQLite) → PythonAnywhere/UAT (MySQL) → Azure/prod (MSSQL)
**Date:** 2026-08-15
**Author:** `/qa-engineer`

## Executive summary

The suite itself is in better shape than its size in memory suggested — **391 test methods across 58 `TestCase` classes** (not the ~104 previously recorded), covering CRUD, permissions, type conversion, bulk edit, MeiGray import/export, want lists, marketplace, and a signed-webhook inbound email relay. That's a real asset, not a gap.

The gaps are structural, not volume: **the suite never runs automatically**, and **it only ever runs against SQLite** — never against either of the two databases the app is actually deployed to. Given the stated deployment flow (SQLite → MySQL → MSSQL), those two facts together mean the test suite currently provides no protection against the single riskiest class of bug this stack can produce: a query, migration, or field behavior that works on SQLite and breaks on MySQL or MSSQL. Everything else in this plan is secondary to fixing those two things.

## Current state — what's working

- 391 tests, well-organized by concern (`CollectionCRUDTests`, `WantListCRUDTests`, `MeiGrayImportCommandTests`, `MailgunInboundWebhookTests`, etc.), using a shared `BaseTestCase` fixture setup
- Permission tests exist per collectible type (login redirect + 403 for non-owner) — a pattern that's easy to skip and wasn't
- Security-relevant surfaces already have dedicated tests: `SecuritySettingsTests`, signature verification in `MailgunInboundWebhookTests` (valid signature, bad signature, replay/unknown-token handling)
- A `Django60CompatibilityTests` class exists — evidence the team already tests framework upgrades deliberately rather than assuming
- `test_settings.py` correctly isolates tests to an in-memory SQLite DB, so the suite is fast and self-contained today

## Findings

### 1. No CI gate runs the test suite at all
**Severity: Critical**

Checked the actual deploy path: `.github/workflows/azure_deploy.yaml` calls a reusable workflow (`wittjr/workflows/.github/workflows/azure-heavyuse-deploy.yml`) whose only steps are `pip install`, `collectstatic` (under `gameworn.ci_settings`, which exists solely to give `collectstatic` a working DB engine — SQLite — so it doesn't need a live MSSQL connection), and `azure/webapps-deploy`. **There is no test step.** `gh run list` confirms the only workflows that have ever run are Dependabot's graph update, the uat→main sync, and this deploy job.

That means: merging to `main` deploys straight to Azure production, and the only thing standing between a broken change and production is whether a human happened to run `make test` locally first. 391 tests is not a safety net if nothing ever runs it.

**Fix:** Add a `test` job to CI that runs on every PR into `uat` (and again before the `main` deploy, as a deploy gate) — see Recommendation 1 below.

### 2. The suite only ever runs against SQLite — never MySQL or MSSQL
**Severity: Critical**

`test_settings.py` hardcodes `django.db.backends.sqlite3` / `:memory:`. `ci_settings.py` — the only other test-adjacent settings file — also hardcodes SQLite. Nothing in the repo runs `manage.py test` (or even `manage.py migrate`) against `mysql` or `mssql`. Given the actual deployment targets (`pa_settings.py` → MySQL via `mysqlclient`, `settings.py` → MSSQL via `mssql-django`/`pyodbc`), this is exactly the gap the user asked about.

Concrete risk classes this leaves uncovered:
- **Migrations that apply cleanly on SQLite but fail on MySQL/MSSQL** — e.g. adding a `NOT NULL` column without a default, index length limits on MySQL `TEXT`/`VARCHAR`, MSSQL's stricter transaction-per-migration DDL rules
- **Case sensitivity / collation differences** — SQLite string comparisons are case-sensitive by default; MySQL's default collation is often case-insensitive; `.filter(field__iexact=)`, uniqueness constraints, and lookups like the MeiGray tag/player matching logic can silently behave differently per backend
- **`LIMIT`/`OFFSET` and pagination translation** — `mssql-django` translates these to `TOP`/`OFFSET FETCH`; subtly different edge-case behavior (e.g. `[:0]` slices, combined `order_by` + slicing) is a known source of backend-specific bugs
- **Boolean and null handling** — MSSQL has no native boolean type (`mssql-django` maps to `bit`); MySQL's `TINYINT(1)` behavior for booleans is nuanced too
- **Auto-increment/identity gaps** after failed inserts, and `bulk_create`/`get_or_create` race behavior, which the `MeiGrayImportCommandTests` and bulk-edit tests exercise logically but only against SQLite's semantics

Given the app has 70+ migrations already (including the recent MeiGray schema work) and both a MySQL and an MSSQL production-adjacent environment, this is the highest-leverage fix available — more valuable right now than any new test class.

**Fix:** Add MySQL and MSSQL service-container jobs in CI (see Recommendation 2).

### 3. No coverage measurement
**Severity: Medium**

No `.coveragerc`, no `pytest-cov`/`coverage` in `requirements-dev.txt`, no coverage step anywhere. 391 tests is a count, not a coverage percentage — there's currently no way to answer "what fraction of `memorabilia/` is actually exercised" other than manual inspection (which is what this audit had to do).

**Fix:** Add `coverage` to `requirements-dev.txt`, wrap the `make test` target, and surface the report in CI as an artifact (start by reporting, not gating — see Recommendation 3).

### 4. Several real modules have zero direct tests
**Severity: Medium-High** (varies by module)

- **`memorabilia/templatetags/memorabilia_extras.py`** — `get_user_avatar_url`, `getmediaurl`, and `collage_rows` are used constantly across templates (every collection/collectible card, the homepage, collages) and have zero direct unit tests. `collage_rows` in particular has real branching logic (arranging N images into rows for a collage) that's exactly the kind of pure function that should have table-driven unit tests, not just incidental coverage via whatever templates happen to render in view tests.
- **`django_flowbite_widgets/`** — a custom `MultiValueField`/widget package (`flowbite_fields.py`, `flowbite_widgets.py`, ~280 lines) backing the image dropzone used on `CollectionForm` and elsewhere. Its `tests.py` is still the untouched Django app-scaffold stub (3 lines). Custom form field `compress`/`decompress` logic is exactly where subtle bugs hide (this is the same shape of bug class as the pickle issue below) and currently has no coverage at all.
- **`memorabilia/relay.py`** (218 lines, the Mailgun inbound relay logic) is exercised only indirectly through `MailgunInboundWebhookTests`, which tests the webhook view's behavior (signature check, relay-or-drop) but not `relay.py`'s internals directly. That's acceptable as integration coverage but means the module's edge cases (malformed subject/reference parsing, address construction) ride entirely on whatever the webhook tests happen to trigger.

**Fix:** See Recommendation 4 (prioritized: `memorabilia_extras.py` first — it's pure, cheap to test, and used everywhere).

### 5. Dead code with an unsafe deserialization pattern
**Severity: Medium (not currently exploitable, but a footgun)**

`memorabilia/widgets.py` defines `FlickrAlbumWidget`/`ImageGallery`, whose `compress`/`decompress` methods call `pickle.dumps`/`pickle.loads` (CWE-502 territory — untrusted `pickle.loads` is a classic RCE vector). Verified via grep: **this code is dead** — `forms.py` imports both classes but the only usage (`images = ImageGallery(required=False)`) is commented out. It's not reachable from any request today.

Being dead doesn't make it safe to leave around: it's exactly the kind of unused-but-plausible-looking code someone re-enables later without re-deriving why it was disabled, and per this repo's security enforcement ladder (`.claude/rules/security.md`), pickle-based deserialization of any value that could trace back to user input is a Critical-severity pattern the moment it's live.

**Fix:** Delete `FlickrAlbumWidget` and `ImageGallery` from `widgets.py` (and the dead import in `forms.py`) rather than writing tests for them — there's nothing to protect by testing unreachable code, and removing it is strictly safer than leaving a pickle-based path one uncommented line away from production. Keep `SpecifyImageWidget` only if it's actually used (grep shows it isn't imported anywhere either — verify and likely remove alongside).

### 6. 4,935-line single-file test suite
**Severity: Low (maintainability)**

All 391 tests live in one `memorabilia/tests.py`. It's well-organized *within* the file (58 clearly-named classes), but at this size it violates the same single-responsibility principle `.claude/rules/code-quality.md` asks of production code, and it's the file most likely to produce merge conflicts as the suite keeps growing.

**Fix:** Split into a `memorabilia/tests/` package mirroring the existing `memorabilia/views/` structure (`test_collections.py`, `test_collectibles.py`, `test_wantlist.py`, `test_meigray.py`, `test_marketplace.py`, `test_security.py`, etc.), with shared fixtures (`BaseTestCase`, `WantListBaseTestCase`) in a `test_base.py`. Mechanical refactor, zero behavior change — good candidate for a dedicated "Two Hats" refactor-only PR per `code-quality.md`.

### 7. No browser-level (E2E) or accessibility test automation
**Severity: Medium**

Per this skill's own workflow, UI-touching changes should get Chrome DevTools E2E coverage and a Lighthouse accessibility gate. Today, every test is a Django `TestCase`/test-client request — none execute JavaScript. That means none of the app's actual client-side behavior is under regression protection: the collectible-form wizard, the type-conversion UI, the gallery lightbox's keyboard navigation, the delete-confirmation modal, league/team datalist autocomplete, or dark-mode rendering.

This directly intersects with the open UI-audit issues from the design review (`plan:ui-audit-2026-08` — e.g. #123 and #127, which specifically add keyboard focus-trapping to the lightbox and delete modal): once those land, there will be zero automated way to catch a regression in that focus-management logic short of manual testing.

**Fix:** Not a full Playwright/Selenium buildout on day one — start narrow (see Recommendation 5).

## Recommended testing strategy

Map the pyramid to the actual deployment flow instead of treating "tests" as one undifferentiated layer:

```
                    ┌─────────────────────────┐
                    │   E2E / a11y (few)       │  Chrome DevTools, critical
                    │   Lighthouse gate         │  flows only (Rec. 5)
                    └─────────────────────────┘
              ┌───────────────────────────────────┐
              │   Cross-DB parity (MySQL + MSSQL)   │  same suite, run on both
              │   backends nightly + pre-deploy      │  real backends (Rec. 2)
              └───────────────────────────────────┘
        ┌─────────────────────────────────────────────┐
        │   Unit + integration (391 tests, growing)     │  SQLite in-memory,
        │   runs on every PR                            │  fast, existing (Rec. 1, 3, 4)
        └─────────────────────────────────────────────┘
```

### Recommendation 1 — CI test gate (do first)
Add a GitHub Actions workflow (`.github/workflows/test.yml`) that runs `make test SETTINGS=test` on every PR into `uat` and `main`. Make it a required check. This alone closes Finding 1 and is the cheapest, highest-leverage change in this plan — it makes the existing 391 tests actually mean something.

### Recommendation 2 — Cross-database parity job (do second)
Add a matrix job (or two dedicated jobs) that runs the **same test suite** against real `mysql:8` and `mcr.microsoft.com/mssql/server:2022-latest` service containers in CI, using new `gameworn.test_mysql_settings` / `gameworn.test_mssql_settings` modules that mirror `pa_settings.py`/`settings.py`'s DB config but point at the CI service container instead of PA/Azure. This requires installing `msodbcsql18` on the runner for the MSSQL job (Microsoft's apt repo, well-documented for `ubuntu-latest`) — nontrivial but well-trodden.

Given CI runtime cost, don't run this on every commit: run it on every PR into `main` (i.e., every UAT→prod promotion) and on a nightly schedule against `uat`. That catches backend-specific breakage before it reaches either production database, without tripling every PR's CI time.

### Recommendation 3 — Coverage reporting (not yet gating)
Add `coverage` to `requirements-dev.txt`, wrap `make test` to produce a report, and upload it as a CI artifact (or a step summary). Don't set a hard coverage-percentage gate yet — the codebase doesn't have a coverage baseline to gate against. Revisit gating once 2-3 CI runs establish what "normal" looks like.

### Recommendation 4 — Close the direct-coverage gaps, in priority order
1. `memorabilia_extras.py` template tags — pure functions, cheap, high template-usage surface
2. `django_flowbite_widgets` field/widget `compress`/`decompress` round-trip tests
3. `relay.py` direct unit tests for parsing/address-construction edge cases (independent of the webhook view)
4. Delete the dead `pickle`-based `FlickrAlbumWidget`/`ImageGallery` (Finding 5) — a deletion, not a test-writing task

### Recommendation 5 — Narrow E2E/a11y start
Don't build a full E2E suite immediately. Start with Chrome DevTools-driven checks for the two highest-risk interactive flows already identified by the design audit:
- Gallery lightbox keyboard navigation + focus trap (once `plan:ui-audit-2026-08` #127-adjacent work lands)
- Delete-confirmation modal focus management
- A Lighthouse accessibility run against `/`, `collection_detail`, and `collectible_form` as a baseline (the design audit already recommended this same follow-up)

Grow the E2E surface from there as new UI work lands, rather than retrofitting the whole app at once.

### Recommendation 6 — Test suite reorg (low priority, do opportunistically)
Split `tests.py` into `memorabilia/tests/` as described in Finding 6. Pure refactor — bundle it into a quiet week rather than scheduling it urgently.

## Suggested phasing

| Phase | Contents | Why this order |
|---|---|---|
| 1 | Rec. 1 (CI test gate) | Zero value from the other 5 recommendations until tests actually run automatically |
| 2 | Rec. 2 (MySQL/MSSQL parity job) | Directly answers the question this plan was requested to address |
| 3 | Rec. 3 (coverage reporting) + Finding 5 (delete dead pickle code) | Cheap, unblocks informed prioritization of Rec. 4 |
| 4 | Rec. 4 (close direct-coverage gaps) | Now informed by an actual coverage report |
| 5 | Rec. 5 (narrow E2E/a11y) | Sequenced after the UI-audit focus-management issues land, so there's something meaningful to protect |
| 6 | Rec. 6 (test suite reorg) | Opportunistic, no urgency |

## Suggested follow-up

Hand this plan to `/program-manager` to decompose into tracked issues, the same way the UI audit was — Phases 1-3 are small enough to be 1-2 issues each; Phase 2 (the MySQL/MSSQL CI job) is likely the largest single unit and may warrant its own two issues (one per backend) given the ODBC driver installation is a distinct chunk of CI plumbing from the MySQL service container.
