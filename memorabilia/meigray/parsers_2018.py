"""
2018-19 NHL population report.

Same single-column per-game schedule as 2017-18 ('Date, Opponent, Jersey,
Comments', weekday 'Sat, Sep. 15, 2018' dates -- note the period after the
month abbreviation, tolerated by toolbox._parse_team_set_date),
PRESEASON/REGULAR SEASON sections. The 2018-19 schedule has NO 'PLAYOFFS'
section header for any team, so the toolbox playoffs key is empty;
per-year hooks recover playoff dates via a gap-heuristic.

Schedule covers Boston, Columbus, Edmonton, Nashville, New Jersey,
Philadelphia, Vegas, Washington.

Per-year fixups:
  * Boston has no 'End Black/White Set 2' marker and no PLAYOFFS header,
    so all post-Set-1 games leak into Set 2. The schedule lacks the data
    to know where Set 2 ended and Set 3 began. Apply the gap heuristic
    to identify the playoff boundary: post-boundary games go to Set 3,
    pre-boundary games are ORPHANED (no schedule key) -- Set 2 entries
    in the pop report stay dateless with an explanatory note.
  * Vegas Set 4 holds regular-season tail + Round 1 vs San Jose. Use the
    same gap heuristic to split Set 4 into regular tail (stays in Set 4)
    and playoffs (assigned to VGK - PO via the playoffs key).
  * NJD - HRTG (4 'Heritage' jersey rows ending 'End Hertiage Set 1 - 4
    Game Set' on 3/1) is bucketed into NJ home Set N by
    jersey_home_away('Heritage')='home'; lift those out.
  * BOS-CHINA, PHI-SS, BOS-WCS, BOS-RM, STP-VGK, CBJ-ONLINE are
    per-event date-in-colour sets wired via apply_promo_color_dates
    extras (same shape as 2015 MB-*, 2017 NJD-PE/PHI-EL/WSH-SS).

Tag sheet 'POP REPORT BY TAG NUMBER' has TAG # at column offset 0;
ignored 'POP REPORT BY PLAYER'.
"""

import re
from datetime import date as _date

from memorabilia.meigray import toolbox
from memorabilia.meigray.registry import (
    SheetManifest,
    YearSpec,
    register,
    sheet,
)

# NJ Devils Heritage Set 1 -- 4 games per the schedule's 'End Hertiage
# Set 1 - 4 Game Set' marker.
_NJD_HERITAGE_DATES = ('2018-12-23', '2019-01-10', '2019-01-31', '2019-03-01')

# Per-year promo prefixes for date-in-colour event sets.
_BOS_CHINA_RE = re.compile(r'^BOS\s*-\s*CHINA\b', re.IGNORECASE)
_PHI_SS_RE = re.compile(r'^PHI\s*-\s*SS\b', re.IGNORECASE)
_BOS_WCS_RE = re.compile(r'^BOS\s*-\s*WCS\b', re.IGNORECASE)
_BOS_RM_RE = re.compile(r'^BOS\s*-\s*RM$', re.IGNORECASE)
_STP_VGK_RE = re.compile(r'^STP\s*-\s*VGK\b', re.IGNORECASE)
_CBJ_ONLINE_RE = re.compile(r'^CBJ\s*-\s*ONLINE\b', re.IGNORECASE)
_PROMO_EXTRAS = {
    _BOS_CHINA_RE: 'NHL China Games',
    _PHI_SS_RE: 'Stadium Series Style',
    _BOS_WCS_RE: 'Winter Classic Style',
    _BOS_RM_RE: 'Rick Middleton Retirement Night',
    _STP_VGK_RE: "St. Patrick's Day Warm-Up",
    _CBJ_ONLINE_RE: 'Online Auction Set',
}

MANIFEST_2018 = SheetManifest(
    tag='POP REPORT BY TAG NUMBER',
    schedule=('SET DATES - JERSEY SCHEDULES',),
    omit=('POP REPORT BY PLAYER',),
)


