# Plan: Collectible Type Registry, `views.py` Decomposition, Primary-Image DRY Fix

Source: `/code-check` audit (2026-08-09) — SOLID #1 (OCP/DRY: `collectible_type` dispatch duplication), SOLID #2 (SRP: `views.py` god module), DRY #1 (primary-image logic duplicated across `models.py` and `views.py`).

## Why these three together

DRY #1's fix (a model-level `get_images()`/`get_primary_image_obj()` API) directly shrinks two of the SOLID #1 dispatch sites (`CollectibleView.get_context_data`, `collectible_pdf`), and the SOLID #1 registry is the seam the `views.py` split (SOLID #2) should be organized around. Doing them in this order avoids redoing work.

## Verified current state (re-read from source, not taken from audit summary)

- `collectible_type` → model dispatch is hand-copied as `if/elif` at: `views.py:56-65` (`_get_collectible`), `views.py:659-674` (`CollectibleView.get_object`), `views.py:755-778` (`collectible_pdf`), `views.py:1049-1056` (`edit_collectible`), `views.py:1170-1177` (`delete_collectible`).
- `export_import.py:412-430` (`_create_collectible`) has a *different-shaped* dispatch (constructs a new instance with type-specific fields) — not folded into the fetch-registry; only its `ImageModel`/`AuthModel` selection is a candidate for reuse.
- `_get_image_formset_class`/`_get_auth_formset_class` (`views.py:920-935`) are **already** properly centralized and reused — not touched by this plan.
- `Collectible.get_primary_image()` (`models.py:357-362`) and `PlayerGear.get_primary_image()` (`models.py:434-439`) are identical except for the relation name (`images` vs `gear_images`). `HockeyJersey` is a **proxy model of `PlayerGear`** (`Meta.proxy = True`, `models.py:452`), so it inherits `PlayerGear`'s override automatically — no third model-level copy exists.
- The same "primary, else first" logic is reimplemented a 3rd and 4th time in `views.py:698-703` (`CollectibleView.get_context_data`, returns `.image`/`.link`) and `views.py:799` (`collectible_pdf`, needs the image *object*, not just its resolved value, to exclude it from the secondary list).
- `urls.py` imports views only via `from . import views` + `views.<name>` attribute access (`urls.py:2`). `tests.py` never imports view functions directly — all 104 tests go through `self.client.get/post`. This means a `views.py` → `views/` package conversion is invisible to both callers as long as `views/__init__.py` re-exports every public name.

## Phase 1 — Model-level fix (DRY #1) — DONE (2026-08-09)

Implemented as specified below in `models.py`, plus one drive-by fix found during Q&A verification: `generalitem_detail.html` had a dead `{% if object.photomatches.all.count > 0 %}` block and an unconditional `gallery_lightbox.html` include for a `photomatch` gallery — `GeneralItem` has no `photomatches` relation (`PhotoMatch.collectible` is a FK to `PlayerGear` only), so this was inert copy-paste from `playergear_detail.html`/`hockeyjersey_detail.html`. Removed both (lines 69-77 and 81 in the original file). Confirmed via `tests.py:210-219` (`test_generalitem_detail`, pre-existing, asserts HTTP 200) that this was never a crash — Django's template engine silently resolves unknown-attribute lookups to falsy inside `{% if %}` (`VariableDoesNotExist.silent_variable_failure = True`) — just dead markup.

**Verified query counts** (via `assertNumQueries` in the new `CollectiblePrimaryImageTests.test_detail_queryset_prefetches_avoid_extra_queries_on_touch`): `PlayerGear.detail_queryset()`/`HockeyJersey.detail_queryset()` each cost **4 queries** when every prefetched/select_related relation is touched (1 for the object + joins, 1 each for the three independent prefetch groups: `gear_images`, `authentications`, `photomatches`). This confirms the Phase 2 concern about the `HockeyJersey`/`PlayerGear` prefetch union was unfounded as a regression risk — `photomatches` was already being lazily queried by the templates (`playergear_detail.html:79-84`, `hockeyjersey_detail.html:175-180`) before this change, so making it an explicit prefetch doesn't add a query, it just makes an existing one deliberate.

