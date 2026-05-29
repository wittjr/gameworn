"""
2011-12 NHL population report.

Tag sheet 'Population Report By Tag #'; schedule on
'Set Dates & Jersey Schedule' (per-team summary table + per-game block).
Ignored: 'Population Report By Player'.
"""

from memorabilia.meigray import toolbox
from memorabilia.meigray.registry import SheetManifest, YearSpec, register

MANIFEST_2011 = SheetManifest(
    tag='Population Report By Tag #',
    schedule=('Set Dates & Jersey Schedule',),
    omit=('Population Report By Player',),
)


def parse_tags_2011(wb, actual, manifest, report):
    return toolbox.read_tag_rows(wb, actual, manifest, report)


def parse_schedule_2011(wb, actual, manifest, report, tag_teams):
    return toolbox.read_combined_schedule(
        wb, actual, 'Set Dates & Jersey Schedule', report.season, tag_teams, 'Set Dates')


register('NHL', '2011-12', YearSpec(MANIFEST_2011, parse_tags_2011, parse_schedule_2011))
