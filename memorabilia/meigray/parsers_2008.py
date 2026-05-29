"""
2008-09 NHL population report.

Tag sheet 'Pop Rept By Tag Number'; schedule on 'Set Dates' (per-team summary
table with date ranges per set; no per-game data).
Ignored: 'Pop Rept By Player'.
"""

from memorabilia.meigray import toolbox
from memorabilia.meigray.registry import SheetManifest, YearSpec, register

MANIFEST_2008 = SheetManifest(
    tag='Pop Rept By Tag Number',
    schedule=('Set Dates',),
    omit=('Pop Rept By Player',),
)


def parse_tags_2008(wb, actual, manifest, report):
    return toolbox.read_tag_rows(wb, actual, manifest, report)


def parse_schedule_2008(wb, actual, manifest, report, tag_teams):
    return toolbox.read_combined_schedule(
        wb, actual, 'Set Dates', report.season, tag_teams, 'Set:')


register('NHL', '2008-09', YearSpec(MANIFEST_2008, parse_tags_2008, parse_schedule_2008))
