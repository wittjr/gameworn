"""
2013-14 NHL population report.

Tag sheet 'POP REPORT BY TAG NUMBER'; schedule on 'SET DATES - JERSEY
SCHEDULES' (per-game schedule + summary table).
Ignored: 'POP REPORT BY PLAYER'.
"""

from memorabilia.meigray import toolbox
from memorabilia.meigray.registry import SheetManifest, YearSpec, register

MANIFEST_2013 = SheetManifest(
    tag='POP REPORT BY TAG NUMBER',
    schedule=('SET DATES - JERSEY SCHEDULES',),
    omit=('POP REPORT BY PLAYER',),
)


def parse_tags_2013(wb, actual, manifest, report):
    return toolbox.read_tag_rows(wb, actual, manifest, report)


def parse_schedule_2013(wb, actual, manifest, report, tag_teams):
    return toolbox.read_combined_schedule(
        wb, actual, 'SET DATES - JERSEY SCHEDULES', report.season, tag_teams)


register('NHL', '2013-14', YearSpec(MANIFEST_2013, parse_tags_2013, parse_schedule_2013))
