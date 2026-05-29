"""
2006-07 NHL population report.

Tag sheet 'Sorted By Tag Number'; schedule on 'Set Breakdowns' (per-game
two-block layout).
Ignored: 'Sorted By Team', 'Sorted By Player'.
"""

from memorabilia.meigray import toolbox
from memorabilia.meigray.registry import SheetManifest, YearSpec, register

MANIFEST_2006 = SheetManifest(
    tag='Sorted By Tag Number',
    schedule=('Set Breakdowns',),
    omit=('Sorted By Team', 'Sorted By Player'),
)


def parse_tags_2006(wb, actual, manifest, report):
    return toolbox.read_tag_rows(wb, actual, manifest, report)


def parse_schedule_2006(wb, actual, manifest, report, tag_teams):
    return toolbox.read_combined_schedule(
        wb, actual, 'Set Breakdowns', report.season, tag_teams , 'Set:')


register('NHL', '2006-07', YearSpec(MANIFEST_2006, parse_tags_2006, parse_schedule_2006))
