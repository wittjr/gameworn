# UI/UX Audit — Gameworn Frontend

**Type:** Design Audit (static code review, no live DevTools/Lighthouse pass)
**Scope:** `memorabilia/templates/`, `templates/`, `theme/`, associated CSS
**Date:** 2026-08-15
**Author:** `/ui-ux-designer`

## Method note

This audit is a static read-through of every template and stylesheet in the repo, looking for design-system inconsistency, accessibility gaps, dead/legacy code, and modernization opportunities. It does not include the full `/ui-ux-designer` deliverable set (four-breakpoint screenshots + Lighthouse report) — those apply to *new* component work per `core-directives.md` Rule 6 ("ceremony scales with scope"); a codebase-wide audit isn't a spec for a component that doesn't exist yet. Recommend running the Lighthouse/DevTools pass from this skill against `/`, a collection detail page, and the collectible form as a fast follow-up — flagged as a to-do at the end.

---

## Summary

The app has a real design system (Flowbite + Tailwind, a `.btn-primary` / `.btn-primary-white` / `.btn-primary-red` component layer, consistent `dark:` variants on most newer pages, thoughtful accessibility fixes already landed on the collectible form — `aria-describedby` wiring, focus-visible rings, keyboard-navigable lightbox). The gaps are concentrated in a handful of older pages that predate the Tailwind/Flowbite migration and never got fully converted, plus some dead files left behind by that migration.

**11 findings**, roughly: 2 dead-code, 3 dark-mode/consistency gaps, 3 duplicated-pattern (DRY) issues, 3 accessibility/modernization gaps.

---

## Findings

### 1. Dead legacy stylesheet — `memorabilia/static/memorabilia/style.css`
**Severity: Medium (cleanup)**

Nothing references this file (verified via repo-wide grep). It defines a completely different, pre-Tailwind design language — `font-family: Cabin`, a red `#CE1126` header/footer, fixed `img { width: 250px }`. Keeping it around risks someone re-linking it by habit and silently reintroducing the old look.

**Fix:** Delete `memorabilia/static/memorabilia/style.css`.

### 2. Dead scaffold template — `theme/templates/base.html`
**Severity: Low (cleanup)**

This is the unmodified `django-tailwind` starter template ("Django + Tailwind = ❤️", `font-serif`). It's never extended by any view — `memorabilia/templates/memorabilia/base.html` is the real base template. It only survives because `theme` is a Django app with its own `templates/` dir.

**Fix:** Delete, or replace with a comment noting it's intentionally unused if `django-tailwind` requires the file to exist for tooling reasons (check before deleting).

### 3. `dark:` coverage is inconsistent across pages
**Severity: High (visible breakage)**

Tailwind's `darkMode` is left at its default (`media` strategy — no `darkMode: 'class'` in `tailwind.config.js`, no toggle button anywhere in the UI). That means **any user whose OS is in dark mode gets dark-mode styling automatically, whether the page supports it or not.** Five templates have zero `dark:` classes:

- `collection_detail.html` (memorabilia/templates/memorabilia/collection_detail.html) — the collection hero + 7-button action bar + tooltips
- `image_form.html`
- `flickr_bulk_add.html`
- `photomatch_detail.html`
- `collectible_pdf.html` (this one's fine to exempt — it's a print/PDF template, not a browser view)

On the first four, a dark-mode OS user gets Tailwind's dark `<body>`/nav chrome wrapped around a form or action bar still rendering white cards, gray-700 text on a near-black background, unstyled borders — the classic "half dark mode" bug.

