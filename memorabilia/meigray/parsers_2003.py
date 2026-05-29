"""
2003-04 NHL population report.

Tag sheet 'Sorted By Tag #': TAG #, Team, Player, JSY #, Jersey Type, Set,
Size, Customizations.

Schedule format: legacy per-team-per-lane summary rows spread across five
tabs. All five emit set-range data (no per-game rows are available for this
year):
  - 'Preseason and 1st Reg Sets'         (Home/Road regular jerseys)
  - '2nd & 3rd Reg + SCP Sets'           (Home/Road regular + playoffs)
  - 'Third Jersey Breakdown'             (third-jersey sets 1 & 2)
  - 'Vintage Sets'                       (vintage jerseys, up to 3 sets each)
  - 'Heritage Classic & MegaStars'       (one-off special-event jerseys)

Header formats vary per tab; the parser strips lane/color/event descriptors
from col 0 before calling toolbox.resolve_teams.

Ignored: 'Sorted By Player' (alternate sort of the tag data).
"""

import re
from datetime import date, datetime

from memorabilia.meigray import toolbox
from memorabilia.meigray.registry import (
    SheetManifest,
    YearSpec,
    register,
    sheet,
)

# 'Anaheim - Home Jade' -> lane='Home', color='Jade'. The team part is left
# to resolve_teams (which strips the same suffix internally).
_LANE_COLOR_RE = re.compile(
    r'\s-\s*(?P<lane>home|away|road)\s+(?P<color>.+)$',
    re.IGNORECASE,
)

# 'Boston - Black Vintage' -> team='Boston', color='Black'.
_VINTAGE_RE = re.compile(
    r'^(?P<team>.+?)\s*-\s*(?P<color>.+?)\s+Vintage\s*$',
    re.IGNORECASE,
)


def _lane_color(cell):
    m = _LANE_COLOR_RE.search(str(cell))
    if not m:
        return ''
    return f"{m.group('lane').title()} {m.group('color').strip()}"


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


def _set_entry(team, label, lane_color, games, dates):
    full = f'{label} {lane_color}'.strip() if lane_color else label
    return {
        'team': team,
        'set_label': full[:50],
        'game_count': games,
        'dates': dates[:255],
    }

MANIFEST_2003 = SheetManifest(
    tag='Sorted By Tag #',
    schedule=(
        'Preseason and 1st Reg Sets',
        '2nd & 3rd Reg + SCP Sets',
        'Third Jersey Breakdown',
        'Vintage Sets',
        'Heritage Classic & MegaStars',
    ),
    omit=('Sorted By Player',),
)

def parse_tags_2003(wb, actual, manifest, report):
    rows = list(wb[sheet(actual, manifest.tag)].iter_rows(values_only=True))
    col = toolbox.detect_col_offset(rows)
    header_idx, headers = toolbox.find_header(rows, col)
    return toolbox.parse_tag_sheet(rows, col, header_idx, headers, report)


