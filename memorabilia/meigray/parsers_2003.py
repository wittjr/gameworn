"""
2003-04 NHL population report.

Tag sheet ('Sorted By Tag #'): TAG #, Team, Player, JSY #, Jersey Type, Set,
  Size, Customizations -- same column shape as 2002, generic color/set parser.

Diverges from 2002-03:
  - The home/road date ranges are split across TWO tabs:
      'Preseason and 1st Reg Sets'  -> sets 1 (preseason) + 2 (1st reg)
      '2nd & 3rd Reg + SCP Sets'    -> sets 3 (2nd reg) + 4 (3rd reg / PO)
  - Range-row team labels now embed a color
    ('Anaheim - Home Jade', 'Atlanta - Road White'); resolve_teams already
    strips the '- Home/Road ...' suffix so team resolution is unaffected.
  - 'Third Jersey Breakdown' is the legacy thirds tab (same as 2002's
    'Third Jersey Dates').
  - Adds 'Vintage Sets' and 'Heritage Classic & MegaStars' -- comma-date /
    free-text tabs with their own keying. DEFERRED: declared in the manifest
    so the sheet-accounting check passes, but not yet parsed, so Vintage /
    Heritage / MegaStars jerseys are currently dateless and surface in the
    dry-run warnings (next iteration).
Ignored: 'Sorted By Player' (alternate sort of the tag data).
"""

from memorabilia.meigray import toolbox
from memorabilia.meigray.registry import (
    SheetManifest,
    YearSpec,
    register,
    sheet,
)

MANIFEST_2003 = SheetManifest(
    tag='Sorted By Tag #',
    schedule=(
        'Preseason and 1st Reg Sets',
        '2nd & 3rd Reg + SCP Sets',
        'Third Jersey Breakdown',
        'Vintage Sets',
        'Heritage Classic & MegaStars',
    ),
    omit=('Sorted By Player',),
)

_RANGE_TABS = ('Preseason and 1st Reg Sets', '2nd & 3rd Reg + SCP Sets')


def build_schedule_2003(wb, actual, manifest, season, tag_teams):
    team_index = toolbox.build_team_index(tag_teams)
    schedule = {}

    ranges = {}
    counts = {}
    for tab in _RANGE_TABS:
        rows = list(wb[sheet(actual, tab)].iter_rows(values_only=True))
        r, c = toolbox.parse_range_rows(rows, team_index)
        ranges.update(r)
        counts.update(c)
    if ranges:
        schedule.update(toolbox.schedule_from_ranges(ranges, counts, season))

    thirds_rows = list(
        wb[sheet(actual, 'Third Jersey Breakdown')].iter_rows(values_only=True)
    )
    schedule.update(toolbox.parse_legacy_thirds(thirds_rows, season, tag_teams))

    # Vintage Sets: keyed (team_lower, vintage_color, set_num), namespaced
    # under 'vintage' so it never collides with the regular schedule.
    vint_rows = list(wb[sheet(actual, 'Vintage Sets')].iter_rows(values_only=True))
    for (team, color, set_num), dates in toolbox.parse_vintage_sheet(
            vint_rows, season, tag_teams).items():
        schedule[('vintage', team, color, set_num)] = dates

    # 'Heritage Classic & MegaStars' still deferred -- see module docstring.
    return schedule


def parse_tags_2003(rows, col, header_idx, headers, league, schedule, season, report):
    from memorabilia.models import MeiGrayEntry
    entries, total = toolbox.parse_entries_color_set(
        rows, col, header_idx, league, schedule, report, MeiGrayEntry
    )
    # Vintage jerseys get their set-level dates from the Vintage Sets sheet;
    # per-jersey 'Worn ...' comment dates are added globally by the orchestrator.
    toolbox.enrich_vintage(entries, schedule)
    return entries, total


SPEC_2003 = YearSpec(
    manifest=MANIFEST_2003,
    build_schedule=build_schedule_2003,
    parse_tags=parse_tags_2003,
)

register('NHL', '2003-04', SPEC_2003)
