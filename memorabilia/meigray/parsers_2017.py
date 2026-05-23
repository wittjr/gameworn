"""
2017-18 NHL population report.

Same single-column per-game schedule as 2016-17 ('Date, Opponent, Jersey,
Comments', weekday 'Mon, Sep 18, 2017' dates, PRESEASON/REGULAR SEASON/
PLAYOFFS sections, 'End <Colour> Set N' markers). Use both: per-game list
is authoritative; parse_set_dates_table contributes the preseason block.

Schedule covers the eight MeiGray-tracked teams: Boston, Columbus, Edmonton,
Nashville, New Jersey, Philadelphia, Vegas (expansion year), Washington.

Toolbox handles PRESEASON / PLAYOFFS section detection and SCF jerseys
generically this year forward. Per-year fixups here:
  * Vegas playoff date 'Fr, Apr 13, 2018' typo (truncated weekday).
  * NJD - PE (Patrik Elias Retirement Night 2/24/18) and PHI - EL (Eric
    Lindros Retirement Night 1/18/18) -- per-event sets with date in the
    colour, same shape as 2015-16 MB-*. Wired via the apply_promo_color_dates
    `extras` hook (per-year prefix) so the date is also excluded from the
    team's regular set games.
  * VGK - PO ('Vegas Golden Knights' dedicated playoff jersey) -- assign
    dates from the shared ('playoffs', team, lane) key built by the toolbox
    from rows in the schedule's PLAYOFFS section.

Tag sheet 'POP REPORT BY TAG NUMBER' has TAG # at column offset 0 (no
leading blank column); detect_col_offset handles that. Ignored:
'POP REPORT BY PLAYER ' (trailing space).
"""

import re

from memorabilia.meigray import toolbox
from memorabilia.meigray.registry import (
    SheetManifest,
    YearSpec,
    register,
    sheet,
)

# Truncated weekday 'Fr' instead of 'Fri' on a Vegas playoff row.
_DATE_CORRECTIONS = {
    'Fr, Apr 13, 2018': 'Fri, Apr 13, 2018',
}

# Per-year promo-set prefixes (one-game-only events with the date in the
# colour, exclude that date from the team's regular set games).
_NJD_PE_RE = re.compile(r'^NJD\s*-\s*PE\b', re.IGNORECASE)
_PHI_EL_RE = re.compile(r'^PHI\s*-\s*EL\b', re.IGNORECASE)
# WSH - SS is two distinct jerseys: 'Stadium Series - Extra Jersey, Not
# Used' (no date, stays dateless) and 'Stadium Series Style - Worn
# 3/20/2018' (date in colour). The shared apply_promo_color_dates handler
# dates the latter via the colour and skips the former (no date to find).
_WSH_SS_RE = re.compile(r'^WSH\s*-\s*SS\b', re.IGNORECASE)
_PROMO_EXTRAS = {
    _NJD_PE_RE: 'Patrik Elias Retirement Night',
    _PHI_EL_RE: 'Eric Lindros Retirement Night',
    _WSH_SS_RE: 'Stadium Series Style',
}

MANIFEST_2017 = SheetManifest(
    tag='POP REPORT BY TAG NUMBER',
    schedule=('SET DATES - JERSEY SCHEDULES',),
    omit=('POP REPORT BY PLAYER',),
)


_VGK_INAUGURAL_DATE = '2017-10-06'

# Boston Willie O'Ree 60th Anniversary Patch (BOS - WO): 7 Black games
# between 'End Black Set 1' (12/18/17) and 'End Set 2 w/ O'Ree Patch -
# 6 Game Set' (1/17/18), including the originally-scheduled 1/4 game
# that was rescheduled to 4/8/18.
_BOS_WO_DATES = ('2017-12-21', '2017-12-23', '2017-12-27',
                 '2018-01-06', '2018-01-15', '2018-01-17',
                 '2018-04-08')

# Columbus Blue Jackets 'Online Auction' (CBJ-Auction) and 'In Arena
# Auction' (CBJ-Arena) sets per the schedule's 'White Auction' / 'Blue
# Auction' jersey labels with 'End <Color> Auction Set - N Game Set'
# markers.
_CBJ_WHITE_AUCTION = ('2017-11-27', '2017-12-02', '2017-12-08', '2017-12-16')
_CBJ_BLUE_AUCTION = ('2017-11-24', '2017-11-28', '2017-12-01',
                     '2017-12-05', '2017-12-09')