def _parse_iso(s):
    y, m, d = s.split('-')
    return _date(int(y), int(m), int(d))


def _norm_opp(s):
    """'vs Toronto' / 'at Toronto' / 'Toronto' -> 'toronto'."""
    if not s:
        return ''
    s = str(s).strip().lower()
    for prefix in ('vs ', 'at ', '@ '):
        if s.startswith(prefix):
            s = s[len(prefix):]
            break
    return s.strip()


def _playoff_boundary(games, lookahead=3, min_repeats=3):
    """Index of the first playoff game within `games`, or None. A game
    starts a playoff series if the opponent appears >= min_repeats times
    within the window of current + next `lookahead` games.

    Opponent repetition is a far more reliable playoff signal than date
    gaps: regular-season schedules rarely play the same opponent 3+ times
    in 4 consecutive games, while playoff series do so by construction
    (4-7 games against one opponent)."""
    if not games:
        return None
    ordered = sorted(games, key=lambda g: g.get('date', ''))
    for i in range(len(ordered)):
        window = ordered[i:i + 1 + lookahead]
        if len(window) < 2:
            continue
        opp = _norm_opp(window[0].get('opponent', ''))
        if not opp:
            continue
        matches = sum(1 for g in window
                      if _norm_opp(g.get('opponent', '')) == opp)
        if matches >= min(min_repeats, len(window)):
            return i
    return None


def _extract_playoffs(games):
    """Returns (regular, playoffs) using opponent-repetition heuristic.
    Both are None if no clear boundary."""
    if not games:
        return None, None
    ordered = sorted(games, key=lambda g: g.get('date', ''))
    boundary = _playoff_boundary(ordered)
    if boundary is None:
        return None, None
    return ordered[:boundary], ordered[boundary:]


def _split_boston_missing_set2(schedule):
    """Boston: schedule has 'End Black/White Set 1' then 'End Black/White
    Set 3 / Playoffs' with no intermediate Set 2 marker. The toolbox's
    reverse-pass authoritatively assigns every post-Set-1 game to Set 3
    (the next End marker at-or-after each row). That over-fills Set 3
    with regular Feb-Apr games it shouldn't have.

    Apply the opponent-repetition heuristic to split Set 3 -> playoffs
    only; the pre-boundary regular tail is orphaned (no schedule key),
    so pop-report Set 2 entries stay dateless with the explanatory note.
    """
    for lane in ('home', 'away'):
        key3 = ('boston bruins', lane, 3)
        regular, playoffs = _extract_playoffs(schedule.get(key3, []))
        if playoffs is None:
            continue
        schedule[key3] = list(playoffs)
        schedule[('playoffs', 'boston bruins', lane)] = list(playoffs)


def _split_vegas_set4(schedule):
    """Vegas has no regular Set 4 (End Gray Set 3 = 3/29 ends regular
    season). Everything in Set 4 is either a playoff game (VGK - PO) or
    a single-game event whose date is in its own set code's colour /
    comment:
      * 'In Arena Auction - 1 Game Set' (4/1) -> VGK-Arena
      * 'Promotional Game - Shirt Off Their Back Night' (4/4) -> PROMO
    Pull the playoff portion into the playoffs key for VGK - PO and
    empty Set 4 -- single-game events are dated by their per-event
    handlers, not the regular Set 4 bucket."""
    for lane in ('home', 'away', 'third'):
        key4 = ('vegas golden knights', lane, 4)
        regular, playoffs = _extract_playoffs(schedule.get(key4, []))
        if playoffs is None:
            continue
        schedule[key4] = []
        schedule[('playoffs', 'vegas golden knights', lane)] = list(playoffs)


