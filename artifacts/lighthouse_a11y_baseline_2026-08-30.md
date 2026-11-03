# Lighthouse Accessibility Baseline — 2026-08-30

**Type:** E2E/a11y baseline (Recommendation 5, `artifacts/plan_testing_strategy.md`)
**Issue:** #137
**Scope:** Baseline capture only — no CI gate implied or added.

## Method

- Chrome DevTools MCP `lighthouse_audit`, `mode: navigation`, `device: desktop`, against a local `make run` dev server (SQLite, seeded dev data).
- `collectible_form` requires an authenticated, collection-owning session (`create_collectible` is `@login_required` + object-permission-gated). The app is `SOCIALACCOUNT_ONLY` (Discord/Facebook OAuth only, no password login), so a Django session was created directly via `SessionStore` for the existing dev user (`wittjr`, owner of collection 13) and injected into the browser as a cookie; the session was deleted immediately after the audits.
- Raw Lighthouse JSON + HTML reports are saved alongside this file in `artifacts/lighthouse_baseline_2026-08-30/`.

## Known noise in this baseline

Django Debug Toolbar (dev-only, `DEBUG=True`, never present in `pa`/prod settings) renders ~13 hidden checkbox inputs into every page's DOM. Lighthouse's `target-size` audit flags all of them as insufficient touch-target size on **every** page below, dragging each score down by the same fixed amount. This is not an app defect — a future comparison run should either strip the toolbar (attempted here; doing so via `dev_settings.py` mid-session tripped the autoreloader and briefly took the dev server down, so it was reverted rather than risk destabilizing a shared dev process) or simply diff the non-`target-size` findings.

## Results

| Page | URL | Accessibility Score | Failed audits | Non-toolbar findings |
|---|---|---|---|---|
| Homepage | `/` | **96** | 5 | `target-size` only (toolbar noise) |
| Collection detail | `/collection/13/` | **96** | 5 | `target-size` only (toolbar noise) |
| Collectible form | `/collection/13/collectible/create` | **91** | 6 | `target-size` (toolbar noise) + `color-contrast` |

### Real (non-toolbar) accessibility finding

**`collectible_form` — `color-contrast`** (weight 7, 1 node)
Insufficient contrast on:
```html
<div id="step2-indicator" class="flex items-center gap-2 text-gray-400">
```
The inactive-step indicator's `text-gray-400` on its background doesn't meet WCAG AA contrast. Worth a follow-up fix (not required by this issue — baseline only).

## Re-running this baseline

To detect regression in a future PR:
1. `make run` (dev server).
2. Chrome DevTools MCP: navigate to each URL above and run `lighthouse_audit` (`mode: navigation`, `device: desktop`). For `collectible_form`, authenticate first (either a real login, or the `SessionStore` injection technique described above against a dev user that owns a collection).
3. Compare category score and the audit list against this file — ignore `target-size` deltas that are entirely toolbar checkboxes; treat any *new* failing audit, or any `target-size` node that isn't a `djdt*` checkbox, as a real regression.
