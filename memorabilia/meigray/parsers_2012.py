"""
2012-13 NHL population report.

Single-column per-game schedule ('Date, Opponent, Jersey, Comments', string
dates like 'Sat Jan 19, 2013', 'End <Colour> Set N' markers). Use both: the
per-game list is authoritative; a summary table (if present) fills gaps.

Tag sheet 'POPULATION REPORT BY TAG NUMBER' has a leading blank column and a
'Vsn' (version) column before Customizations (handled via header detection).
Ignored: 'POPULATION REPORT BY PLAYER'.
"""

from memorabilia.meigray import toolbox
from memorabilia.meigray.registry import (
    SheetManifest,
    YearSpec,
    register,
    sheet,
)

MANIFEST_2012 = SheetManifest(
    tag='POPULATION REPORT BY TAG NUMBER',
    schedule=('SET DATES AND JERSEY SCHEDULE',),
    omit=('POPULATION REPORT BY PLAYER',),
)


def build_schedule_2012(wb, actual, manifest, season, tag_teams):
    rows = list(wb[sheet(actual, 'SET DATES AND JERSEY SCHEDULE')]
                .iter_rows(values_only=True))
    schedule = toolbox.parse_set_dates_table(rows, season, tag_teams)
    schedule.update(toolbox.parse_pergame_schedule(rows, season, tag_teams))
    return schedule


def parse_tags_2012(rows, col, header_idx, headers, league, schedule, season, report):
    from memorabilia.models import MeiGrayEntry
    entries, total = toolbox.parse_entries_color_set(
        rows, col, header_idx, league, schedule, report, MeiGrayEntry
    )
    toolbox.enrich_vintage(entries, schedule)
    return entries, total




SPEC_2012 = YearSpec(
    manifest=MANIFEST_2012,
    build_schedule=build_schedule_2012,
    parse_tags=parse_tags_2012,
    corrections=toolbox.apply_promo_color_dates,
)

register('NHL', '2012-13', SPEC_2012)
