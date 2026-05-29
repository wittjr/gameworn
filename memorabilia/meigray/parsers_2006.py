"""
2006-07 NHL population report.

Same per-game two-block schedule format as 2005-06, with drift the generalized
toolbox parser absorbs automatically:
  - schedule tab is 'Set Breakdowns' (was 'Team Set Dates')
  - the second column group / season marker shifted one column right
  - date cells are real datetimes (were 'Oct 5 2005, Wed' strings)
Tag sheet 'Sorted By Tag Number' -- generic color/set parser.
Ignored: 'Sorted By Team', 'Sorted By Player' (alternate sorts of the tags).
"""

from memorabilia.meigray import toolbox
from memorabilia.meigray.registry import (
    SheetManifest,
    YearSpec,
    register,
    sheet,
)

MANIFEST_2006 = SheetManifest(
    tag='Sorted By Tag Number',
    schedule=('Set Breakdowns',),
    omit=('Sorted By Team', 'Sorted By Player'),
)


def build_schedule_2006(wb, actual, manifest, season, tag_teams):
    rows = list(wb[sheet(actual, 'Set Breakdowns')].iter_rows(values_only=True))
    return toolbox.parse_team_set_dates(rows, season, tag_teams)


# Per-file data corrections: {tag_number: (corrected_set, note)}. Used only
# for known errors in this specific report.
_SET_CORRECTIONS = {
    # D08815 is colour 'Third Set 1' but the Set column says 2; every other
    # Colorado 'Third Set 1' says 1 -- the 2 is a typo.
    'D08815': ('1', 'Population Report says set 2, but assuming it should be set 1'),
}


def parse_tags_2006(rows, col, header_idx, headers, league, schedule, season, report):
    from memorabilia.models import MeiGrayEntry
    entries, total = toolbox.parse_entries_color_set(
        rows, col, header_idx, league, schedule, report, MeiGrayEntry
    )
    toolbox.enrich_vintage(entries, schedule)

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


SPEC_2006 = YearSpec(
    manifest=MANIFEST_2006,
    build_schedule=build_schedule_2006,
    parse_tags=parse_tags_2006,
)

register('NHL', '2006-07', SPEC_2006)
