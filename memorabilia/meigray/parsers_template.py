"""
Template for a new year's MeiGray parser. Copy to ``parsers_<startyear>.py``
(e.g. ``parsers_2022.py`` for 2022-23) and fill in the marked sections.

Workflow:
  1. Copy this file -> ``parsers_<YYYY>.py``.
  2. Replace every ``YYYY``/``YYYY-YY`` placeholder with the real year.
  3. Update the module docstring with the year's storyline (teams covered,
     SCF participants, any schedule quirks) and a per-year fixups list.
  4. Inspect the XLSX directly (``openpyxl.load_workbook(...).sheetnames``,
     scan ``SET DATES - JERSEY SCHEDULES`` and ``POP REPORT BY TAG NUMBER``)
     before designing fixes -- DON'T guess from prior years.
  5. Add only the fixups this year actually needs; delete the unused
     scaffolding sections below.
  6. Register the spec at the bottom (``register('NHL', 'YYYY-YY', ...)``)
     and add ``import parsers_YYYY`` to ``memorabilia/meigray/__init__.py``.
  7. Verify: ``make check SETTINGS=dev``, all-year parity (``with_dates`` vs.
     baselines in [[meigray-parser-rewrite]]), ``make test SETTINGS=test``.
  8. Update the baseline list in the memory file once the year is final.

See [[meigray-parsing-rules]] for the worn/dateless semantics and
[[meigray-parser-rewrite]] for the package design. The 2021-22 format is
assumed (per-game schedule with End markers, ``POP REPORT BY TAG NUMBER``
tag sheet at column offset 0, ignored ``POP REPORT BY PLAYER``).
"""

import re

from memorabilia.meigray import toolbox
from memorabilia.meigray.registry import (
    SheetManifest,
    YearSpec,
    register,
    sheet,
)


# ---------------------------------------------------------------------------
# Per-tag colour overrides (typos / mislabels that defeat the schedule lookup)
# Keep this dict empty unless a specific tag has a wrong colour in the report.
# Tag number -> (corrected colour, generated note explaining the override).
# Applied BEFORE the global GI / flag passes so the corrected colour drives
# is_game_issued / color_flag_text.
# ---------------------------------------------------------------------------
_COLOR_CORRECTIONS = {
    # 'U12345': ('Navy Alternate Set 2',
    #            "Colour in report 'Third Set 2' assumed to be a typo"),
}


# ---------------------------------------------------------------------------
# Per-event date-in-colour promo sets (e.g. 'BOS - WO' = Willie O'Ree night).
# Each pattern matches a set_number prefix. The label is recorded as the
# generated note; the date(s) come from the colour string (numeric m/d/yy
# or spelled-out 'Month D, YYYY') via apply_promo_color_dates.
# Add only the codes this year actually has.
# ---------------------------------------------------------------------------
# _XXX_YYY_RE = re.compile(r'^XXX\s*-\s*YYY\b', re.IGNORECASE)
_PROMO_EXTRAS = {
    # _XXX_YYY_RE: 'Descriptive Event Name',
}


# ---------------------------------------------------------------------------
# Sheet manifest. The 2021-22 layout is the going-forward default; only
# touch this if a new sheet appears (then either add to `schedule` if it
# carries dates we need, or to `omit` if it's a sheet to ignore).
# `check_sheets` errors on any unrecognized sheet.
# ---------------------------------------------------------------------------
MANIFEST_YYYY = SheetManifest(
    tag='POP REPORT BY TAG NUMBER',
    schedule=('SET DATES - JERSEY SCHEDULES',),
    omit=('POP REPORT BY PLAYER',),
)


# ---------------------------------------------------------------------------
# build_schedule: parse the schedule sheet into a dict of
# {(team_lower, lane, set_num): [game dicts]} (plus special keys for
# preseason / playoffs / vintage / scf / reverse_retro / etc.).
#
# Default body is enough for most years: range-table fallback then
# per-game schedule (authoritative; overrides ranges). Append per-year
# fixup calls AFTER those two lines (see Heritage / Set-3 split examples
# in parsers_2018.py / parsers_2019.py / parsers_2020.py).
# ---------------------------------------------------------------------------
def build_schedule_YYYY(wb, actual, manifest, season, tag_teams):
    rows = list(wb[sheet(actual, 'SET DATES - JERSEY SCHEDULES')]
                .iter_rows(values_only=True))
    schedule = toolbox.parse_set_dates_table(rows, season, tag_teams)
    schedule.update(toolbox.parse_pergame_schedule(rows, season, tag_teams))
    # _your_per_year_schedule_fixup(schedule)   # e.g. lift Heritage rows out
    return schedule


