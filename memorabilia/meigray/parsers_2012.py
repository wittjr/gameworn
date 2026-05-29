"""
2012-13 NHL population report.

Tag sheet 'POPULATION REPORT BY TAG NUMBER'; schedule on
'SET DATES AND JERSEY SCHEDULE' (single-column per-game schedule + summary).
Ignored: 'POPULATION REPORT BY PLAYER'.
"""

from memorabilia.meigray import toolbox
from memorabilia.meigray.registry import SheetManifest, YearSpec, register

MANIFEST_2012 = SheetManifest(
    tag='POPULATION REPORT BY TAG NUMBER',
    schedule=('SET DATES AND JERSEY SCHEDULE',),
    omit=('POPULATION REPORT BY PLAYER',),
)


def parse_tags_2012(wb, actual, manifest, report):
    return toolbox.read_tag_rows(wb, actual, manifest, report)


def parse_schedule_2012(wb, actual, manifest, report, tag_teams):
    return toolbox.read_combined_schedule(
        wb, actual, 'SET DATES AND JERSEY SCHEDULE', report.season, tag_teams)


register('NHL', '2012-13', YearSpec(MANIFEST_2012, parse_tags_2012, parse_schedule_2012))
