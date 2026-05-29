"""
2005-06 NHL population report.

Tag sheet 'Sorted By Tag Number'; schedule on 'Team Set Dates' (per-game
two-block layout). The shared per-game reader handles it when team-header
detection picks up the block boundaries; if not, schedule rows are empty
for this year and only tags import.
Ignored: 'Sorted By Player'.
"""

from memorabilia.meigray import toolbox
from memorabilia.meigray.registry import SheetManifest, YearSpec, register

MANIFEST_2005 = SheetManifest(
    tag='Sorted By Tag Number',
    schedule=('Team Set Dates',),
    omit=('Sorted By Player',),
)


def parse_tags_2005(wb, actual, manifest, report):
    return toolbox.read_tag_rows(wb, actual, manifest, report)


def parse_schedule_2005(wb, actual, manifest, report, tag_teams):
    return toolbox.read_combined_schedule(
        wb, actual, 'Team Set Dates', report.season, tag_teams, 'Set:')


register('NHL', '2005-06', YearSpec(MANIFEST_2005, parse_tags_2005, parse_schedule_2005))