def _apply_vgk_inaugural(entries):
    """Vegas Golden Knights' inaugural game (10/6/17): blank-set jerseys
    with 'First Game in Golden Knights History' in the colour were worn
    in part of the inaugural game (1st & 2nd Period Only / 3rd Period
    Only / Worn Entire Game). Assign 10/6 (non-GI / non-Warm-Up Only) and
    exclude that date from Vegas regular Set 1 jerseys, mirroring the
    promo-exclusion pattern."""
    for e in entries:
        if e.team != 'Vegas Golden Knights':
            continue
        if str(e.set_number).strip():
            continue
        if 'first game in golden knights history' not in e.color.lower():
            continue
        if toolbox.is_game_issued(e.color) or toolbox.is_warmup_only(e.color):
            continue
        e.games_worn = [{'type': 'worn',
                         'date': _VGK_INAUGURAL_DATE}]
        gen = e.notes.setdefault('generated', [])
        note = 'Golden Knights Inaugural Game'
        if note not in gen:
            gen.append(note)

    for e in entries:
        if e.team != 'Vegas Golden Knights':
            continue
        if not e.games_worn:
            continue
        if not str(e.set_number).strip().isdigit():
            continue
        # Skip jerseys that will be cleared by the global GI / flag passes
        # so the exclusion note doesn't mislead on a tag that ends up
        # dateless anyway.
        if (toolbox.is_game_issued(e.color)
                or toolbox.color_flag_text(e.color)):
            continue
        if not any(g.get('date') == _VGK_INAUGURAL_DATE for g in e.games_worn):
            continue
        e.games_worn = [g for g in e.games_worn
                        if g.get('date') != _VGK_INAUGURAL_DATE]
        gen = e.notes.setdefault('generated', [])
        note = (f'Excluded {_VGK_INAUGURAL_DATE} '
                '(worn as Inaugural Game patch jersey)')
        if note not in gen:
            gen.append(note)


def _strip_special_event_dates(schedule):
    """Remove dates that belong to per-event special sets (Boston O'Ree
    set, Columbus Blue/White Auction sets) from the regular team home/away
    schedule buckets they default-leaked into. Each special set is then
    assigned to its tag entries separately in parse_tags_2017."""
    bad_bos = set(_BOS_WO_DATES)
    bad_cbj = set(_CBJ_WHITE_AUCTION) | set(_CBJ_BLUE_AUCTION)
    for key, val in list(schedule.items()):
        if not (len(key) == 3 and isinstance(val, list)):
            continue
        if key[0] == 'boston bruins' and key[1] in ('home', 'away'):
            schedule[key] = [g for g in val if g.get('date') not in bad_bos]
        elif key[0] == 'columbus blue jackets' and key[1] in ('home', 'away'):
            schedule[key] = [g for g in val if g.get('date') not in bad_cbj]


def _apply_bos_oree(entries):
    """Boston BOS - WO ('Black w/ Willie O'Ree 60th Anniversary Patch'):
    assign the 7 dates (6 games in the O'Ree-patch window + the rescheduled
    1/4 -> 4/8 game). Non-GI / non-Warm-Up Only only."""
    for e in entries:
        if e.team != 'Boston Bruins' or e.set_number != 'BOS - WO':
            continue
        if (toolbox.is_game_issued(e.color) or toolbox.is_warmup_only(e.color)):
            continue
        e.games_worn = [{'type': 'worn', 'date': d} for d in _BOS_WO_DATES]
        gen = e.notes.setdefault('generated', [])
        note = "Willie O'Ree 60th Anniversary"
        if note not in gen:
            gen.append(note)


def _apply_cbj_auctions(entries):
    """Columbus CBJ-Auction (White Auction, 4 dates) and CBJ-Arena (Blue
    Auction, 5 dates) per the schedule's 'Auction' jersey labels. Non-GI
    only. CBJ-Arena entries already pick up dates via the comment-date
    extraction, but stripping the schedule keeps the regular set 1 lookup
    clean and a label note is added."""
    for e in entries:
        if e.team != 'Columbus Blue Jackets':
            continue
        if toolbox.is_game_issued(e.color) or toolbox.is_warmup_only(e.color):
            continue
        if e.set_number == 'CBJ-Auction':
            e.games_worn = [{'type': 'worn', 'date': d}
                            for d in _CBJ_WHITE_AUCTION]
            gen = e.notes.setdefault('generated', [])
            if 'Online Auction Set' not in gen:
                gen.append('Online Auction Set')
        elif e.set_number == 'CBJ-Arena':
            gen = e.notes.setdefault('generated', [])
            if 'In Arena Auction Set' not in gen:
                gen.append('In Arena Auction Set')


_LABEL_NOTES = {
    'VGK - VS': 'Vegas Strong Warm-Up Only',
    'EDM - YSC': 'Young Stars Classic prospect tournament',
    'NJD - DEV': 'Development Camp Only',
}

# Two blank-set Vegas tags whose colour clearly says 'Set 1' (the third
# blank-set entry P06019 is GI and stays dateless regardless).
_SET_CORRECTIONS = {
    'P05832': ('1', "Set field is blank, but colour says 'White Set 1'"),
    'P05849': ('1', "Set field is blank, but colour says 'White Set 1'"),
}

