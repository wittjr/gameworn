"""
2010-11 NHL population report (the original .xls was converted to .xlsx).

Same per-team 'Set | Dates | Games' summary-table model as 2008-10
(parse_set_dates_table), with drift the generalized parser absorbs:
  - team header is '<City> 2010-11' (no 'Season' word)
  - 'Black Set 3 / Playoffs' labels (the '/ Playoffs' qualifier is stripped)
  - 'Black SCF Set N' rows are ignored (SCF stays dateless-special)
  - single-date values are real datetime cells
Tag sheet 'Pop Report - Sorted by Inv Tag ' has a 'Version' column before
Customizations (comment column located from the header).
Ignored: 'Pop Report - Sorted by Player'.
"""

from memorabilia.meigray import toolbox
from memorabilia.meigray.registry import (
    SheetManifest,
    YearSpec,
    register,
    sheet,
)

MANIFEST_2010 = SheetManifest(
    tag='Pop Report - Sorted by Inv Tag',
    schedule=('Jersey Set Dates',),
    omit=('Pop Report - Sorted by Player',),
)


# Per-file summary-table cell fixups. Washington 'Red Set 2/PO' start date
# is typo'd '2/8/10' (should be 2/8/11 -- Feb of the 2010-11 season).
_CELL_CORRECTIONS = {
    '2/8/10 - 4/13/11': '2/8/11 - 4/13/11',
}


def build_schedule_2010(wb, actual, manifest, season, tag_teams):
    rows = list(wb[sheet(actual, 'Jersey Set Dates')].iter_rows(values_only=True))
    # Use BOTH sources: the per-game list (exact dates per set, incl. Set 3 /
    # playoffs via the 'OS2 Ends' markers) is authoritative; the summary table
    # fills any (team, set) the per-game block doesn't cover.
    schedule = toolbox.parse_set_dates_table(
        rows, season, tag_teams, cell_corrections=_CELL_CORRECTIONS)
    schedule.update(toolbox.parse_pergame_schedule(rows, season, tag_teams))
    return schedule


def parse_tags_2010(rows, col, header_idx, headers, league, schedule, season, report):
    from memorabilia.models import MeiGrayEntry
    entries, total = toolbox.parse_entries_color_set(
        rows, col, header_idx, league, schedule, report, MeiGrayEntry
    )
    toolbox.enrich_vintage(entries, schedule)
    return entries, total


SPEC_2010 = YearSpec(
    manifest=MANIFEST_2010,
    build_schedule=build_schedule_2010,
    parse_tags=parse_tags_2010,
)

register('NHL', '2010-11', SPEC_2010)
