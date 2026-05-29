"""
2019-20 NHL population report (COVID-shortened season; Tampa Bay won
the bubble SCF vs Dallas -- neither is a MeiGray-tracked team here,
so no SCF entries).

Same single-column per-game schedule as 2018-19 ('Date, Opponent, Jersey,
Comments', weekday 'Mon, Sep. 16, 2019' dates with month period).

Schedule covers Boston, Columbus, Edmonton, Nashville, New Jersey,
Philadelphia, Washington.

Per-year fixups:
  * NJD - HRTG - 1, NJD - HRTG - 2 ('heritage' jersey rows in NJ schedule
    ending 'End Heritage Set 1' on 12/20 and 'End Heritage Set 2' on
    1/7). jersey_home_away('heritage')='home' so the per-game parser
    leaks them into NJ home Set N; lift them out.
  * NJD - 2000, NSH - WCS via apply_promo_color_dates extras (date in
    colour; NSH - WCS uses multi-date '... worn January 18, 2020 &
    February 16, 2020').
  * Philadelphia Set 3: the 2019-20 schedule has no End Set 3 markers
    (the COVID pause + bubble restart broke the normal pattern). Pop
    report Set 3 colours indicate which sections each jersey was worn
    in: 'Set 3 Regular Season' = post-End-Set-2 March games, '/ Round
    Robin' = Exhibition + Round Robin section rows, '/ Playoffs' =
    Playoffs section rows. Parse the colour string to build per-tag
    games_worn from the right sections.

Tag sheet 'POP REPORT BY TAG NUMBER' has TAG # at column offset 0;
ignored 'POP REPORT BY PLAYER'.
"""

import re

from memorabilia.meigray import toolbox
from memorabilia.meigray.registry import (
    SheetManifest,
    YearSpec,
    register,
    sheet,
)

# NJ Devils Heritage sets (from schedule's 'End Heritage Set 1' / 'End
# Heritage Set 2' markers on 'heritage' jersey rows).
_NJD_HRTG_1_DATES = ('2019-11-30', '2019-12-20')
_NJD_HRTG_2_DATES = ('2020-01-07',)

# Per-year promo prefixes for date-in-colour event sets.
_NJD_2000_RE = re.compile(r'^NJD\s*-\s*2000\b', re.IGNORECASE)
_NSH_WCS_RE = re.compile(r'^NSH\s*-\s*WCS\b', re.IGNORECASE)
_PROMO_EXTRAS = {
    _NJD_2000_RE: '2000 Stanley Cup 20th Anniversary',
    _NSH_WCS_RE: 'Winter Classic Style',
}

# Philadelphia Set 3 phase tokens (parsed from colour string).
_PHI_REGULAR_RE = re.compile(r'regular\s+season', re.IGNORECASE)
_PHI_ROUND_ROBIN_RE = re.compile(r'round[\s-]+robin', re.IGNORECASE)
_PHI_PLAYOFFS_RE = re.compile(r'playoffs?', re.IGNORECASE)
_PHI_SKILLS_RE = re.compile(r'skills\s+competition', re.IGNORECASE)
# Section header text in the PHI schedule date column.
_PHI_EXHIBITION_HDR = 'exhibition'
_PHI_ROUND_ROBIN_HDR = 'round-robin'
_PHI_PLAYOFFS_HDR = 'playoffs'

MANIFEST_2019 = SheetManifest(
    tag='POP REPORT BY TAG NUMBER',
    schedule=('SET DATES - JERSEY SCHEDULES',),
    omit=('POP REPORT BY PLAYER',),
)


def _attach_njd_heritage(schedule):
    """Lift NJ Heritage dates out of NJ home Set N buckets and stash
    them under per-set heritage keys for NJD - HRTG - 1 / -2 entries."""
    bad = set(_NJD_HRTG_1_DATES) | set(_NJD_HRTG_2_DATES)
    for key, val in list(schedule.items()):
        if (len(key) == 3 and key[0] == 'new jersey devils'
                and key[1] == 'home' and isinstance(val, list)):
            schedule[key] = [g for g in val if g.get('date') not in bad]
    schedule[('heritage', 'new jersey devils', 1)] = [
        {'type': 'worn', 'date': d} for d in _NJD_HRTG_1_DATES]
    schedule[('heritage', 'new jersey devils', 2)] = [
        {'type': 'worn', 'date': d} for d in _NJD_HRTG_2_DATES]


