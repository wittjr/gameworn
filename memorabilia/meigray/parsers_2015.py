"""
2015-16 NHL population report.

Same single-column per-game schedule as 2014-15 ('Date, Opponent, Jersey,
Comments', weekday 'Sun, Sep 20, 2015' dates, PRESEASON/REGULAR SEASON/PLAYOFFS
sections, 'End <Colour> Set N' markers). Use both: per-game list is
authoritative; parse_set_dates_table contributes the preseason block.

Schedule covers the nine MeiGray-tracked teams: Boston, Columbus, Dallas,
Edmonton, Los Angeles, Nashville, New Jersey, Philadelphia, Washington. All
other teams in the tag tab carry special-set codes only (SS-DET-*, RB-HOF,
AS-MET-GI, etc.) and are dateless by design.

PROMO / VERIZON / BANNER / HHOF / RETRO / KIOSK / GOLD-VIN / Stadium-Series
special sets (date in the colour, numeric or spelled-out) are handled by the
shared toolbox.apply_promo_color_dates corrections hook.

LA Kings' GOLD-VIN set is listed as 'Gold' in the schedule's Jersey column
this year (no 'Vint'/'Vintage' label, no date in the tag's colour). That
default-buckets the Gold dates into LA's home lane (polluting Black Set N)
and leaves GOLD-VIN entries dateless. _attach_la_gold_vintage moves those
dates to a vintage key and _apply_la_gold_vin assigns them to GOLD-VIN tags.

Tag sheet 'POP REPORT BY TAG NUMBER' has a leading blank column (handled via
header detection). Ignored: 'POP REPORT BY PLAYER'.
"""

import re

from memorabilia.meigray import toolbox
from memorabilia.meigray.registry import (
    SheetManifest,
    YearSpec,
    register,
    sheet,
)

# Martin Brodeur Night (NJ Devils, 2/9/16): set codes 'MB - 1', 'MB - 2 & 3',
# 'MB - W' carry the event date in the colour, same shape as the global
# SS-*/HC-*/MM-* promo prefixes -- but MB is this-year-only, so we register
# it via apply_promo_color_dates' per-year `extras` rather than the shared
# _PROMO_PREFIX_RE.
_MB_RE = re.compile(r'^MB\b', re.IGNORECASE)
_PROMO_EXTRAS = {_MB_RE: 'Martin Brodeur Night'}

# Columbus schedule typos: the second date drops a row entirely, including its
# 'End White Set 1' marker, collapsing all White set-2 games into set 1.
_DATE_CORRECTIONS = {
    'Sa, Oct 24, 2015': 'Sat, Oct 24, 2015',
    'Sat, Nov, 28, 2015': 'Sat, Nov 28, 2015',
}

# Philly Stolarz Third Set 2 jerseys: Set field is '3', but the Flyers' Third
# set doesn't reach a Set 3 this year and the colour says 'Third Set 2'.
_SET_CORRECTIONS = {
    'M05758': ('2', "Set field in report is '3', but there is no Third Set 3"),
    'M05759': ('2', "Set field in report is '3', but there is no Third Set 3"),
}

MANIFEST_2015 = SheetManifest(
    tag='POP REPORT BY TAG NUMBER',
    schedule=('SET DATES - JERSEY SCHEDULES',),
    omit=('POP REPORT BY PLAYER',),
)


