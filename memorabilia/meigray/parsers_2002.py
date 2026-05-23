"""
2002-03 NHL population report.

Tag sheet ('Tag Number'): TAG #, Team, Player, JSY #, Color, Set, Size
  (no Notes column -- the generic color/set parser pads it).
Schedule:
  'Jersey Set Dates'   -- legacy home/road date-range tab
  'Third Jersey Dates' -- legacy third-jersey comma-date tab
Ignored: 'Player', 'Team' (alternate sort orders of the tag data).

Until a later year's format diverges, the registry reuses this spec for all
following seasons via resolve()'s inheritance.
"""

from memorabilia.meigray import toolbox
from memorabilia.meigray.registry import (
    SheetManifest,
    YearSpec,
    register,
    sheet,
)

MANIFEST_2002 = SheetManifest(
    tag='Tag Number',
    schedule=('Jersey Set Dates', 'Third Jersey Dates'),
    omit=('Player', 'Team'),
)


def build_schedule_2002(wb, actual, manifest, season, tag_teams):
    """Merge the home/road range tab and the third-jersey comma-date tab into
    one schedule dict."""
    team_index = toolbox.build_team_index(tag_teams)
    schedule = {}

    range_rows = list(wb[sheet(actual, 'Jersey Set Dates')].iter_rows(values_only=True))
    set_ranges, set_counts = toolbox.parse_range_rows(range_rows, team_index)
    if set_ranges:
        schedule.update(toolbox.schedule_from_ranges(set_ranges, set_counts, season))

    thirds_rows = list(wb[sheet(actual, 'Third Jersey Dates')].iter_rows(values_only=True))
    schedule.update(toolbox.parse_legacy_thirds(thirds_rows, season, tag_teams))

    return schedule


def parse_tags_2002(rows, col, header_idx, headers, league, schedule, season, report):
    from memorabilia.models import MeiGrayEntry
    return toolbox.parse_entries_color_set(
        rows, col, header_idx, league, schedule, report, MeiGrayEntry
    )


SPEC_2002 = YearSpec(
    manifest=MANIFEST_2002,
    build_schedule=build_schedule_2002,
    parse_tags=parse_tags_2002,
)

register('NHL', '2002-03', SPEC_2002)
