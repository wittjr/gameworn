"""
2007-08 NHL population report.

Tag sheet 'Sorted By Tag#'; schedule on 'Set Breakdowns' (per-game two-block
layout, same as 2006-07).
Ignored: 'Sorted By Player'.
"""

from memorabilia.meigray import toolbox
from memorabilia.meigray.registry import SheetManifest, YearSpec, register

MANIFEST_2007 = SheetManifest(
    tag='Sorted By Tag#',
    schedule=('Set Breakdowns',),
    omit=('Sorted By Player',),
)


def parse_tags_2007(wb, actual, manifest, report):
    return toolbox.read_tag_rows(wb, actual, manifest, report)


def parse_schedule_2007(wb, actual, manifest, report, tag_teams):
    return toolbox.read_combined_schedule(
        wb, actual, 'Set Breakdowns', report.season, tag_teams, 'Set:')


register('NHL', '2007-08', YearSpec(MANIFEST_2007, parse_tags_2007, parse_schedule_2007))