def _attach_la_gold_vintage(rows, schedule):
    """Re-scan the LA Kings block of the schedule for Gold-jersey rows, lift
    those dates out of LA's home buckets (where jersey_home_away placed them),
    and stash them under a vintage key for GOLD-VIN entries to consume."""
    headers = [i for i, r in enumerate(rows)
               if any(c is not None
                      and toolbox._TEAM_HDR_RE.match(str(c).strip())
                      for c in r)]
    headers.append(len(rows))
    for hi in range(len(headers) - 1):
        start, end = headers[hi], headers[hi + 1]
        if not any(c is not None and 'LOS ANGELES' in str(c).upper()
                   for c in rows[start]):
            continue
        gold_dates = []
        for r in rows[start + 1:end]:
            if len(r) <= 3 or not r[3]:
                continue
            if str(r[3]).strip().lower() != 'gold':
                continue
            iso = toolbox._parse_team_set_date(r[1] if len(r) > 1 else None)
            if iso:
                gold_dates.append(iso)
        gold_dates = sorted(set(gold_dates))
        if not gold_dates:
            return
        bad = set(gold_dates)
        for key, val in list(schedule.items()):
            if (len(key) == 3 and key[0] == 'los angeles kings'
                    and key[1] == 'home' and isinstance(val, list)):
                schedule[key] = [g for g in val if g.get('date') not in bad]
        entries = [{'type': 'vintage', 'date': d} for d in gold_dates]
        schedule[('vintage', 'los angeles kings', 'gold', 1)] = entries
        schedule[('vintage', 'los angeles kings', None, 1)] = entries
        return


def _apply_la_gold_vin(entries, schedule):
    """GOLD-VIN entries on LA Kings: enrich_vintage skips them because the set
    code isn't numeric. Assign the LA vintage dates directly. GI variants are
    cleared by the global GI pass; 'One Game Only' variants are replaced by
    the global one-game pass with their explicit colour date.

    A player wearing a 'Gold - One Game Only' jersey did not wear their
    regular Gold Vintage that game, so the OGO date is excluded from that
    player's regular Gold Vintage entries (mirrors apply_promo_color_dates)."""
    dates = schedule.get(('vintage', 'los angeles kings', 'gold', 1)) or []
    if not dates:
        return

    ogo_player_dates = {}
    for e in entries:
        if (e.team == 'Los Angeles Kings' and e.set_number == 'GOLD-VIN'
                and toolbox.is_one_game_only(e.color)):
            for d in toolbox.one_game_only_dates(e.color):
                ogo_player_dates.setdefault(e.player, set()).add(d)

    for e in entries:
        if e.team != 'Los Angeles Kings' or e.set_number != 'GOLD-VIN':
            continue
        if toolbox.is_game_issued(e.color) or toolbox.is_one_game_only(e.color):
            continue
        skip = ogo_player_dates.get(e.player, set())
        e.games_worn = [g for g in dates if g['date'] not in skip]
        if skip:
            note = ('Excluded ' + ', '.join(sorted(skip))
                    + ' (worn as One Game Only jersey)')
            gen = e.notes.setdefault('generated', [])
            if note not in gen:
                gen.append(note)


def build_schedule_2015(wb, actual, manifest, season, tag_teams):
    rows = list(wb[sheet(actual, 'SET DATES - JERSEY SCHEDULES')]
                .iter_rows(values_only=True))
    schedule = toolbox.parse_set_dates_table(rows, season, tag_teams)
    schedule.update(toolbox.parse_pergame_schedule(
        rows, season, tag_teams, date_corrections=_DATE_CORRECTIONS))
    _attach_la_gold_vintage(rows, schedule)
    return schedule


def parse_tags_2015(rows, col, header_idx, headers, league, schedule, season, report):
    from memorabilia.models import MeiGrayEntry
    entries, total = toolbox.parse_entries_color_set(
        rows, col, header_idx, league, schedule, report, MeiGrayEntry
    )
    toolbox.enrich_vintage(entries, schedule)
    _apply_la_gold_vin(entries, schedule)

    for e in entries:
        fix = _SET_CORRECTIONS.get(e.tag_number)
        if not fix:
            continue
        new_set, note = fix
        e.set_number = new_set
        e.games_worn = toolbox.lookup_games(
            schedule, e.team, e.color,
            toolbox.parse_set_number(new_set), set_raw=new_set)
        e.notes.setdefault('generated', []).append(note)

    return entries, total


def corrections_2015(entries):
    toolbox.apply_promo_color_dates(entries, extras=_PROMO_EXTRAS)


SPEC_2015 = YearSpec(
    manifest=MANIFEST_2015,
    build_schedule=build_schedule_2015,
    parse_tags=parse_tags_2015,
    corrections=corrections_2015,
)

register('NHL', '2015-16', SPEC_2015)