def _build_phi_set3_buckets(rows, schedule):
    """Walk the Philadelphia 2019-20 block and bucket the orphaned
    post-End-Set-2 rows by phase (regular_set3, exhibition, round_robin).
    Playoffs rows are already routed by the toolbox's PLAYOFFS section
    handling to ('playoffs', team, lane), so we don't duplicate them.

    Stores keys ('phi19_set3', phase, lane) -> list of {'date': iso}.
    """
    # Locate PHI header and next-team header.
    phi_start = None
    phi_end = len(rows)
    for i, r in enumerate(rows):
        if not r:
            continue
        for c in r:
            if c is None:
                continue
            s = str(c).strip().upper()
            if s.startswith('PHILADELPHIA FLYERS'):
                phi_start = i
                break
            if (phi_start is not None and i > phi_start
                    and re.match(r'^[A-Z][A-Z ./]+\d{4}', s)):
                phi_end = i
                break
        if phi_start is not None and phi_end != len(rows):
            break
    if phi_start is None:
        return

    # Identify section header rows and End <Color> Set 2 markers.
    exhibition_row = None
    round_robin_row = None
    playoffs_row = None
    end_set2 = {'home': None, 'away': None, 'third': None}
    # Detect the date column from the local header row.
    date_col = 0
    for ri in range(phi_start, min(phi_start + 5, phi_end)):
        r = rows[ri]
        for j, c in enumerate(r or ()):
            if c is not None and str(c).strip().upper() == 'DATE':
                date_col = j
                break

    for ri in range(phi_start + 1, phi_end):
        r = rows[ri]
        if not r:
            continue
        cell = r[date_col] if date_col < len(r) else None
        if cell is not None:
            label = str(cell).strip().lower().replace(' ', '')
            if label == _PHI_EXHIBITION_HDR:
                exhibition_row = ri
                continue
            if label == _PHI_ROUND_ROBIN_HDR:
                round_robin_row = ri
                continue
            if label == _PHI_PLAYOFFS_HDR:
                playoffs_row = ri
                continue
        # Notes column for End markers (col offset 3 in this schedule).
        note = ''
        if len(r) > date_col + 3 and r[date_col + 3] is not None:
            note = str(r[date_col + 3]).strip()
        if note:
            m = toolbox._END_COLOR_RE.search(note)
            if m and int(m.group(2)) == 2:
                lane_e = toolbox.jersey_home_away(m.group(1))
                end_set2[lane_e] = ri
            m = toolbox._END_THIRD_RE.search(note)
            if m and int(m.group(1)) == 2:
                end_set2['third'] = ri

    def _phase_for(ri):
        if playoffs_row is not None and ri > playoffs_row:
            return None  # already in ('playoffs', team, lane)
        if round_robin_row is not None and ri > round_robin_row:
            return 'round_robin'
        if exhibition_row is not None and ri > exhibition_row:
            return 'exhibition'
        # Pre-EXHIBITION post-End-Set-2 rows -> regular_set3 for the row's lane.
        return 'regular_set3'

    buckets = {}
    for ri in range(phi_start + 1, phi_end):
        r = rows[ri]
        if not r:
            continue
        iso = toolbox._parse_team_set_date(
            r[date_col] if date_col < len(r) else None)
        if not iso:
            continue
        jersey = ''
        if len(r) > date_col + 2 and r[date_col + 2] is not None:
            jersey = str(r[date_col + 2]).strip()
        if not jersey:
            continue
        lane = toolbox.jersey_home_away(jersey)
        phase = _phase_for(ri)
        if phase is None:
            continue
        # regular_set3 only applies AFTER this lane's End Set 2 marker.
        if phase == 'regular_set3':
            mark = end_set2.get(lane)
            if mark is None or ri <= mark:
                continue
            # And only if EXHIBITION hasn't started yet.
            if exhibition_row is not None and ri >= exhibition_row:
                continue
        buckets.setdefault((phase, lane), []).append({'date': iso})

    for (phase, lane), games in buckets.items():
        schedule[('phi19_set3', phase, lane)] = games

def _build_caps_third_set3(rows, schedule):
    """Washington Capitals third jersey rows in the schedule have 'Set 3' in
    the colour but no End Set 3 marker. Build a synthetic bucket of their
    dates for use in parsing Caps Set 3 entries."""
    # Locate CAPS header and next-team header.
    caps_start = None
    caps_end = len(rows)
    third_set2_start = None
    third_set2_end = caps_end
    games = []
    
    for i, r in enumerate(rows):
        if (third_set2_start is not None and i >= third_set2_start and i<= third_set2_end and r[3] is not None and r[3].strip().upper() == 'THIRD'):
            iso = toolbox._parse_team_set_date(r[1])
            if iso:
                games.append({'date': iso})
        if (third_set2_start is not None and i >= third_set2_start and i<= third_set2_end):
            if (r[4] is not None and str(r[4]).strip().upper() == 'END THIRD SET 2'):
                break
        if (caps_start is not None and i > caps_start and i<= caps_end):
            if (r[4] is not None and str(r[4]).strip().upper() == 'END THIRD SET 1'):
                third_set2_start = i+1
        if not r:
            continue
        for c in r:
            if c is None:
                continue
            s = str(c).strip().upper()
            if s.startswith('WASHINGTON CAPITALS'):
                caps_start = i
                break
            if (caps_start is not None and i > caps_start
                    and re.match(r'^[A-Z][A-Z ./]+\d{4}', s)):
                caps_end = i
                break
        if caps_start is not None and caps_end != len(rows):
            break
    if caps_start is None:
        return

    schedule[('washington capitals', 'third', 2)] = games