def _attach_njd_heritage(schedule):
    """4 Heritage games for NJ leaked into NJ home Set N (jersey_home_away
    of 'Heritage' = 'home'). Strip them out and stash for NJD - HRTG."""
    bad = set(_NJD_HERITAGE_DATES)
    for key, val in list(schedule.items()):
        if (len(key) == 3 and key[0] == 'new jersey devils'
                and key[1] == 'home' and isinstance(val, list)):
            schedule[key] = [g for g in val if g.get('date') not in bad]
    schedule[('heritage', 'new jersey devils')] = [
        {'type': 'worn', 'date': d} for d in _NJD_HERITAGE_DATES]


def build_schedule_2018(wb, actual, manifest, season, tag_teams):
    rows = list(wb[sheet(actual, 'SET DATES - JERSEY SCHEDULES')]
                .iter_rows(values_only=True))
    schedule = toolbox.parse_set_dates_table(rows, season, tag_teams)
    schedule.update(toolbox.parse_pergame_schedule(rows, season, tag_teams))
    _split_boston_missing_set2(schedule)
    _split_vegas_set4(schedule)
    _attach_njd_heritage(schedule)
    return schedule


def _apply_vgk_playoffs(entries, schedule):
    by_lane = {
        'home': schedule.get(
            ('playoffs', 'vegas golden knights', 'home'), []),
        'away': schedule.get(
            ('playoffs', 'vegas golden knights', 'away'), []),
        'third': schedule.get(
            ('playoffs', 'vegas golden knights', 'third'), []),
    }
    for e in entries:
        if e.team != 'Vegas Golden Knights' or e.set_number != 'VGK - PO':
            continue
        if toolbox.is_game_issued(e.color) or toolbox.is_warmup_only(e.color):
            continue
        lane = toolbox.jersey_home_away(e.color)
        dates = by_lane.get(lane, [])
        e.games_worn = [{'type': 'worn', 'date': g['date']} for g in dates]
        gen = e.notes.setdefault('generated', [])
        note = 'Playoff dates only'
        if note not in gen:
            gen.append(note)


def _apply_njd_heritage(entries, schedule):
    dates = schedule.get(('heritage', 'new jersey devils')) or []
    if not dates:
        return
    for e in entries:
        if e.team != 'New Jersey Devils' or e.set_number != 'NJD - HRTG':
            continue
        if toolbox.is_game_issued(e.color) or toolbox.is_warmup_only(e.color):
            continue
        e.games_worn = list(dates)
        gen = e.notes.setdefault('generated', [])
        if 'Heritage Set 1' not in gen:
            gen.append('Heritage Set 1')


def _apply_boston_set2_note(entries):
    """Boston Set 2 entries can't be dated -- the population report has
    no Set 2 boundary markers. Add an explanatory generated note."""
    note = ('Population report is missing Set 2 boundaries, '
            'cannot determine exact dates for set')
    for e in entries:
        if e.team != 'Boston Bruins' or e.set_number != '2':
            continue
        if toolbox.is_game_issued(e.color) or toolbox.color_flag_text(e.color):
            continue
        gen = e.notes.setdefault('generated', [])
        if note not in gen:
            gen.append(note)


def parse_tags_2018(rows, col, header_idx, headers, league, schedule, season, report):
    from memorabilia.models import MeiGrayEntry
    entries, total = toolbox.parse_entries_color_set(
        rows, col, header_idx, league, schedule, report, MeiGrayEntry
    )
    toolbox.enrich_vintage(entries, schedule)
    _apply_vgk_playoffs(entries, schedule)
    _apply_njd_heritage(entries, schedule)
    _apply_boston_set2_note(entries)
    return entries, total


def corrections_2018(entries):
    toolbox.apply_promo_color_dates(entries, extras=_PROMO_EXTRAS)


SPEC_2018 = YearSpec(
    manifest=MANIFEST_2018,
    build_schedule=build_schedule_2018,
    parse_tags=parse_tags_2018,
    corrections=corrections_2018,
)

register('NHL', '2018-19', SPEC_2018)