Tests added: `memorabilia/tests.py` `CollectiblePrimaryImageTests` (9 tests covering `get_images()`/`get_primary_image_obj()`/`get_primary_image()` across all 4 types including proxy-model inheritance for `HockeyJersey`, plus `detail_queryset()` correctness and query-count regression guards). Full suite: 377 tests, `OK`. `make check` clean.

---

## Phase 1 spec (as originally planned, for reference)

**File: `memorabilia/models.py`**

1. On `Collectible` (abstract base, ~line 300): add `image_relation_name = 'images'` class attribute.
2. On `PlayerGearItem` (abstract base, ~line 402): override `image_relation_name = 'gear_images'`.
3. Replace `Collectible.get_primary_image()` (357-362) with:
   ```python
   def get_images(self):
       return list(getattr(self, self.image_relation_name).all())

   def get_primary_image_obj(self):
       images = self.get_images()
       return next((img for img in images if img.primary), images[0] if images else None)

   def get_primary_image(self):
       obj = self.get_primary_image_obj()
       if obj is None:
           return None
       return obj.image if obj.image else obj.link
   ```
4. Delete `PlayerGear.get_primary_image()` (434-439) entirely — it's now inherited and correct via `image_relation_name`.
5. Add a `detail_queryset()` classmethod to each concrete model, moving the select/prefetch lists that currently live inline in `CollectibleView.get_object` and `collectible_pdf`:
   - `PlayerItem.detail_queryset()` → `cls.objects.prefetch_related('images', 'authentications__auth_type', 'authentications__issuer')`
   - `GeneralItem.detail_queryset()` → same shape as `PlayerItem`'s
   - `PlayerGear.detail_queryset()` → `cls.objects.select_related('game_type', 'usage_type', 'gear_type').prefetch_related('gear_images', 'authentications__auth_type', 'authentications__issuer')`
   - `HockeyJersey.detail_queryset()` → override, adds `season_set` to `select_related` and `photomatches` to `prefetch_related` (union of what `CollectibleView` and `collectible_pdf` each needed separately — verify no view regresses from the union; it's strictly a superset, so it can't under-fetch)
6. At the bottom of `models.py`, after all four concrete classes are defined:
   ```python
   COLLECTIBLE_MODELS = {
       'playeritem': PlayerItem,
       'generalitem': GeneralItem,
       'playergear': PlayerGear,
       'hockeyjersey': HockeyJersey,
   }
   ```

**Tests first** (per `testing` skill): add regression tests to `memorabilia/tests.py` before touching `models.py`:
- `PlayerGear`/`HockeyJersey`/`PlayerItem`/`GeneralItem` each: no images → `get_primary_image()` is `None`; one non-primary image → returns it; one image flagged `primary=True` among several → returns that one, not the first. Parametrize across all 4 types so `HockeyJersey`'s proxy inheritance is exercised, not assumed.
- `get_images()` returns the correct relation per type (assert on the *manager* used, e.g. via `assertQuerysetEqual` against `gear_images.all()` for gear types).

**Done when**: new tests fail on current code (proving they exercise the real logic), pass after the change, and the full suite (`make test SETTINGS=test`) is still green.

## Phase 2 — Collapse dispatch sites onto the registry (SOLID #1) — DONE (2026-08-09)

Implemented exactly as specified below in `views.py`: all 5 dispatch sites now read `COLLECTIBLE_MODELS` (imported from `.models`) instead of hand-written `if/elif` chains. Net: `views.py` shrank by 51 lines (89 changed: 19 insertions, 70 deletions), touching only the 5 call sites — no unrelated changes.