# ---------------------------------------------------------------------------
# Optional per-year schedule fixups. Examples:
#   * Lift 'heritage' / promo rows out of the team's home Set N bucket
#     (jersey_home_away maps non-white/non-third colours -> 'home').
#   * Re-route playoff games when the schedule lacks a PLAYOFFS header.
#   * Split a set bucket via the opponent-repetition playoff heuristic
#     (toolbox.opponent_repetition_playoff_boundary) for Boston-style
#     missing-marker cases.
# Delete this section if not needed.
# ---------------------------------------------------------------------------
# def _your_per_year_schedule_fixup(schedule):
#     ...


# ---------------------------------------------------------------------------
# Per-tag date assignments. Use only when a tag's Comments identifies a
# specific game that no generic schedule lookup / colour-date extraction
# can resolve (e.g. 'Shirt Off Their Back Night'). Format:
# tag_number -> ((iso_date, ...), generated_note_text).
# Delete if not needed this year.
# ---------------------------------------------------------------------------
_PER_TAG_DATES = {
    # 'T01234': (('2022-05-08',),
    #            'Comment: Shirt Off Their Back Night (5/8/2022)'),
}


# ---------------------------------------------------------------------------
# Per-tag note corrections. Add a generated note to an entry where the
# pop-report data is ambiguous or missing context. Use a 'Population report
# is missing ...' prefix when the year cannot determine dates (the
# orchestrator's dateless_unexpected filter treats that note as
# expected-dateless). Delete if not needed.
# ---------------------------------------------------------------------------
_NOTE_CORRECTIONS = {
    # 'S05432': 'Population report is missing Set 2 boundaries, '
    #           'cannot determine exact dates for set',
}


def _apply_color_corrections(entries, schedule):
    """Per-tag colour overrides + re-lookup of dates. Runs early so the
    corrected colour drives the global GI / flag passes."""
    for e in entries:
        fix = _COLOR_CORRECTIONS.get(e.tag_number)
        if not fix:
            continue
        new_color, note = fix
        e.color = new_color
        set_num = toolbox.parse_set_number(e.set_number)
        if set_num is not None:
            e.games_worn = toolbox.lookup_games(
                schedule, e.team, new_color, set_num, set_raw=e.set_number)
        e.notes.setdefault('generated', []).append(note)


def _apply_per_tag_dates(entries):
    for e in entries:
        fix = _PER_TAG_DATES.get(e.tag_number)
        if not fix:
            continue
        dates, note = fix
        e.games_worn = [{'type': 'worn', 'date': d} for d in dates]
        e.notes.setdefault('generated', []).append(note)


def _apply_note_corrections(entries):
    for e in entries:
        note = _NOTE_CORRECTIONS.get(e.tag_number)
        if not note:
            continue
        gen = e.notes.setdefault('generated', [])
        if note not in gen:
            gen.append(note)


# ---------------------------------------------------------------------------
# parse_tags: the order below is the verified-safe ordering. Add any
# per-year hooks BETWEEN enrich_vintage and the return (so global comment
# extraction / One-Game-Only / Training-Camp / GI clear -- which run in
# __init__._parse AFTER parse_tags returns -- don't fight them).
# Drop the helper calls whose dicts are empty for this year.
# ---------------------------------------------------------------------------
def parse_tags_YYYY(rows, col, header_idx, headers, league, schedule, season, report):
    from memorabilia.models import MeiGrayEntry
    entries, total = toolbox.parse_entries_color_set(
        rows, col, header_idx, league, schedule, report, MeiGrayEntry
    )
    _apply_color_corrections(entries, schedule)
    toolbox.enrich_vintage(entries, schedule)
    _apply_per_tag_dates(entries)
    _apply_note_corrections(entries)
    # _your_per_year_entry_hook(entries, schedule)   # see parsers_2019._apply_phi_set3
    return entries, total


# ---------------------------------------------------------------------------
# corrections: runs LAST (after dedupe). Promo date-in-colour extras live
# here. Drop this function entirely if _PROMO_EXTRAS is empty AND no other
# late-stage fixups apply.
# ---------------------------------------------------------------------------
def corrections_YYYY(entries):
    toolbox.apply_promo_color_dates(entries, extras=_PROMO_EXTRAS)


SPEC_YYYY = YearSpec(
    manifest=MANIFEST_YYYY,
    build_schedule=build_schedule_YYYY,
    parse_tags=parse_tags_YYYY,
    corrections=corrections_YYYY,
)

# Update the season string ('YYYY-YY', e.g. '2022-23'). Don't forget to
# add 'from . import parsers_YYYY' in __init__.py so this register() runs.
register('NHL', 'YYYY-YY', SPEC_YYYY)
