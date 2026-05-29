"""
2007-08 NHL population report.

Same per-game two-block 'Set Breakdowns' schedule as 2006-07 (block A is
Preseason, block B Regular Season -- the generalized parser accumulates them
into the lane sets, advancing on End-Set markers). Tag sheet is
'Sorted By Tag#' and inserts a 'Version' column before Customizations; the
generic parser locates the comment column from the header.
Ignored: 'Sorted By Player'.
"""

from memorabilia.meigray import toolbox
from memorabilia.meigray.registry import (
    SheetManifest,
    YearSpec,
    register,
    sheet,
)

MANIFEST_2007 = SheetManifest(
    tag='Sorted By Tag#',
    schedule=('Set Breakdowns',),
    omit=('Sorted By Player',),
)


# Per-file note fixes for the Set Breakdowns tab. Nashville's set-1 end
# marker has the wrong word order with 'Reverse Jersey' merged on; correct it
# to the standard 'End <Colour> Set N' form so the away set advances.
_NOTE_CORRECTIONS = {
    'End Set 1 White   Reverse Jersey': 'End White Set 1',
}

# Per-file Set-column corrections: {tag: (corrected_set, note)}.
_SET_CORRECTIONS = {
    # E02111 colour is 'Black Set 1 w/C' but the Set column is blank.
    'E02111': ('1', 'Population Report has no set, but assuming it should be set 1'),
}


def build_schedule_2007(wb, actual, manifest, season, tag_teams):
    rows = list(wb[sheet(actual, 'Set Breakdowns')].iter_rows(values_only=True))
    # Use both: the per-game list (exact dates, End-Set markers) is
    # authoritative; the 'Set N Home/Away' summary table fills any (team, set)
    # the per-game block didn't resolve.
    schedule = toolbox.parse_set_dates_table(rows, season, tag_teams)
    schedule.update(toolbox.parse_team_set_dates(
        rows, season, tag_teams, note_corrections=_NOTE_CORRECTIONS))
    return schedule


def parse_tags_2007(rows, col, header_idx, headers, league, schedule, season, report):
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


SPEC_2007 = YearSpec(
    manifest=MANIFEST_2007,
    build_schedule=build_schedule_2007,
    parse_tags=parse_tags_2007,
)

register('NHL', '2007-08', SPEC_2007)