def parse_schedule_2003(wb, actual, manifest, report, tag_teams):
    team_index = toolbox.build_team_index(tag_teams)
    set_ranges = []

    # Tab 1: 'Preseason and 1st Reg Sets'
    #   cols: [team, preseason desc, 1st reg dates, games:1stReg, promo]
    rows = toolbox.read_schedule_sheet(wb, actual, 'Preseason and 1st Reg Sets')
    for r in rows[3:]:
        if not r or not r[0]:
            continue
        teams = toolbox.resolve_teams(str(r[0]), team_index)
        if not teams:
            continue
        lane_color = _lane_color(r[0])
        preseason = _to_str(r[1] if len(r) > 1 else None)
        first_reg = _to_str(r[2] if len(r) > 2 else None)
        first_reg_games = _to_int(r[3] if len(r) > 3 else None)
        promo = _to_str(r[4] if len(r) > 4 else None)
        if len(promo) > 0:
            first_reg += f", Promo Date: {promo}"
        for tt in teams:
            if preseason:
                set_ranges.append(_set_entry(tt, 'PreSeason Set:', lane_color, None, preseason))
            if first_reg:
                set_ranges.append(_set_entry(tt, '1st Regular Season Set:', lane_color, first_reg_games, first_reg))

    # Tab 2: '2nd & 3rd Reg + SCP Sets'
    #   cols: [team, 2nd reg dates, games:2ndReg, 3rd reg/PO dates,
    #          games:3rdReg, games:Playoffs, promo, games:3rdReg+PO, New PO Set]
    rows = toolbox.read_schedule_sheet(wb, actual, '2nd & 3rd Reg + SCP Sets')
    for r in rows[3:]:
        if not r or not r[0]:
            continue
        teams = toolbox.resolve_teams(str(r[0]), team_index)
        if not teams:
            continue
        lane_color = _lane_color(r[0])
        second_reg = _to_str(r[1] if len(r) > 1 else None)
        second_reg_games = _to_int(r[2] if len(r) > 2 else None)
        third_po = _to_str(r[3] if len(r) > 3 else None)
        promo = _to_str(r[6] if len(r) > 6 else None)
        if len(promo) > 0:
            second_reg += f", Promo Date: {promo}"
        third_games = _to_str(r[4] if len(r) > 4 else None)
        po_games = _to_str(r[5] if len(r) > 5 else None)
        new_po_set = _to_str(r[8] if len(r) > 8 else None)
        third_po_games = _to_str(r[7] if len(r) > 7 else None)
        third_po_desc = f'{third_po_games} (3rd: {third_games}/Playoffs: {po_games} | New PO Set: {new_po_set})'
        for tt in teams:
            if second_reg:
                set_ranges.append(_set_entry(tt, '2nd Regular Season Set:', lane_color, second_reg_games, second_reg))
            if third_po:
                set_ranges.append(_set_entry(tt, '3rd Regular Season / Playoffs:', lane_color, third_po_desc, third_po))

    # Tab 3: 'Third Jersey Breakdown'
    #   cols: [team, total third games, set1 dates, set1 games,
    #          set2 dates, set2 games, extra notes]
    # Team header has no Home/Away suffix; the third jersey IS the lane/color.
    rows = toolbox.read_schedule_sheet(wb, actual, 'Third Jersey Breakdown')
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
        other_games = _to_str(r[6] if len(r) > 6 else None)
        for tt in teams:
            if set1:
                set_ranges.append(_set_entry(tt, 'Third Set 1:', '', set1_games, set1))
            if set2:
                set_ranges.append(_set_entry(tt, 'Third Set 2:', '', set2_games, set2))
            if other_games:
                set_ranges.append(_set_entry(tt, 'Third Jersey Games Not Included in Set 1 or 2:', '', None, other_games))

    # Tab 4: 'Vintage Sets'
    #   col 0: '<Team> - <Color> Vintage'; cols 1..3: Set 1/2/3 date descriptions
    #   No game counts in this tab.
    rows = toolbox.read_schedule_sheet(wb, actual, 'Vintage Sets')
    for r in rows[3:]:
        if not r or not r[0]:
            continue
        m = _VINTAGE_RE.match(str(r[0]).strip())
        if not m:
            continue
        teams = toolbox.resolve_teams(m.group('team').strip(), team_index)
        if not teams:
            continue
        color = m.group('color').strip()
        for idx in (1, 2, 3):
            dates = _to_str(r[idx] if len(r) > idx else None)
            if not dates:
                continue
            label = f'Vintage Set {idx} {color}'
            for tt in teams:
                set_ranges.append(_set_entry(tt, label, '', None, dates))

    # Tab 5: 'Heritage Classic & MegaStars'
    #   col 0: '<Team> - <Descriptor>' (e.g. 'Edmonton - White Heritage Classic')
    #   col 1: free-text date description. One set per row, no game count.
    rows = toolbox.read_schedule_sheet(wb, actual, 'Heritage Classic & MegaStars')
    for r in rows[3:]:
        if not r or not r[0]:
            continue
        parts = str(r[0]).strip().split(' - ', 1)
        if len(parts) != 2:
            continue
        team_name, descriptor = parts[0].strip(), parts[1].strip()
        teams = toolbox.resolve_teams(team_name, team_index)
        if not teams:
            continue
        dates = _to_str(r[1] if len(r) > 1 else None)
        if not dates:
            continue
        for tt in teams:
            set_ranges.append(_set_entry(tt, descriptor, '', None, dates))

    return [], set_ranges


register('NHL', '2003-04', YearSpec(MANIFEST_2003, parse_tags_2003, parse_schedule_2003))