**Fix:** Either (a) add `dark:` variants to the four remaining browser-facing templates to match the rest of the app, or (b) pin `darkMode: 'class'` and ship an explicit toggle so dark mode is opt-in and testable, rather than silently applied per-OS with partial coverage. Given ~43 of 48 templates already carry `dark:` classes, (a) is less work; (b) is the more "modern experience" answer since most production apps now default to system preference *plus* a manual override (see #9).

### 4. Two competing layout systems: hand-written CSS vs. Tailwind utilities
**Severity: Medium (consistency)**

`collection.css` and `collection-detail.css` are hand-rolled, non-Tailwind stylesheets (flexbox by raw CSS, nested selectors, `.collection-card` with fixed `max-width: 400px`/`min-width: 200px`) still wired in via `{% block page_css %}` on `collection_list.html` and `collection_detail.html`. Every other "grid of cards" page (`marketplace.html`, `search.html`, `collectible_detail.html`'s photomatch grid) uses plain Tailwind utility classes (`flex flex-wrap gap-4 justify-evenly` or `grid grid-cols-*`) with no separate stylesheet.

Concretely: `collection_card.html` renders at a fixed `w-96` with no responsive breakpoints, while the near-identical `collectible_card.html` is fully responsive (`w-full md:w-2/5 xl:w-1/4`). Two cards that should look and behave like siblings currently don't.

**Fix:** Port `collection_list.html`/`collection_detail.html` to the same Tailwind grid/flex pattern the rest of the app uses, and give `collection_card.html` the same responsive width treatment as `collectible_card.html`. Then delete `collection.css` and `collection-detail.css`.

### 5. FontAwesome icon syntax is split between v5 and v6 class names
**Severity: Low-Medium (could silently render missing icons)**

`externalresource_card.html` and `externalresource_list.html` use the old `fas fa-globe` / `fas fa-external-link-alt` syntax, while `photomatch_card.html` and `tablerow.html` use the current `fa-solid fa-user-pen` / `fa-solid fa-check` syntax. Both currently render because the FontAwesome kit script (loaded via `kit.fontawesome.com`, `memorabilia/templates/memorabilia/base.html:18`) ships backward-compat shims, but that's relying on an external, unversioned, unpinned kit script to keep bridging two syntaxes forever — a future kit config change breaks half the icons in the app with no compile-time warning.

**Fix:** Standardize on `fa-solid`/`fa-regular`/`fa-brands` (current FA6 syntax) everywhere; update the two `fas` occurrences.

### 6. Filter-form pattern duplicated verbatim between `search.html` and `marketplace.html`
**Severity: Medium (DRY / maintainability)**

Both pages hand-roll the same label/input grid (`<label class="block mb-1 text-sm font-medium text-gray-700">` repeated per field, `bg-white rounded-lg shadow p-4` form container, league/team datalist wiring, near-identical `<script>` blocks for team autocomplete). Per `.claude/rules/code-quality.md`'s DRY guidance, this is knowledge duplication, not incidental — the two forms represent the same UI concept (collectible filters) and will drift if one is updated and not the other. Notably, both also **missed the `dark:` pass**: every filter label is `text-gray-700` with no dark variant, and the "Clear" link is a one-off `border-gray-300` button that doesn't match `.btn-primary-white`.

**Fix:** Extract a shared `_filter_field.html` partial (label + input + optional datalist) and reuse it in both templates; add `dark:text-gray-300` to labels; replace the bespoke "Clear" button with `.btn-primary-white` for consistency.

### 7. Table markup vs. div-grid markup for the same "label/value row" concept
**Severity: Low-Medium (consistency, but also a completed-vs-incomplete signal)**

`collectible_form.html` has an inline comment "Fix 13: div-based layout replacing table/tr/th/td" — someone already migrated the *form* away from table markup for better small-screen wrapping and semantics. `collectible_detail.html`, the read-only counterpart showing the same fields, still renders a `<table>` via `tablerow.html` (`<tr>`/`<th scope="row">`/`<td>`). This isn't wrong markup (a real data table with a header column is legitimate use of `<table>`), but it means the same field list has two different visual/interaction models depending on whether you're viewing or editing — the detail page's table also doesn't reflow on mobile as gracefully as the form's flex-col rows.

**Fix:** Low priority — not broken, just inconsistent. Worth revisiting only if the detail page's mobile table overflow (`overflow-x-auto` currently masks this) becomes a reported complaint.

### 8. 7-button, ungrouped action bar on `collection_detail.html`
**Severity: Medium (modernization / IA)**

The owner-only action bar renders seven top-level buttons (Delete, Import Items, Add from Flickr, Export Collection, Edit All Collectibles, Edit Collection, Create Collectible) each with its own Flowbite tooltip, all `flex-wrap`ped together (`memorabilia/templates/memorabilia/collection_detail.html:16-58`). On mobile this wraps to 3-4 rows of buttons above the fold, before the user sees any actual content. It's also the only page in the app with this many peer-level actions — every other page has at most 2-3.

**Fix (modernization suggestion):** Group into a primary action (`Create Collectible`, kept prominent) plus a "More actions" Flowbite dropdown for Import/Flickr/Export/Bulk Edit/Edit/Delete. This is the single highest-leverage "modern experience" change in the audit — it's the busiest screen in the app and currently reads as a toolbar dump rather than a designed hierarchy.

### 9. No manual dark-mode toggle
**Severity: Low (modernization)**

Related to #3: dark mode is fully OS-driven with no in-app override. Users on a dark-mode OS who prefer light (or vice versa) have no way to choose. This is now a baseline expectation for "modern" web apps.

**Fix:** Add a toggle (sun/moon icon in the nav, next to the avatar menu) that sets `localStorage` + toggles a `dark` class on `<html>`, and switch `tailwind.config.js` to `darkMode: 'class'`. This also resolves #3 more durably than chasing missing `dark:` classes page-by-page, since class-strategy dark mode is opt-in per user rather than ambient per OS.

### 10. Lightbox and delete-confirm modal don't manage focus
**Severity: Medium (accessibility — WCAG 2.4.3 Focus Order)**

Both `elements/gallery_lightbox.html` and the global delete-confirmation modal (`memorabilia/templates/memorabilia/base.html:255-314`) are well-built for a hand-rolled dialog — `aria-modal`, `role="dialog"`, Escape-to-close, click-outside-to-close, keyboard arrow nav on the lightbox. What's missing in both: focus isn't moved into the dialog on open (keyboard/screen-reader users opening a lightbox via Enter stay focused on the thumbnail behind it), Tab isn't trapped inside the dialog (a keyboard user can Tab out to page content hidden behind the black overlay), and focus isn't restored to the trigger element on close.

**Fix:** On open, call `.focus()` on the close button (or the dialog container with `tabindex="-1"`); on Tab/Shift+Tab, cycle within the dialog's focusable elements; on close, return focus to the element that opened it (`document.activeElement` captured at open time). This is a contained, ~20-line addition to each script block, not a rewrite.

### 11. FontAwesome kit script loads without CSP nonce or SRI
**Severity: Low (security/consistency, not urgent)**

Every other inline `<script>` in `base.html` carries `nonce="{{ request.csp_nonce }}"` per the CSP setup (`gameworn/settings.py`), and the Flowbite CDN script is pinned to `2.5.1`. The FontAwesome kit script (`memorabilia/templates/memorabilia/base.html:18`) is neither pinned to a version nor covered by a nonce (kit scripts are external, so nonce doesn't apply to the tag itself, but it does inject further script/style at runtime that CSP has to separately allow — confirmed `font-src` already allowlists `ka-f.fontawesome.com` for this reason). Not a bug today, but worth knowing this is the one script tag in the page that isn't self-hosted-or-pinned like its neighbors, and every FA icon syntax change silently rides on whatever the kit account is configured to serve.

**Fix:** Low priority. If a future audit wants FA fully self-hosted (removing the kit's non-nonce script), swap for the `@fortawesome/fontawesome-free` npm package built through the existing Tailwind pipeline — a larger change, only worth it alongside #5's syntax cleanup.

---

## Prioritized action list

| # | Finding | Effort | Impact |
|---|---------|--------|--------|
| 3 | Fix missing `dark:` on 4 templates (or ship class-based toggle, see #9) | Medium | High — visibly broken today for dark-mode-OS users |
| 8 | Group `collection_detail.html` action bar into primary + dropdown | Medium | High — busiest screen in the app |
| 10 | Focus management on lightbox + delete modal | Small | Medium — real a11y gap, contained fix |
| 6 | Extract shared filter-field partial (search + marketplace) | Small | Medium — stops future drift |
| 4 | Migrate `collection_list`/`collection_detail` off hand-written CSS | Medium | Medium — visual consistency |
| 1, 2 | Delete dead `style.css` and unused `theme/templates/base.html` | Trivial | Low risk, removes a footgun |
| 5 | Standardize FA icon syntax to `fa-solid`/`fa-brands` | Trivial | Low, prevents future breakage |
| 9 | Manual dark-mode toggle | Medium | Modernization, pairs with #3 |
| 7 | Table vs. div markup on detail vs. form | — | Deprioritized, not broken |
| 11 | FA kit script pinning | — | Deprioritized |

## Suggested follow-up

Run the full `/ui-ux-designer` DevTools workflow (Lighthouse + 320/768/1024/1440 screenshots) against `/`, `collection_detail`, and `collectible_form` once #3 and #8 land — those are the two changes most likely to move the accessibility/mobile-usability score.
