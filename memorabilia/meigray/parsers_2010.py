"""
2010-11 NHL population report.

Tag sheet 'Pop Report - Sorted by Inv Tag'; schedule on 'Jersey Set Dates'
(per-team summary table + per-game block).
Ignored: 'Pop Report - Sorted by Player'.
"""

from memorabilia.meigray import toolbox
from memorabilia.meigray.registry import SheetManifest, YearSpec, register

MANIFEST_2010 = SheetManifest(
    tag='Pop Report - Sorted by Inv Tag',
    schedule=('Jersey Set Dates',),
    omit=('Pop Report - Sorted by Player',),
)


def parse_tags_2010(wb, actual, manifest, report):
    return toolbox.read_tag_rows(wb, actual, manifest, report)


def parse_schedule_2010(wb, actual, manifest, report, tag_teams):
    games, set_ranges = toolbox.read_combined_schedule(
    wb, actual, 'Jersey Set Dates', report.season, tag_teams, 'Set')
    # The schedule sheet does not label the playoff section.
    for g in games:
        if g['date'] >= '2011-04-13':
            g['game_type'] = 'Playoffs'
        elif g['date'] < '2010-10-07':
            g['game_type'] = 'Preseason'
        else:
            g['game_type'] = 'Regular Season'
    return games, set_ranges


register('NHL', '2010-11', YearSpec(MANIFEST_2010, parse_tags_2010, parse_schedule_2010))
