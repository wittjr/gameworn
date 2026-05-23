"""
2016-17 NHL population report.

Same single-column per-game schedule as 2015-16 ('Date, Opponent, Jersey,
Comments', weekday 'Mon, Sep 26, 2016' dates, PRESEASON/REGULAR SEASON/
PLAYOFFS sections, 'End <Colour> Set N' markers). Use both: per-game list
is authoritative; parse_set_dates_table contributes the preseason block.

Schedule covers the eight MeiGray-tracked teams: Boston, Columbus, Dallas,
Edmonton, Nashville, New Jersey, Philadelphia, Washington.

PROMO / VERIZON / BANNER / HHOF / RETRO / KIOSK / GOLD-VIN / Stadium-Series
(SS-*) / Heritage Classic (HC-*) special sets are handled by the shared
toolbox.apply_promo_color_dates corrections hook.

Per-year fixups:
  * Edmonton playoff-schedule date typos (4/3-4/10 are 5/3-5/10 -- Round 2
    vs Anaheim was May 2017) -- date_corrections on parse_pergame_schedule.
  * Edmonton 'Playoffs' set is a dedicated playoff jersey (separate from
    Set 3); _apply_edm_playoffs assigns the team's playoff dates by colour.
  * Edmonton 'Set 3 / Regular Season Only' jerseys must NOT carry the
    playoff dates the schedule lumps into away-set-3.
  * NJ Devils RETRO: schedule has 2 Retro games (1/26/17, 3/16/17) but the
    set code 'RETRO' has no digit so lookup_games returns []; lift those
    dates out of NJ's home buckets and assign to RETRO entries.
  * Washington N05743 set='4': mislabeled GI tag (the other 21 Set 4 entries
    are all Game-Issued). Stays dateless, with a generated note.

Tag sheet 'POP REPORT BY TAG NUMBER' has a leading blank column (handled via
header detection). Ignored: 'POP REPORT BY PLAYER'.
"""

from memorabilia.meigray import toolbox
from memorabilia.meigray.registry import (
    SheetManifest,
    YearSpec,
    register,
    sheet,
)

# Schedule date typos:
#   Edmonton PLAYOFFS section: 5/3-5/10 typo'd as 4/3-4/10 (Anaheim Round 2
#   was actually May 2017).
#   Nashville PLAYOFFS section: Round 2 at St. Louis on Apr 26/28 typo'd as
#   2016 instead of 2017.
_DATE_CORRECTIONS = {
    'Wed, Apr 3, 2017': 'Wed, May 3, 2017',
    'Fri, Apr 5, 2017': 'Fri, May 5, 2017',
    'Sun, Apr 7, 2017': 'Sun, May 7, 2017',
    'Wed, Apr 10, 2017': 'Wed, May 10, 2017',
    'Wed, Apr 26, 2016': 'Wed, Apr 26, 2017',
    'Fri, Apr 28, 2016': 'Fri, Apr 28, 2017',
}

# Edmonton 2017 playoff dates by jersey lane (after _DATE_CORRECTIONS).
_EDM_PLAYOFF_BY_LANE = {
    'away': ('2017-04-16', '2017-04-18', '2017-04-22', '2017-04-26',
             '2017-04-28', '2017-05-10'),
    'third': ('2017-04-12', '2017-04-14', '2017-04-20', '2017-04-30',
              '2017-05-03', '2017-05-05', '2017-05-07'),
}
_EDM_ALL_PLAYOFF_DATES = frozenset(
    d for ds in _EDM_PLAYOFF_BY_LANE.values() for d in ds)

# NJ Devils RETRO set was worn at two games per the schedule.
_NJD_RETRO_DATES = ('2017-01-26', '2017-03-16')

_NOTE_CORRECTIONS = {
    'N05743': ('This should be Game issued. Set 4 was not worn, every other '
               'jersey in this set is Game Issued.'),
}

MANIFEST_2016 = SheetManifest(
    tag='POP REPORT BY TAG NUMBER',
    schedule=('SET DATES - JERSEY SCHEDULES',),
    omit=('POP REPORT BY PLAYER',),
)


def _attach_nashville_scf(schedule):
    """Nashville's SCF jerseys cover BOTH the Western Conference Finals
    (5/12-5/22, not labelled with SCF comments in the schedule) and the
    Stanley Cup Final itself (5/29-6/14, labelled '<Color> Stanley Cup
    Final Set N'). The toolbox parser routes only the labelled SCF rows
    into ('scf', team, color, num); the WCF rows still sit in the regular
    away/home set-3 buckets. Merge both into the SCF keys."""
    team = 'nashville predators'
    for lane, schedule_lane in (('white', 'away'), ('gold', 'home')):
        wcf = list(schedule.get((team, schedule_lane, 3), []))
        scf1 = list(schedule.get(('scf', team, lane, 1), []))
        schedule[('scf', team, lane, 1)] = wcf + scf1
    # SCF-2 White wasn't worn; toolbox may or may not have created the key.
    schedule.setdefault(('scf', team, 'white', 2), [])


