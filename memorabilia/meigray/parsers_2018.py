"""
2018-19 NHL population report.

Tag sheet 'POP REPORT BY TAG NUMBER'; schedule on 'SET DATES - JERSEY
SCHEDULES' (per-game schedule + summary table).
Ignored: 'POP REPORT BY PLAYER'.
"""

from memorabilia.meigray import toolbox
from memorabilia.meigray.registry import SheetManifest, YearSpec, register

MANIFEST_2018 = SheetManifest(
    tag='POP REPORT BY TAG NUMBER',
    schedule=('SET DATES - JERSEY SCHEDULES',),
    omit=('POP REPORT BY PLAYER',),
)


def parse_tags_2018(wb, actual, manifest, report):
    return toolbox.read_tag_rows(wb, actual, manifest, report)


def parse_schedule_2018(wb, actual, manifest, report, tag_teams):
    games, set_ranges = toolbox.read_combined_schedule(
        wb, actual, 'SET DATES - JERSEY SCHEDULES', report.season, tag_teams)
    # The 2018-19 schedule sheet does not label the playoff section.
    for g in games:
        if g['date'] >= '2019-04-10':
            g['game_type'] = 'Playoffs'
    return games, set_ranges


register('NHL', '2018-19', YearSpec(MANIFEST_2018, parse_tags_2018, parse_schedule_2018))