def build_schedule_2019(wb, actual, manifest, season, tag_teams):
    rows = list(wb[sheet(actual, 'SET DATES - JERSEY SCHEDULES')]
                .iter_rows(values_only=True))
    schedule = toolbox.parse_set_dates_table(rows, season, tag_teams)
    schedule.update(toolbox.parse_pergame_schedule(rows, season, tag_teams))
    _attach_njd_heritage(schedule)
    _build_phi_set3_buckets(rows, schedule)
    _build_caps_third_set3(rows, schedule)
    return schedule


def _apply_njd_heritage(entries, schedule):
    for e in entries:
        if e.team != 'New Jersey Devils':
            continue
        if e.set_number not in ('NJD - HRTG - 1', 'NJD - HRTG - 2'):
            continue
        if toolbox.is_game_issued(e.color) or toolbox.is_warmup_only(e.color):
            continue
        set_num = 1 if e.set_number == 'NJD - HRTG - 1' else 2
        dates = schedule.get(('heritage', 'new jersey devils', set_num), [])
        e.games_worn = list(dates)
        gen = e.notes.setdefault('generated', [])
        label = f'Heritage Set {set_num}'
        if label not in gen:
            gen.append(label)


def _apply_phi_set3(entries, schedule):
    """Assign Philadelphia Flyers Set 3 entries from per-phase buckets.
    Phase tokens in the colour string:
      - 'Regular Season' -> the orphaned March 5/7/10 Orange rows (lane home)
      - 'Round Robin'    -> the Exhibition (7/28) + Round-Robin section rows
      - 'Playoffs'       -> the PLAYOFFS-section rows
    Lane comes from the leading colour word (Orange=home, White=away)."""
    for e in entries:
        if e.team != 'Philadelphia Flyers' or e.set_number != '3':
            continue
        if toolbox.is_game_issued(e.color) or toolbox.is_warmup_only(e.color):
            continue
        if _PHI_SKILLS_RE.search(e.color):
            continue
        # Phase from colour string (after 'Set 3').
        text = e.color
        m_anchor = re.search(r'set\s*3', text, re.IGNORECASE)
        phase_text = text[m_anchor.end():] if m_anchor else text
        has_regular = bool(_PHI_REGULAR_RE.search(phase_text))
        has_round_robin = bool(_PHI_ROUND_ROBIN_RE.search(phase_text))
        has_playoffs = bool(_PHI_PLAYOFFS_RE.search(phase_text))
        if not (has_regular or has_round_robin or has_playoffs):
            continue
        lane = toolbox.jersey_home_away(e.color)
        dates = []
        labels = []
        if has_regular:
            for g in schedule.get(
                    ('phi19_set3', 'regular_set3', lane), []):
                dates.append(g['date'])
            labels.append('Set 3 Regular Season')
        if has_round_robin:
            for g in schedule.get(
                    ('phi19_set3', 'exhibition', lane), []):
                dates.append(g['date'])
            for g in schedule.get(
                    ('phi19_set3', 'round_robin', lane), []):
                dates.append(g['date'])
            labels.append('Round Robin')
        if has_playoffs:
            for g in schedule.get(
                    ('playoffs', 'philadelphia flyers', lane), []):
                dates.append(g['date'])
            labels.append('Playoffs')
        # Dedupe and sort.
        seen = set()
        ordered = []
        for d in sorted(dates):
            if d in seen:
                continue
            seen.add(d)
            ordered.append({'type': 'worn', 'date': d})
        if not ordered:
            continue
        e.games_worn = ordered
        gen = e.notes.setdefault('generated', [])
        label = ' / '.join(labels)
        if label not in gen:
            gen.append(label)


def parse_tags_2019(rows, col, header_idx, headers, league, schedule, season, report):
    from memorabilia.models import MeiGrayEntry
    entries, total = toolbox.parse_entries_color_set(
        rows, col, header_idx, league, schedule, report, MeiGrayEntry
    )
    toolbox.enrich_vintage(entries, schedule)
    _apply_njd_heritage(entries, schedule)
    _apply_phi_set3(entries, schedule)
    return entries, total


def corrections_2019(entries):
    toolbox.apply_promo_color_dates(entries, extras=_PROMO_EXTRAS)


SPEC_2019 = YearSpec(
    manifest=MANIFEST_2019,
    build_schedule=build_schedule_2019,
    parse_tags=parse_tags_2019,
    corrections=corrections_2019,
)

register('NHL', '2019-20', SPEC_2019)
