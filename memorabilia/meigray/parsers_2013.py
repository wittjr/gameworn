"""
2013-14 NHL population report.

Single-column per-game schedule ('Date, Opponent, Jersey, Comments',
'Mon Sep 16, 2013' dates, PRESEASON/REGULAR SEASON section labels,
'End <Colour> Set N' markers). Use both: the per-game list is authoritative;
parse_set_dates_table contributes the preseason block (and any summary table).

Tag sheet 'POP REPORT BY TAG NUMBER' has a leading blank column and a 'Vsn'
column before Customizations (handled via header detection).
Ignored: 'POP REPORT BY PLAYER'.
"""

from memorabilia.meigray import toolbox
from memorabilia.meigray.registry import (
    SheetManifest,
    YearSpec,
    register,
    sheet,
)

MANIFEST_2013 = SheetManifest(
    tag='POP REPORT BY TAG NUMBER',
    schedule=('SET DATES - JERSEY SCHEDULES',),
    omit=('POP REPORT BY PLAYER',),
)


def build_schedule_2013(wb, actual, manifest, season, tag_teams):
    rows = list(wb[sheet(actual, 'SET DATES - JERSEY SCHEDULES')]
                .iter_rows(values_only=True))
    schedule = toolbox.parse_set_dates_table(rows, season, tag_teams)
    schedule.update(toolbox.parse_pergame_schedule(rows, season, tag_teams))
    return schedule


def parse_tags_2013(rows, col, header_idx, headers, league, schedule, season, report):
    from memorabilia.models import MeiGrayEntry
    entries, total = toolbox.parse_entries_color_set(
        rows, col, header_idx, league, schedule, report, MeiGrayEntry
    )
    toolbox.enrich_vintage(entries, schedule)
    return entries, total


SPEC_2013 = YearSpec(
    manifest=MANIFEST_2013,
    build_schedule=build_schedule_2013,
    parse_tags=parse_tags_2013,
    # Same PROMO/VERIZON colour-date pattern as 2012-13.
    corrections=toolbox.apply_promo_color_dates,
)

register('NHL', '2013-14', SPEC_2013)
