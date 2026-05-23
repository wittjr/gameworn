"""
2009-10 NHL population report.

Same range-table model as 2008-09 (per-team 'Set:' summary table, no per-game
End markers), with drift the generalized parser absorbs: a leading blank
column, the team+season combined in one cell ('Atlanta Thrashers 2009-10
Season'), '<Colour> Set N' labels instead of 'Set N Home/Away', and the game
count in a separate '<n> Games' cell.
Tag sheet 'Pop Report Sorted By Inv Tag Nu' (Version column before
Customizations -- comment column located from the header).
Ignored: 'Pop Report Sorted By Player'.
"""

from memorabilia.meigray import toolbox
from memorabilia.meigray.registry import (
    SheetManifest,
    YearSpec,
    register,
    sheet,
)

MANIFEST_2009 = SheetManifest(
    tag='Pop Report Sorted By Inv Tag Nu',
    schedule=('Set Dates and Jersey Schedul',),
    omit=('Pop Report Sorted By Player',),
)


def build_schedule_2009(wb, actual, manifest, season, tag_teams):
    rows = list(wb[sheet(actual, 'Set Dates and Jersey Schedul')]
                .iter_rows(values_only=True))
    return toolbox.parse_set_dates_table(rows, season, tag_teams)


def parse_tags_2009(rows, col, header_idx, headers, league, schedule, season, report):
    from memorabilia.models import MeiGrayEntry
    entries, total = toolbox.parse_entries_color_set(
        rows, col, header_idx, league, schedule, report, MeiGrayEntry
    )
    toolbox.enrich_vintage(entries, schedule)
    return entries, total


def corrections_2009(entries):
    """Per-file manual fixups for Marty Turco's 500th game (Dallas, 3/18/10).

    G00215 is the 500th-game jersey -- colour says 'Black Set 3 - One Game
    Only' with no date, so it was left dateless. The game was 3/18/10 in the
    White jersey: assign that single date. Because a dedicated jersey was used
    that day, Turco's normal White Set 2 jerseys (G00189, G00210) did NOT cover
    3/18 -- exclude it from their range.
    """
    by = {e.tag_number: e for e in entries}

    g = by.get('G00215')
    if g is not None:
        g.games_worn = [{'type': 'worn', 'date': '2010-03-18'}]
        note = 'Manual correction: 500th game worn 3/18/10 in the White jersey'
        gen = g.notes.setdefault('generated', [])
        if note not in gen:
            gen.append(note)

    for tag in ('G00189', 'G00210'):
        e = by.get(tag)
        if e is None:
            continue
        new = []
        for ge in e.games_worn:
            if ge.get('type') == 'range':
                ge = dict(ge)
                ex = set(ge.get('exclude', []))
                ex.add('2010-03-18')
                ge['exclude'] = sorted(ex)
                if isinstance(ge.get('games'), int):
                    ge['games'] = max(ge['games'] - 1, 0)
            new.append(ge)
        e.games_worn = new
        note = ('Manual correction: 3/18/10 excluded (Turco wore his '
                '500th-game jersey that day)')
        gen = e.notes.setdefault('generated', [])
        if note not in gen:
            gen.append(note)


SPEC_2009 = YearSpec(
    manifest=MANIFEST_2009,
    build_schedule=build_schedule_2009,
    parse_tags=parse_tags_2009,
    corrections=corrections_2009,
)

register('NHL', '2009-10', SPEC_2009)
