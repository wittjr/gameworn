"""
2002-03 NHL population report.

Tag sheet 'Tag Number': TAG #, Team, Player, JSY #, Color, Set, Size.

Schedule format: legacy per-team-per-lane summary rows across two tabs. All
set-range data; no per-game rows exist for this year:
  - 'Jersey Set Dates'   (Home/Away regular jerseys: preseason, 1st, 2nd,
                          3rd/PO sets all on one row per team-lane)
  - 'Third Jersey Dates' (third-jersey sets 1 & 2)

Team headers are lane-only ('Anaheim - Home', 'Toronto - Thirds') with no
color, so the team is split from the lane before resolve_teams.

Ignored: 'Player', 'Team' (alternate sort orders of the tag data).
"""

from datetime import date, datetime

from memorabilia.meigray import toolbox
from memorabilia.meigray.registry import SheetManifest, YearSpec, register

MANIFEST_2002 = SheetManifest(
    tag='Tag Number',
    schedule=('Jersey Set Dates', 'Third Jersey Dates'),
    omit=('Player', 'Team'),
)


def _team_and_lane(cell):
    """'Anaheim - Home' -> ('Anaheim', 'Home'); 'Toronto - Thirds' ->
    ('Toronto', 'Thirds'). Splitting here (rather than via resolve_teams'
    Home/Away/Road strip) keeps non-standard lanes like 'Thirds' working."""
    s = str(cell).strip()
    if ' - ' in s:
        team_part, lane_part = s.rsplit(' - ', 1)
        return team_part.strip(), lane_part.strip()
    return s, ''


def _to_int(val):
    if val is None or val == '':
        return None
    try:
        return int(val)
    except (TypeError, ValueError):
        return None


def _to_str(val):
    if val is None:
        return ''
    if isinstance(val, datetime):
        return val.date().strftime("%m/%d")
    if isinstance(val, date):
        return val.strftime("%m/%d")
    return str(val).strip()


def _set_entry(team, label, lane, games, dates):
    full = f'{label} {lane}'.strip() if lane else label
    return {
        'team': team,
        'set_label': full[:50],
        'game_count': games,
        'dates': dates[:255],
    }


def parse_tags_2002(wb, actual, manifest, report):
    return toolbox.read_tag_rows(wb, actual, manifest, report)


def parse_schedule_2002(wb, actual, manifest, report, tag_teams):
    team_index = toolbox.build_team_index(tag_teams)
    set_ranges = []

    # Tab 1: 'Jersey Set Dates'
    #   cols: [team-lane, preseason, 1st reg dates, games:1stReg,
    #          2nd reg dates, games:2ndReg, 3rd reg/PO dates, games:3rdReg,
    #          games:Playoffs, promo, total:3rdReg/PO, P/O set]
    rows = toolbox.read_schedule_sheet(wb, actual, 'Jersey Set Dates')
    for r in rows[3:]:
        if not r or not r[0]:
            continue
        team_part, lane = _team_and_lane(r[0])
        teams = toolbox.resolve_teams(team_part, team_index)
        if not teams:
            continue
        preseason = _to_str(r[1] if len(r) > 1 else None)
        first_reg = _to_str(r[2] if len(r) > 2 else None)
        first_reg_games = _to_int(r[3] if len(r) > 3 else None)
        second_reg = _to_str(r[4] if len(r) > 4 else None)
        second_reg_games = _to_int(r[5] if len(r) > 5 else None)
        third_po = _to_str(r[6] if len(r) > 6 else None)

        # Promo column is a date when present, or 0 / blank for "no promo".
        promo_cell = r[9] if len(r) > 9 else None
        promo = _to_str(promo_cell)
        total_3rd_po = _to_str(r[10] if len(r) > 10 else None)
        third_games = _to_str(r[7] if len(r) > 7 else None)
        po_games = _to_str(r[8] if len(r) > 8 else None)
        po_set = _to_str(r[11] if len(r) > 11 else None)

        third_games_label = ''
        po_games_label = ''
        promo_label = ''
        if third_games and third_games != '0':
            third_games_label = f'3rd: {third_games}'
        if po_games and po_games != '0':
            po_games_label = f' | Playoffs: {po_games}'
        if promo and promo != '0':
            promo_label = f" | Promo Game: {promo}"
        third_po_desc = f'{total_3rd_po} ({third_games_label}{po_games_label}{promo_label})'


        for tt in teams:
            if preseason:
                set_ranges.append(_set_entry(tt, 'PreSeason Set:', lane, None, preseason))
            if first_reg:
                set_ranges.append(_set_entry(tt, '1st Regular Season Set:', lane, first_reg_games, first_reg))
            if second_reg:
                set_ranges.append(_set_entry(tt, '2nd Regular Season Set:', lane, second_reg_games, second_reg))
            if third_po:
                set_ranges.append(_set_entry(tt, '3rd Regular Season / Playoffs:', lane, third_po_desc, third_po))
            if po_set and po_set.lower() != '0':
                set_ranges.append(_set_entry(tt, 'Playoff Set:', lane, None, po_set))

    # Tab 2: 'Third Jersey Dates'
    #   cols: [team, total third games, set1 dates, set1 games,
    #          set2 dates, set2 games, notes]
    rows = toolbox.read_schedule_sheet(wb, actual, 'Third Jersey Dates')
    for r in rows[2:]:
        if not r or not r[0]:
            continue
        teams = toolbox.resolve_teams(str(r[0]), team_index)
        if not teams:
            continue
        set1 = _to_str(r[2] if len(r) > 2 else None)
        set1_games = _to_int(r[3] if len(r) > 3 else None)
        set2 = _to_str(r[4] if len(r) > 4 else None)
        set2_games = _to_int(r[5] if len(r) > 5 else None)
        notes = _to_str(r[6] if len(r) > 6 else None)
        for tt in teams:
            if set1:
                set_ranges.append(_set_entry(tt, 'Third Set 1:', '', set1_games, set1))
            if set2:
                set_ranges.append(_set_entry(tt, 'Third Set 2:', '', set2_games, set2))
            if notes:
                set_ranges.append(_set_entry(tt, 'Third Jersey Games Not Included in Set 1 or 2:', '', None, notes))

    return [], set_ranges


register('NHL', '2002-03', YearSpec(MANIFEST_2002, parse_tags_2002, parse_schedule_2002))
