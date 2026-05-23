"""
2008-09 NHL population report.

Tag sheet 'Pop Rept By Tag Number' (has a 'Version' column before
Customizations -- the generic parser locates the comment column from the
header). Schedule tab 'Set Dates' has no per-game End markers; instead each
team block ends with a 'Set:' / 'Dates and Number of Games:' summary table
giving a date range + count per set + home/away/third. That table is the
set delimiter (the 2002-03 range model, embedded per team).
Ignored: 'Pop Rept By Player'.
"""

from memorabilia.meigray import toolbox
from memorabilia.meigray.registry import (
    SheetManifest,
    YearSpec,
    register,
    sheet,
)

MANIFEST_2008 = SheetManifest(
    tag='Pop Rept By Tag Number',
    schedule=('Set Dates',),
    omit=('Pop Rept By Player',),
)


def build_schedule_2008(wb, actual, manifest, season, tag_teams):
    rows = list(wb[sheet(actual, 'Set Dates')].iter_rows(values_only=True))
    return toolbox.parse_set_dates_table(rows, season, tag_teams)


def parse_tags_2008(rows, col, header_idx, headers, league, schedule, season, report):
    from memorabilia.models import MeiGrayEntry
    entries, total = toolbox.parse_entries_color_set(
        rows, col, header_idx, league, schedule, report, MeiGrayEntry
    )
    toolbox.enrich_vintage(entries, schedule)
    return entries, total


SPEC_2008 = YearSpec(
    manifest=MANIFEST_2008,
    build_schedule=build_schedule_2008,
    parse_tags=parse_tags_2008,
)

register('NHL', '2008-09', SPEC_2008)
