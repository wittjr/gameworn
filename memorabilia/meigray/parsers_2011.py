"""
2011-12 NHL population report.

Structurally the same as 2010-11: a per-game two-block schedule
('Date, Opponent, JSY, Notes', 'End <Colour> Set N' markers, Preseason
sub-block) plus a per-team 'Set | Dates | Games' summary table. Use both:
the per-game list is authoritative (exact dates incl. Set 3 / playoffs); the
summary table fills any (team, set) the per-game block doesn't cover.

Tag sheet 'Population Report By Tag #' has a leading blank column and a
'Version' column before Comments (both handled via header detection).
Ignored: 'Population Report By Player'.
"""

from memorabilia.meigray import toolbox
from memorabilia.meigray.registry import (
    SheetManifest,
    YearSpec,
    register,
    sheet,
)

MANIFEST_2011 = SheetManifest(
    tag='Population Report By Tag #',
    schedule=('Set Dates & Jersey Schedule',),
    omit=('Population Report By Player',),
)


def build_schedule_2011(wb, actual, manifest, season, tag_teams):
    rows = list(wb[sheet(actual, 'Set Dates & Jersey Schedule')]
                .iter_rows(values_only=True))
    schedule = toolbox.parse_set_dates_table(rows, season, tag_teams)
    schedule.update(toolbox.parse_pergame_schedule(rows, season, tag_teams))
    return schedule


def parse_tags_2011(rows, col, header_idx, headers, league, schedule, season, report):
    from memorabilia.models import MeiGrayEntry
    entries, total = toolbox.parse_entries_color_set(
        rows, col, header_idx, league, schedule, report, MeiGrayEntry
    )
    toolbox.enrich_vintage(entries, schedule)
    return entries, total


SPEC_2011 = YearSpec(
    manifest=MANIFEST_2011,
    build_schedule=build_schedule_2011,
    parse_tags=parse_tags_2011,
)

register('NHL', '2011-12', SPEC_2011)
