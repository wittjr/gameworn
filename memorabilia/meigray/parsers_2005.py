"""
2005-06 NHL population report.

Tag sheet ('Sorted By Tag Number'): TAG #, Team, Player, JSY #, Color, Set,
  Size, Customizations -- generic color/set parser.

Schedule diverges from 2002-04: a single 'Team Set Dates' tab in the per-game
two-block format (one block per team, season split across two column groups,
each row DATE / Jersey / note / OPPONENT). Set numbers advance on
'End Set N (H/A)' / 'End Third Set N' markers. Parsed into a
(team, lane, set) schedule that lookup_games resolves via its home/away branch.

Vintage here ('V (1)', 'V (2)') has no dedicated sheet, so those stay dateless
unless a 'Worn ...' comment supplies dates (handled globally).
Ignored: 'Sorted By Player'.
"""

from memorabilia.meigray import toolbox
from memorabilia.meigray.registry import (
    SheetManifest,
    YearSpec,
    register,
    sheet,
)

MANIFEST_2005 = SheetManifest(
    tag='Sorted By Tag Number',
    schedule=('Team Set Dates',),
    omit=('Sorted By Player',),
)


def build_schedule_2005(wb, actual, manifest, season, tag_teams):
    rows = list(wb[sheet(actual, 'Team Set Dates')].iter_rows(values_only=True))
    return toolbox.parse_team_set_dates(rows, season, tag_teams)


def parse_tags_2005(rows, col, header_idx, headers, league, schedule, season, report):
    from memorabilia.models import MeiGrayEntry
    entries, total = toolbox.parse_entries_color_set(
        rows, col, header_idx, league, schedule, report, MeiGrayEntry
    )
    # Vintage games are mixed into Team Set Dates (VINT rows) -> schedule
    # under ('vintage', team, color, set); fill them like 2003-04.
    toolbox.enrich_vintage(entries, schedule)
    return entries, total


SPEC_2005 = YearSpec(
    manifest=MANIFEST_2005,
    build_schedule=build_schedule_2005,
    parse_tags=parse_tags_2005,
)

register('NHL', '2005-06', SPEC_2005)
