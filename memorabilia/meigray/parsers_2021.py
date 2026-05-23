"""
2021-22 NHL population report (full season; Colorado won SCF vs Tampa --
neither tracked here, so no SCF entries).

Schedule's data shifted by one column vs prior years (team header now at
col 0 instead of col 1; date at col 0 not col 1). detect_col_offset
handles this transparently.

Schedule covers Boston, Columbus, Edmonton, Nashville, New Jersey,
Philadelphia, Seattle (inaugural year), Washington.

Per-year fixups:
  * Edmonton: pop report has Set 3 (33) and Set 4 (25) White entries
    that have no schedule data (no 'End White Set 2/3' markers), and
    we can't disambiguate Set 2 -> 3 -> 4 boundaries. Add the missing-
    source-data note so the Set 3/4 entries register as expected-
    dateless rather than actionable.
  * Per-event date-in-colour sets wired via apply_promo_color_dates
    extras: CBJ - RN, BOS - WO, PHI - LN50, NSH - PR, NSH - SS.

Tag sheet 'POP REPORT BY TAG NUMBER' has TAG # at column offset 0;
ignored 'POP REPORT BY PLAYER'.
"""

import re

from memorabilia.meigray import toolbox
from memorabilia.meigray.registry import (
    SheetManifest,
    YearSpec,
    register,
    sheet,
)

# Per-tag colour overrides for typos / mislabels that defeat the
# schedule lookup. Applied before global GI / flag passes so the
# corrected colour drives those checks.
_COLOR_CORRECTIONS = {
    'U05427': ('Navy Alternate Set 2',
               "Colour in report 'Third Set 2' assumed to be a typo"),
}


# Per-year promo prefixes for one-off events with the date in the colour.
_CBJ_RN_RE = re.compile(r'^CBJ\s*-\s*RN\b', re.IGNORECASE)
_BOS_WO_RE = re.compile(r'^BOS\s*-\s*WO\b', re.IGNORECASE)
_PHI_LN50_RE = re.compile(r'^PHI\s*-\s*LN50\b', re.IGNORECASE)
_NSH_PR_RE = re.compile(r'^NSH\s*-\s*PR\b', re.IGNORECASE)
_NSH_SS_RE = re.compile(r'^NSH\s*-\s*SS\b', re.IGNORECASE)
_PROMO_EXTRAS = {
    _CBJ_RN_RE: 'Rick Nash Retirement Night',
    _BOS_WO_RE: "Willie O'Ree Retirement Night",
    _PHI_LN50_RE: 'Lou Nolan 50 Years',
    _NSH_PR_RE: 'Pekka Rinne Retirement Night',
    _NSH_SS_RE: 'Stadium Series Style',
}

MANIFEST_2021 = SheetManifest(
    tag='POP REPORT BY TAG NUMBER',
    schedule=('SET DATES - JERSEY SCHEDULES',),
    omit=('POP REPORT BY PLAYER',),
)


def build_schedule_2021(wb, actual, manifest, season, tag_teams):
    rows = list(wb[sheet(actual, 'SET DATES - JERSEY SCHEDULES')]
                .iter_rows(values_only=True))
    schedule = toolbox.parse_set_dates_table(rows, season, tag_teams)
    schedule.update(toolbox.parse_pergame_schedule(rows, season, tag_teams))
    return schedule


def _apply_edm_missing_set_note(entries):
    """Edmonton's schedule lacks End markers past Set 1 except for Orange
    Set 2 (3/30). Per project rule, sets without an End marker stay
    dateless:
      * White Set 2 (no End White Set 2 marker)
      * Navy Alternate / Third Set 2 (no End Navy Set 2 marker)
      * Any Set 3 or Set 4 (no markers)
    Orange Set 2 has the End Orange Set 2 marker and stays dated.
    Empty games_worn and add the missing-data note for affected entries
    (skips GI / flag entries which are dateless for other reasons)."""
    note = ('Population report is missing Set boundaries, '
            'cannot determine exact dates for set')
    for e in entries:
        if e.team != 'Edmonton Oilers':
            continue
        if toolbox.is_game_issued(e.color) or toolbox.color_flag_text(e.color):
            continue
        s = str(e.set_number).strip()
        c = e.color.lower()
        clear = False
        if s == '2':
            # Orange Set 2 has End marker -> dated; everything else Set 2
            # missing.
            if 'orange' not in c:
                clear = True
        elif s in ('3', '4'):
            clear = True
        if not clear:
            continue
        e.games_worn = []
        gen = e.notes.setdefault('generated', [])
        if note not in gen:
            gen.append(note)


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


def parse_tags_2021(rows, col, header_idx, headers, league, schedule, season, report):
    from memorabilia.models import MeiGrayEntry
    entries, total = toolbox.parse_entries_color_set(
        rows, col, header_idx, league, schedule, report, MeiGrayEntry
    )
    _apply_color_corrections(entries, schedule)
    toolbox.enrich_vintage(entries, schedule)
    _apply_edm_missing_set_note(entries)
    return entries, total


def corrections_2021(entries):
    toolbox.apply_promo_color_dates(entries, extras=_PROMO_EXTRAS)


SPEC_2021 = YearSpec(
    manifest=MANIFEST_2021,
    build_schedule=build_schedule_2021,
    parse_tags=parse_tags_2021,
    corrections=corrections_2021,
)

register('NHL', '2021-22', SPEC_2021)
