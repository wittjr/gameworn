"""
2020-21 NHL population report (COVID-shortened 56-game season, divisional
play, no fans most of year; Tampa Bay won SCF vs Montreal -- neither
tracked here, so no SCF entries).

Same single-column per-game schedule as 2019-20 (no preseason this year
due to COVID; the schedule starts directly with REGULAR SEASON).

Schedule covers Boston, Columbus, Edmonton, Nashville, New Jersey,
Philadelphia, Washington.

Per-year fixups:
  * Edmonton has pop-report Set 3 entries for White (12) and Navy (10)
    -- these are playoff-only jerseys separate from Set 2. The schedule
    has a PLAYOFFS section header so the toolbox playoffs key holds
    Edmonton's 4 playoff games (2 home Navy, 2 away White); move those
    to Set 3 and strip from Set 2.

Toolbox handles Reverse Retro (2020-21+) via the 'reverse_retro' key.
"""

from memorabilia.meigray import toolbox
from memorabilia.meigray.registry import (
    SheetManifest,
    YearSpec,
    register,
    sheet,
)

# Nashville 4 'Promotional Game - Player Set' dates per the schedule's
# note column. The Gold dates (5/8, 5/10) are also encoded in the PROMO
# Gold tags' colours so apply_promo_color_dates already excludes them
# from non-PROMO entries -- but the White dates (5/3, 5/5) are NOT in
# the PROMO White colour ('White - Promotional Game'), so we have to
# strip them from the schedule and assign manually.
_NSH_PROMO_PLAYER_SET = {
    'away': ('2021-05-03', '2021-05-05'),
    'home': ('2021-05-08', '2021-05-10'),
}
_NSH_PROMO_WHITE_DATES = _NSH_PROMO_PLAYER_SET['away']

# Per-tag date assignments for tags whose Comments identifies a specific
# game that the generic schedule lookup / colour-date extraction can't
# resolve.
# T02055 Swayman: 'Black - Promotional Game - Back-Up Only', tag note
# 'Shirt Off Their Back Night' -- Boston SOTBN game was 5/8/2021.
_PER_TAG_DATES = {
    'T02055': (('2021-05-08',),
               'Comment: Shirt Off Their Back Night (5/8/2021)'),
}


MANIFEST_2020 = SheetManifest(
    tag='POP REPORT BY TAG NUMBER',
    schedule=('SET DATES - JERSEY SCHEDULES',),
    omit=('POP REPORT BY PLAYER',),
)


def _strip_nsh_promo_dates(schedule):
    """Strip the 4 Nashville PROMO Player-Set / Shirt-Off-Their-Back
    dates from regular Nashville home/away set buckets and the playoffs
    bucket, so non-PROMO Set entries don't carry them."""
    for lane, dates in _NSH_PROMO_PLAYER_SET.items():
        bad = set(dates)
        for key, val in list(schedule.items()):
            if not (len(key) == 3 and isinstance(val, list)):
                continue
            if key[0] == 'nashville predators' and key[1] == lane:
                schedule[key] = [g for g in val if g.get('date') not in bad]
        # Also strip from playoffs key if present
        pk = ('playoffs', 'nashville predators', lane)
        if pk in schedule:
            schedule[pk] = [g for g in schedule[pk] if g.get('date') not in bad]


def _split_edm_set3(schedule):
    """Move Edmonton's playoff games from Set 2 to Set 3 (the pop report
    issued a separate playoff jersey set)."""
    for lane in ('home', 'away'):
        po_key = ('playoffs', 'edmonton oilers', lane)
        po_games = schedule.get(po_key, [])
        if not po_games:
            continue
        po_dates = {g.get('date') for g in po_games}
        key2 = ('edmonton oilers', lane, 2)
        games2 = schedule.get(key2, [])
        schedule[key2] = [g for g in games2 if g.get('date') not in po_dates]
        schedule[('edmonton oilers', lane, 3)] = list(po_games)


def build_schedule_2020(wb, actual, manifest, season, tag_teams):
    rows = list(wb[sheet(actual, 'SET DATES - JERSEY SCHEDULES')]
                .iter_rows(values_only=True))
    schedule = toolbox.parse_set_dates_table(rows, season, tag_teams)
    schedule.update(toolbox.parse_pergame_schedule(rows, season, tag_teams))
    _strip_nsh_promo_dates(schedule)
    _split_edm_set3(schedule)
    return schedule


def _apply_nsh_promo_white(entries):
    """Assign 5/3 and 5/5 to Nashville PROMO White entries whose tag
    Comments note is 'Player Set'. The colour ('White - Promotional
    Game') lacks the date so apply_promo_color_dates can't reach them."""
    for e in entries:
        if e.team != 'Nashville Predators' or e.set_number != 'PROMO':
            continue
        c = e.color.lower()
        if 'white' not in c:
            continue
        if toolbox.is_game_issued(e.color) or toolbox.is_warmup_only(e.color):
            continue
        notes_tag = e.notes.get('tag', []) if isinstance(e.notes, dict) else []
        if not any('player set' in str(n).lower() for n in notes_tag):
            continue
        e.games_worn = [{'type': 'worn', 'date': d}
                        for d in _NSH_PROMO_WHITE_DATES]
        gen = e.notes.setdefault('generated', [])
        note = 'Promotional Game - Player Set'
        if note not in gen:
            gen.append(note)


def _apply_per_tag_dates(entries):
    for e in entries:
        fix = _PER_TAG_DATES.get(e.tag_number)
        if not fix:
            continue
        dates, note = fix
        e.games_worn = [{'type': 'worn', 'date': d} for d in dates]
        e.notes.setdefault('generated', []).append(note)


def parse_tags_2020(rows, col, header_idx, headers, league, schedule, season, report):
    from memorabilia.models import MeiGrayEntry
    entries, total = toolbox.parse_entries_color_set(
        rows, col, header_idx, league, schedule, report, MeiGrayEntry
    )
    toolbox.enrich_vintage(entries, schedule)
    _apply_nsh_promo_white(entries)
    _apply_per_tag_dates(entries)
    return entries, total


SPEC_2020 = YearSpec(
    manifest=MANIFEST_2020,
    build_schedule=build_schedule_2020,
    parse_tags=parse_tags_2020,
    corrections=toolbox.apply_promo_color_dates,
)

register('NHL', '2020-21', SPEC_2020)
