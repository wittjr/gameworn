"""
2014-15 NHL population report.

Same single-column per-game schedule as 2013-14 ('Date, Opponent, Jersey,
Comments', weekday 'Sat, Jan 17, 2015' dates, PRESEASON/REGULAR SEASON
sections, 'End <Colour> Set N' markers). Use both: per-game list is
authoritative; parse_set_dates_table contributes preseason/summary.

PROMO / VERIZON / BANNER / HHOF / RETRO / KIOSK / GOLD-VIN / Stadium-Series
special sets (date in the colour, numeric or spelled-out) are handled by the
shared toolbox.apply_promo_color_dates corrections hook.

Tag sheet 'POP REPORT BY TAG NUMBER' has a leading blank column (handled via
header detection). Ignored: 'POP REPORT BY PLAYER'.
"""

from memorabilia.meigray import toolbox
from memorabilia.meigray.registry import (
    SheetManifest,
    YearSpec,
    register,
    sheet,
)

# L04228's Set column is the typo '56'; the colour says 'White Set 2'.
_SET_CORRECTIONS = {
    'L04228': ('2', "Set field in report is '56'"),
}

MANIFEST_2014 = SheetManifest(
    tag='POP REPORT BY TAG NUMBER',
    schedule=('SET DATES - JERSEY SCHEDULES',),
    omit=('POP REPORT BY PLAYER',),
)


def build_schedule_2014(wb, actual, manifest, season, tag_teams):
    rows = list(wb[sheet(actual, 'SET DATES - JERSEY SCHEDULES')]
                .iter_rows(values_only=True))
    schedule = toolbox.parse_set_dates_table(rows, season, tag_teams)
    schedule.update(toolbox.parse_pergame_schedule(rows, season, tag_teams))
    return schedule


def parse_tags_2014(rows, col, header_idx, headers, league, schedule, season, report):
    from memorabilia.models import MeiGrayEntry
    entries, total = toolbox.parse_entries_color_set(
        rows, col, header_idx, league, schedule, report, MeiGrayEntry
    )
    toolbox.enrich_vintage(entries, schedule)

    for e in entries:
        fix = _SET_CORRECTIONS.get(e.tag_number)
        if not fix:
            continue
        new_set, note = fix
        e.set_number = new_set
        e.games_worn = toolbox.lookup_games(
            schedule, e.team, e.color,
            toolbox.parse_set_number(new_set), set_raw=new_set)
        e.notes.setdefault('generated', []).append(note)

    return entries, total


SPEC_2014 = YearSpec(
    manifest=MANIFEST_2014,
    build_schedule=build_schedule_2014,
    parse_tags=parse_tags_2014,
    corrections=toolbox.apply_promo_color_dates,
)

register('NHL', '2014-15', SPEC_2014)