**Tests added before refactoring** (characterization tests locking in true current behavior, per "tests first"): `Collectible404Tests` gained `hockeyjersey` 404 coverage and an unrecognized-`collectible_type` 404 case for `CollectibleView`; a new `CollectiblePdfTests` class (`collectible_pdf` had **zero** prior test coverage — added 8 tests: 200 for owner across all 4 types, 404 for bad pk, 404 for unrecognized type, 403 for non-owner, 302 for anonymous); a new `CollectibleDispatchFallbackTests` for `delete_collectible`'s fallback-to-`PlayerItem` behavior on an unrecognized type.

**Bug found via characterization testing — fixed as a follow-up (2026-08-09)**: writing the equivalent test for `edit_collectible` revealed it did not degrade gracefully for an unrecognized `collectible_type` — it 500'd. Root cause: `_get_auth_formset_class()`'s catch-all defaulted to `GeneralItemAuthenticationFormSet`, disagreeing with every sibling default in this dispatch family (`_get_image_formset_class`'s catch-all → `CollectibleImageFormSet`, bound to `PlayerItem`; `COLLECTIBLE_MODELS.get(ctype, PlayerItem)` → `PlayerItem`). Building the `GeneralItem`-bound formset against the `PlayerItem` instance the collectible-fetch had produced raised `ValueError: Cannot query "...": Must be "GeneralItem" instance.`.

Fix (`views.py`, `_get_auth_formset_class`): added an explicit `('generalitem', 'GeneralItem')` branch, then changed the catch-all from `GeneralItemAuthenticationFormSet` to `PlayerItemAuthenticationFormSet`. The explicit branch was required, not optional — `'generalitem'` had no dedicated branch before this fix and was *itself* reaching the correct formset only via that same catch-all, so naively swapping the catch-all's target without adding the branch would have silently broken real `GeneralItem` edits (a 500 for every `generalitem` edit) while fixing the bogus-type case. Caught by writing `test_edit_collectible_generalitem_still_uses_generalitem_auth_formset` as a regression guard before making the change.

Tests: `test_edit_collectible_unrecognized_type_falls_back_to_playeritem_without_crashing` (red on unfixed code — reproduced the exact `ValueError` — green after the fix) and the `generalitem` guard above (green throughout, proving the fix didn't regress the real case). Full suite: 391 tests, `OK`. `make check` clean.

**Verification**:
- Full suite: 389 tests (was 377 after Phase 1; +12 new), `OK`. `make check` clean.
- **Live dev-server smoke test** (not just the test client): started `manage.py runserver`, authenticated via a real Django session (the login page only offers Discord/Facebook OAuth, no password form, so a session was created directly via `SessionStore` — equivalent to what a real OAuth login would produce), created one throwaway item of each of the 4 types plus a throwaway superuser, and drove all 5 endpoints (`detail`, `edit`, `pdf`, plus the two unrecognized-type edge cases) over real HTTP against the running server. All 16 checks passed, including confirming `collectible_pdf` produces real, non-trivial PDF bytes (8.5–12.3 KB) for all 4 types via WeasyPrint. All throwaway data (user, collection, 4 collectibles, images, session) was deleted afterward — verified the dev database's real data (3 users, 2 collections) was untouched.

---

## Phase 2 spec (as originally planned, for reference)

**File: `memorabilia/views.py`**, using `COLLECTIBLE_MODELS` and the new `detail_queryset()` methods from Phase 1:

1. `_get_collectible` (56-65) →
   ```python
   def _get_collectible(request, **view_kwargs):
       collectible_id = view_kwargs['collectible_id']
       collectible_type = view_kwargs.get('collectible_type', 'playeritem')
       Model = COLLECTIBLE_MODELS.get(collectible_type, PlayerItem)
       return get_object_or_404(Model, pk=collectible_id)
   ```
2. `edit_collectible` (1049-1056) and `delete_collectible` (1170-1177): same `Model = COLLECTIBLE_MODELS.get(collectible_type, PlayerItem)` one-liner replacing the 8-line if/elif in each.
3. `CollectibleView.get_object` (653-674): 
   ```python
   def get_object(self, queryset=None):
       pk = self.kwargs.get('pk')
       collection_id = self.kwargs.get('collection_id')
       collectible_type = self.kwargs.get('collectible_type')
       Model = COLLECTIBLE_MODELS.get(collectible_type)
       if Model is None:
           raise Http404("Collectible not found")
       return get_object_or_404(Model.detail_queryset(), pk=pk, collection_id=collection_id)
   ```
   Note this changes silent-fallback behavior for an unrecognized type from "falls through to `Http404` anyway" (current code already does this — the existing `raise Http404` at line 674 was the fallthrough) to the same outcome via the registry — **verify this is truly behavior-preserving** by running `CollectiblePermissionTests`/`Collectible404Tests` before and after.
4. `collectible_pdf` (750-799): replace the four-branch `if/elif` building `collectible`/`images`/`photomatches` with `Model = COLLECTIBLE_MODELS.get(collectible_type); if Model is None: raise Http404(...); collectible = get_object_or_404(Model.detail_queryset(), pk=pk, collection_id=collection_id); images = collectible.get_images(); photomatches = list(collectible.photomatches.all()) if hasattr(collectible, 'photomatches') else []`, and replace line 799's manual primary-pick with `primary = collectible.get_primary_image_obj()`.
5. `CollectibleView.get_context_data` (698-703): replace the 6-line block with `context['primary_image'] = collectible.get_primary_image()`.
6. **Explicitly out of scope for this phase**: `export_import.py:412-430`'s `_create_collectible` — its dispatch builds a *new* instance with type-specific constructor kwargs, which is genuinely different logic per type, not a duplicate of the fetch-dispatch. Leave it as-is; do not force it onto `COLLECTIBLE_MODELS` beyond what it already does correctly.

**Tests first**: before editing, confirm `CollectiblePermissionTests`, `Collectible404Tests`, and `CollectibleDetailContextTests` (existing, per project memory) cover every one of the 4 types × the 5 call sites above. Add any missing combination (e.g. a 404 test for `collectible_pdf` with a bad `collectible_type`) before refactoring, so a regression fails loudly.

**Done when**: same test classes pass unchanged, `git diff --stat` shows only the 5 dispatch sites shrank, and manual smoke test (via `/run` or dev server) of viewing/editing/deleting/exporting-PDF for one item of each of the 4 types still works.

## Phase 3 — Split `views.py` into a package (SOLID #2) — DONE (2026-08-09)

Implemented via AST-based extraction rather than manual cut-and-paste: parsed `views.py` with Python's `ast` module to get exact line ranges for every top-level `def`/`class`/module-level constant (78 nodes), assigned each to one of the 8 planned modules, and reassembled with hand-written import headers verified mechanically with `pyflakes` (not by manual tracing) before ever touching the real file. This caught two things manual extraction would likely have missed:
- The AST walk only collects `FunctionDef`/`ClassDef`/`Assign` nodes by design, so two module-level aliased imports (`import os as _os`, `import tempfile as _tempfile` at the old `views.py:1694-1695`) fell through silently. Caught by `pyflakes` reporting `undefined name '_os'`/`'_tempfile'` in the reassembled `import_export.py`; fixed by dropping the aliases (`os`/`tempfile` directly), consistent with the `json`/`_json` alias cleanup below.
- `wantlist.py`'s `.models` import list initially included `Collection`, `GeneralItem`, `HockeyJersey`, `PlayerGear`, `PlayerItem` — all false positives from a plain-text symbol scan matching string *literals* (e.g. `'PlayerItem'` as a display-label value in a dict), not real code references. `pyflakes`'s AST-based unused-import check correctly flagged and these were removed.

**Also completed per the original Phase 3 spec**: fixed the duplicate `json`/`_json` import alias (`views.py:2,49,1527` in the original) — every module now does a single plain `import json`; the local `import json as _json` inside `bulk_add_flickr_album` was dropped entirely once its call sites were repointed to the shared `json`. The dead imports the `/code-check` audit flagged (`CoaType`, `OwnerInquiry`, `CollectibleForm`, `GeneralItemForm`, `PlayerGearForm`, plus `HockeyJerseyForm`/`reverse` that turned out unused in specific submodules) naturally fell away since each submodule now only imports what it actually uses — verified by a clean `pyflakes` pass on all 9 files.

**One deviation from the plan's size estimate, disclosed rather than silently accepted**: the "each under ~450 lines" target in the original spec was a rough guess. Actual sizes: `core.py` 128, `collections.py` 117, `webhooks.py` 36, `import_export.py` 179, `flickr.py` 316, `search.py` 350, `wantlist.py` 526, **`collectibles.py` 721**. `collectibles.py` (detail view, PDF export, create/edit/delete, bulk-edit, photo-match CRUD) is the single largest functional cluster in the original file and came out roughly 1.6x the estimate. It's still a single coherent responsibility (individual + bulk collectible CRUD) and a large improvement over one 2326-line file, but it did not hit the original size target. Splitting it further (e.g. carving `bulk_edit_collectibles` and its conversion helpers into their own module) was not in the approved plan's module list, so it was not done here — left as a candidate for a future, separately-scoped follow-up rather than an unrequested deviation.

**Verification**:
- `pyflakes` clean on all 9 new files (the only residual warnings are the inherent, expected `import *` noise in `__init__.py` and one pre-existing cosmetic `f-string is missing placeholders` in `wantlist.py` that existed in the original file — left untouched, out of scope for a pure code-motion phase).
- `python -c "from memorabilia import views; views.home; views.CollectibleView; views.want_list_import; views.mailgun_inbound"` — resolves correctly, confirming `urls.py`'s `from . import views; views.X` pattern needs zero changes.
- Full suite: 391 tests, `OK` (unchanged from before this phase — pure code motion, no behavior change expected or observed). `make check` clean.
- Grepped `templates/` and `memorabilia/templates/` for `views\.` — zero matches, confirming no template depends on view module paths.
- `git diff --stat`: `views.py` (2377 lines) replaced by 9 files totaling 2381 lines across the package — net near-zero line change, as expected for a pure move plus the disclosed cleanups above.
- No live dev-server re-run for this phase: Phase 2's live smoke test already validated runtime rendering end-to-end for all 4 collectible types, and this phase changes no logic, only file/import layout — the full test suite plus the direct `views.X` resolution check cover the actual risk surface (import wiring, URL resolution) for a pure code-motion change.

Only start this once Phases 1–2 are merged — splitting a file mid-refactor multiplies diff noise and review risk for no benefit.

1. Convert `memorabilia/views.py` into `memorabilia/views/` with:
   - `views/__init__.py` — re-exports every public name referenced by `urls.py`, `admin.py`, or templates (`from .core import *`, etc.) so `from . import views; views.home` keeps working with zero changes to `urls.py`.
   - `views/core.py` — `home`, `home_recent`, `privacy_policy`, `data_deletion`, `profile`, `IndexView`, `MyCollectionsView`, `UserCollectionsView`, `_get_collectible`, `_has_image_q`, `_user_want_list_url`, `_collectible_trade_url`, `_FEATURED_Q`
   - `views/search.py` — `_model_has_field`, `_apply_collectible_filters`, `search_collectibles`, `marketplace`, `_resolve_interest`, `contact_owner`, `get_teams`
   - `views/collections.py` — `create_collection`, `edit_collection`, `delete_collection`, `CollectionView`, `_get_all_collage_images`, `ExternalResourceListView`
   - `views/collectibles.py` — `_collectible_script_src`, `CollectibleView`, `collectible_pdf`, `create_collectible`, `_get_image_formset_class`, `_get_auth_formset_class`, `_update_collage_after_conversion`, `_convert_bulk_item`, `_copy_images`, `edit_collectible`, `delete_collectible`, `PhotoMatchView`, `create_photo_match`, `edit_photo_match`, `delete_photo_match`, `bulk_edit_collectibles`
   - `views/flickr.py` — `get_flickr_albums`, `get_flickr_user_albums`, `get_flickr_album_photo_ids`, `bulk_add_from_flickr`, `bulk_add_flickr_album`, `bulk_add_flickr_batch`, `_process_albums_background`, `_import_flickr_album_photos`, `get_flickr_album`
   - `views/import_export.py` — `_safe_filename`, `export_collectible`, `export_collection`, `download_population_report`, `import_upload`, `import_preview` (named to avoid colliding with the existing top-level `memorabilia/export_import.py` module)
   - `views/wantlist.py` — all `want_list_*`/`_want_list_*` functions (2002–2377 in current file)
   - `views/webhooks.py` — `mailgun_inbound`
2. Each submodule imports only what it needs from `.models`, `.forms`, `.relay` (no more one 40-line shared import block) — this is where the currently-dead imports (`CoaType`, `OwnerInquiry`, `CollectibleForm`, `GeneralItemForm`, `PlayerGearForm` in the old `views.py:13-30`, per the dead-code audit) naturally fall away instead of being carried into every submodule.
3. Fix the duplicate `json`/`_json` import (`views.py:2,49,1527`) while moving code — pick `json` everywhere.
4. Move `Q(allow_featured=True) | ...` (`_FEATURED_Q`, line 70) and any other cross-cutting module-level constant used by more than one submodule into `views/core.py` and import it explicitly where needed (no wildcard re-exports between submodules, only `__init__.py` → submodule).

**Migration mechanics to keep this safe**:
- Do the split as a pure move (no logic changes) — a dedicated commit per submodule extraction, each followed by `make test SETTINGS=test`.
- After all submodules exist, run `python -c "from memorabilia import views; views.home"` (or equivalent Makefile target) plus the full suite once more, then `make check` (Django system checks catch broken URL resolution).
- Grep for `views\.` across `templates/` (some templates may reference `request.resolver_match` or similar, unlikely to matter, but confirm no template does `{% url %}` lookups that depend on view module paths rather than URL names — Django `{% url %}` uses URL names, not import paths, so this should be a non-issue, but verify by grepping).

**Done when**: `views.py` no longer exists, `views/` package exists with 8 focused submodules each under ~450 lines, full test suite green, `make check` clean, and `git diff` for this phase touches no behavior — only file locations and import lists.

## Sequencing & risk notes

- Each phase is an independently mergeable PR per `core-directives.md` Rule (trunk-based, no stacked chains) — branch each off `main` in order, since Phase 2 depends on Phase 1's model methods and Phase 3 depends on Phase 2's registry existing.
- Highest-risk step is Phase 2 step 3 (`CollectibleView.get_object`'s fallback path) and the `HockeyJersey.detail_queryset()` union in Phase 1 step 5 — both touch permission-gated detail views. Run `CollectiblePermissionTests` and `Collectible404Tests` explicitly (not just the full suite) after each, and eyeball the diff.
- No database migration is required — all changes are Python-level (methods, dict, module layout), no model field changes.
- Out of scope (tracked separately, not part of this plan): `export_import.py`'s construction-dispatch, the `bulk_edit_collectibles`/`edit_collectible` long-method complexity findings, the auth-decorator (403 vs 404) consistency finding, and all Low-severity dead-code/logging cleanup — those were separate line items in the `/code-check` report and don't block or get blocked by this plan.

## Handoff

Ready for `/builder` to implement phase-by-phase (or `/swarm-execute` if parallelizing Phase 3's submodule extractions across workers once Phase 1–2 are merged — each submodule extraction is independent of the others once the shared import list is settled). After each phase: `/swarm-review` before merge.
