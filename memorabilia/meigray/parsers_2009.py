"""
2009-10 NHL population report.

Tag sheet 'Pop Report Sorted By Inv Tag Nu'; schedule on
'Set Dates and Jersey Schedul' (per-team summary table with date ranges).
Ignored: 'Pop Report Sorted By Player'.
"""

from memorabilia.meigray import toolbox
from memorabilia.meigray.registry import SheetManifest, YearSpec, register

MANIFEST_2009 = SheetManifest(
    tag='Pop Report Sorted By Inv Tag Nu',
    schedule=('Set Dates and Jersey Schedul',),
    omit=('Pop Report Sorted By Player',),
)


def parse_tags_2009(wb, actual, manifest, report):
    return toolbox.read_tag_rows(wb, actual, manifest, report)


def parse_schedule_2009(wb, actual, manifest, report, tag_teams):
    rows = toolbox.read_schedule_sheet(wb, actual, 'Set Dates and Jersey Schedul')
    games = toolbox.parse_pergame_schedule_2009(rows, tag_teams)
    set_ranges = toolbox.parse_set_dates_table(rows, report.season, tag_teams, 'Set:')
    return games, set_ranges


register('NHL', '2009-10', YearSpec(MANIFEST_2009, parse_tags_2009, parse_schedule_2009))