def _attach_njd_retro(schedule):
    """The 2 NJ Retro games (1/26/17, 3/16/17) default-bucket into NJ's home
    lane (jersey_home_away('Retro')='home'), polluting Red Set N. Remove
    them from every NJ home key and stash under a retro key for later
    lookup by RETRO tag entries."""
    bad = set(_NJD_RETRO_DATES)
    for key, val in list(schedule.items()):
        if (len(key) == 3 and key[0] == 'new jersey devils'
                and key[1] == 'home' and isinstance(val, list)):
            schedule[key] = [g for g in val if g.get('date') not in bad]
    schedule[('retro', 'new jersey devils')] = [
        {'type': 'worn', 'date': d} for d in _NJD_RETRO_DATES]


def _apply_njd_retro(entries, schedule):
    dates = schedule.get(('retro', 'new jersey devils')) or []
    if not dates:
        return
    for e in entries:
        if e.team != 'New Jersey Devils' or e.set_number != 'RETRO':
            continue
        if toolbox.is_game_issued(e.color) or toolbox.is_warmup_only(e.color):
            continue
        e.games_worn = list(dates)


def _apply_edm_playoffs(entries):
    """Edmonton has three patterns:
      * 'Playoffs' set: dedicated playoff jersey -> assign the team's playoff
        dates matching the colour's lane.
      * 'Set N / Regular Season Only' colour: strip playoff dates that
        leaked into the set N lookup (per-game parser puts playoffs in the
        same home/away/third buckets as regular season).
      * Anything else: leave unchanged ('Set N / Playoffs' colours keep all
        the lookup's dates, regular + playoff)."""
    for e in entries:
        if e.team != 'Edmonton Oilers':
            continue
        if e.set_number == 'Playoffs':
            if (toolbox.is_game_issued(e.color)
                    or toolbox.is_warmup_only(e.color)):
                continue
            lane = toolbox.jersey_home_away(e.color)
            dates = _EDM_PLAYOFF_BY_LANE.get(lane, ())
            e.games_worn = [{'type': 'worn', 'date': d} for d in dates]
            gen = e.notes.setdefault('generated', [])
            note = 'Playoff dates only'
            if note not in gen:
                gen.append(note)
        elif ('regular season only' in e.color.lower()
                and e.games_worn):
            kept = [g for g in e.games_worn
                    if g.get('date') not in _EDM_ALL_PLAYOFF_DATES]
            if len(kept) == len(e.games_worn):
                continue
            removed = sorted({g['date'] for g in e.games_worn
                              if g['date'] in _EDM_ALL_PLAYOFF_DATES})
            e.games_worn = kept
            gen = e.notes.setdefault('generated', [])
            note = 'Excluded playoff date(s): ' + ', '.join(removed)
            if note not in gen:
                gen.append(note)


def build_schedule_2016(wb, actual, manifest, season, tag_teams):
    rows = list(wb[sheet(actual, 'SET DATES - JERSEY SCHEDULES')]
                .iter_rows(values_only=True))
    schedule = toolbox.parse_set_dates_table(rows, season, tag_teams)
    schedule.update(toolbox.parse_pergame_schedule(
        rows, season, tag_teams, date_corrections=_DATE_CORRECTIONS))
    _attach_njd_retro(schedule)
    _attach_nashville_scf(schedule)
    return schedule


def parse_tags_2016(rows, col, header_idx, headers, league, schedule, season, report):
    from memorabilia.models import MeiGrayEntry
    entries, total = toolbox.parse_entries_color_set(
        rows, col, header_idx, league, schedule, report, MeiGrayEntry
    )
    toolbox.enrich_vintage(entries, schedule)
    _apply_njd_retro(entries, schedule)
    _apply_edm_playoffs(entries)

    for e in entries:
        note = _NOTE_CORRECTIONS.get(e.tag_number)
        if note:
            gen = e.notes.setdefault('generated', [])
            if note not in gen:
                gen.append(note)

    return entries, total


SPEC_2016 = YearSpec(
    manifest=MANIFEST_2016,
    build_schedule=build_schedule_2016,
    parse_tags=parse_tags_2016,
    corrections=toolbox.apply_promo_color_dates,
)

register('NHL', '2016-17', SPEC_2016)