# Per-tag date assignments for entries whose Comments field identifies a
# specific game that the generic schedule lookup can't resolve.
# P06094 Miller -- 'Worn in Game 4 of the 2018 Stanley Cup Final' (6/4/18).
# (P07213 Neal has the same 'White Stanley Cup Final Set 2' colour but no
# Comment, so it stays dateless.)
_PER_TAG_DATES = {
    'P06094': (('2018-06-04',),
               'Comment: Worn in Game 4 of the 2018 Stanley Cup Final'),
}

# Per-tag colour-string overrides for typos / wording variants that defeat
# the global flag/lookup logic. Applied before global passes so the
# corrected colour drives is_preseason_only / is_warmup_only / GI checks.
# Stored as (corrected_color, note).
_COLOR_CORRECTIONS = {
    'P05932': ('White Preseason Only w/A',
               "Colour typo in report: 'Whire Preseason Only w/A'"),
    'P05941': ('White Preseason Only',
               "Colour typo in report: 'White Presaeson Only'"),
    'P06032': ('Gray Preseason Only (A removed)',
               "Colour in report omits 'Only': 'Gray Preseason (A removed)'"),
}


def _apply_labels(entries):
    """Add generated-note labels to per-event special sets that stay
    dateless by design, so the reason is captured in the data."""
    for e in entries:
        label = _LABEL_NOTES.get(e.set_number)
        if not label:
            continue
        gen = e.notes.setdefault('generated', [])
        if label not in gen:
            gen.append(label)


def _apply_set_corrections(entries, schedule):
    """Per-tag set corrections for mis-labeled tags (cosmetic + assigns the
    right schedule dates)."""
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


def _apply_per_tag_dates(entries):
    """Per-tag date assignments for entries whose Comments specify a game
    the generic schedule lookup misses (e.g. a one-off Stanley Cup Final
    jersey without a matching SCF schedule row)."""
    for e in entries:
        fix = _PER_TAG_DATES.get(e.tag_number)
        if not fix:
            continue
        dates, note = fix
        e.games_worn = [{'type': 'worn', 'date': d} for d in dates]
        e.notes.setdefault('generated', []).append(note)


def _apply_vgk_playoffs(entries, schedule):
    """VGK - PO dedicated playoff jerseys (74 entries). Lane is parsed from
    the colour (Gray->home, White->away). Use the toolbox-built playoffs
    key. GI/Warm-Up Only variants stay dateless."""
    home = schedule.get(('playoffs', 'vegas golden knights', 'home'), [])
    away = schedule.get(('playoffs', 'vegas golden knights', 'away'), [])
    by_lane = {'home': home, 'away': away}
    for e in entries:
        if e.team != 'Vegas Golden Knights' or e.set_number != 'VGK - PO':
            continue
        if toolbox.is_game_issued(e.color) or toolbox.is_warmup_only(e.color):
            continue
        lane = toolbox.jersey_home_away(e.color)
        dates = by_lane.get(lane, [])
        e.games_worn = [{'type': 'worn', 'date': g['date']} for g in dates]
        gen = e.notes.setdefault('generated', [])
        note = 'Playoff dates only'
        if note not in gen:
            gen.append(note)


def build_schedule_2017(wb, actual, manifest, season, tag_teams):
    rows = list(wb[sheet(actual, 'SET DATES - JERSEY SCHEDULES')]
                .iter_rows(values_only=True))
    schedule = toolbox.parse_set_dates_table(rows, season, tag_teams)
    schedule.update(toolbox.parse_pergame_schedule(
        rows, season, tag_teams, date_corrections=_DATE_CORRECTIONS))
    _strip_special_event_dates(schedule)
    return schedule


def _apply_color_corrections(entries):
    """Per-tag colour-string overrides. Must run before the global GI / flag
    passes so corrected colours drive those checks."""
    for e in entries:
        fix = _COLOR_CORRECTIONS.get(e.tag_number)
        if not fix:
            continue
        new_color, note = fix
        e.color = new_color
        e.notes.setdefault('generated', []).append(note)


def parse_tags_2017(rows, col, header_idx, headers, league, schedule, season, report):
    from memorabilia.models import MeiGrayEntry
    entries, total = toolbox.parse_entries_color_set(
        rows, col, header_idx, league, schedule, report, MeiGrayEntry
    )
    _apply_color_corrections(entries)
    toolbox.enrich_vintage(entries, schedule)
    _apply_vgk_playoffs(entries, schedule)
    _apply_vgk_inaugural(entries)
    _apply_bos_oree(entries)
    _apply_cbj_auctions(entries)
    _apply_labels(entries)
    _apply_set_corrections(entries, schedule)
    _apply_per_tag_dates(entries)
    return entries, total


def corrections_2017(entries):
    toolbox.apply_promo_color_dates(entries, extras=_PROMO_EXTRAS)


SPEC_2017 = YearSpec(
    manifest=MANIFEST_2017,
    build_schedule=build_schedule_2017,
    parse_tags=parse_tags_2017,
    corrections=corrections_2017,
)

register('NHL', '2017-18', SPEC_2017)
