"""
Shared, format-agnostic primitives for parsing MeiGray population reports.

Nothing in here is year-specific. Per-year parsers (parsers_YYYY.py) compose
these building blocks; the registry decides which parsers a given season uses.
"""

import io
import re
from datetime import date, datetime
import sys

import openpyxl

_PRE_PLUS_RE = re.compile(r'(?:all\s+)?pre(?:season)?\s*\+\s*(.+)', re.IGNORECASE)

_TAG_HEADERS = {'TAG #', 'TAG NUMBER', 'TAG#'}

COLOR_TO_SCHEDULE = [
    ('third', 'Third'),
    ('black', 'Black'),
    ('white', 'White'),
    ('blue', 'Blue'),
    ('green', 'Green'),
    ('orange', 'Orange'),
    ('gold', 'Gold'),
    ('red', 'Red'),
    ('yellow', 'Yellow'),
    ('stadium series', 'SS'),
    ('ss', 'SS'),
]

# Abbreviated team names in tag data -> schedule words they should match.
_TEAM_NAME_ALIASES = {
    'vancanucks': ['vancouver'],
    'atlthrashers': ['atlanta'],
    'atlthrash': ['atlanta'],
    # 2010-11 schedule says 'NJ Devils'; the tag team is 'New Jersey'.
    'new jersey': ['devils'],
}


# ---------------------------------------------------------------------------
# Workbook loading + sheet-name normalization
# ---------------------------------------------------------------------------

def notes_struct(tag_comment='', schedule=None, generated=None):
    """Build the canonical notes structure (a list per source)."""
    return {
        'tag': [tag_comment] if tag_comment else [],
        'schedule': list(schedule or []),
        'generated': list(generated or []),
    }


def notes_tag_text(notes):
    """The verbatim tag-tab comment text from a notes structure (joined if a
    duplicate merge collected several)."""
    if not notes:
        return ''
    return ' '.join(notes.get('tag', []) or [])


def load_workbook(source):
    """Load an openpyxl workbook from a path or bytes. Always read_only + data_only."""
    if isinstance(source, (str, bytes)):
        content = open(source, 'rb').read() if isinstance(source, str) else source
    else:
        content = source.read()
    return openpyxl.load_workbook(io.BytesIO(content), read_only=True, data_only=True)


def short_season(season):
    """Normalize '2002-2003' -> '2002-03'; pass '2002-03' through unchanged."""
    parts = str(season).split('-')
    if len(parts) == 2 and len(parts[1]) == 4:
        return f'{parts[0]}-{parts[1][2:]}'
    return season


def norm_sheet(name):
    """Normalize a sheet name for matching: upper-case, collapse internal
    whitespace, strip ends. Tolerates the trailing-space / casing drift seen
    across report years (e.g. 'Pop Report - Sorted by Inv Tag ')."""
    return re.sub(r'\s+', ' ', str(name)).strip().upper()


def sheet_lookup(wb):
    """{normalized name -> actual workbook sheet name}."""
    return {norm_sheet(n): n for n in wb.sheetnames}


# ---------------------------------------------------------------------------
# Tag-sheet header / column detection
# ---------------------------------------------------------------------------

def detect_col_offset(rows):
    for row in rows[:15]:
        for col_idx in range(min(3, len(row))):
            val = row[col_idx]
            if val and str(val).strip().upper() in _TAG_HEADERS:
                return col_idx
    return 0


def find_header(rows, col):
    """Return (header_row_index, upper-cased header list)."""
    for i, row in enumerate(rows[:15]):
        val = row[col] if len(row) > col else None
        if val and str(val).strip().upper() in _TAG_HEADERS:
            return i, [str(v).strip().upper() if v else '' for v in row[col:col + 9]]
    return 5, []


def parse_set_number(raw):
    """Integer set number from formats like '2 (Reg)', '1 (Pre)', plain 2.
    A datetime/date is NOT a set number -- Excel mis-coerces strings like
    '3-Jan' into dates; those are named sets, not numeric."""
    if raw is None or isinstance(raw, (datetime, date)):
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        m = re.search(r'\d+', str(raw))
        return int(m.group()) if m else None


def format_set_number(raw):
    """Display string for a Set cell. A datetime/date is Excel's mis-coercion
    of a string like '3-Jan' -> restore it as '3-Jan' rather than a timestamp."""
    if raw is None:
        return ''
    if isinstance(raw, (datetime, date)):
        return f"{raw.day}-{raw.strftime('%b')}"
    return str(raw).strip()


# ---------------------------------------------------------------------------
# Team-name resolution (fuzzy match schedule names <-> tag team names)
# ---------------------------------------------------------------------------

def build_team_index(tag_teams):
    """Map normalized words -> list of lowercased full team names."""
    index = {}
    for team in tag_teams:
        team_lower = team.lower()
        for word in team_lower.split():
            if len(word) > 2:
                index.setdefault(word, []).append(team_lower)
        for extra_word in _TEAM_NAME_ALIASES.get(team_lower, []):
            index.setdefault(extra_word, []).append(team_lower)
    return index


def resolve_teams(schedule_name, team_index):
    """Map a schedule team name to all matching tag team names (lowercased).
    Strips a Home/Away/Road suffix, then collects every tag team sharing a word."""
    name = re.sub(r'\s*-\s*(home|away|road).*', '', schedule_name, flags=re.IGNORECASE).strip()
    candidates = set()
    for word in name.lower().split():
        if len(word) > 2 and word in team_index:
            candidates.update(team_index[word])
    return list(candidates)


# ---------------------------------------------------------------------------
# Legacy comma-date parsing (third-jersey tabs, etc.)
# ---------------------------------------------------------------------------

def parse_legacy_dates(cell_value, year_start):
    """Parse individual game dates from a cell like '11/9, 11/19, 12/14, 1/3'.
    Months >= 10 belong to year_start; months < 10 to year_start + 1.
    Returns a list of 'm/d/yyyy' strings."""
    dates = []
    for m in re.finditer(r'\b(\d{1,2})/(\d{1,2})\b', cell_value):
        month = int(m.group(1))
        day = int(m.group(2))
        year = year_start if month >= 10 else year_start + 1
        dates.append(f'{month}/{day}/{year}')
    return dates


def parse_legacy_thirds(rows, season, tag_teams):
    """Parse a legacy third-jersey tab: one row per team, 'Third Set 1' /
    'Third Set 2' columns hold comma-separated dates.
    Returns {(team_lower, 'third', set_num): [game_dicts]}."""
    year_start = int(season.split('-')[0])
    team_index = build_team_index(tag_teams)

    header_idx = third1_col = third2_col = None
    for i, row in enumerate(rows[:5]):
        for j, cell in enumerate(row):
            if not cell:
                continue
            cell_stripped = str(cell).strip().lower()
            if cell_stripped == 'third set 1':
                header_idx = i
                third1_col = j
            elif cell_stripped == 'third set 2':
                third2_col = j
        if header_idx is not None:
            break

    if header_idx is None or third1_col is None:
        return {}

    schedule = {}
    for row in rows[header_idx + 1:]:
        if not row[0]:
            continue
        raw_team = str(row[0]).strip()
        if not raw_team:
            continue

        full_teams = resolve_teams(raw_team, team_index)
        if not full_teams:
            continue

        for set_num, col in [(1, third1_col), (2, third2_col)]:
            if col is None or len(row) <= col or not row[col]:
                continue
            dates = parse_legacy_dates(str(row[col]), year_start)
            if dates:
                games = [{'date': _iso(d), 'opponent': None, 'comment': None}
                         for d in dates]
                for full_team in full_teams:
                    schedule[(full_team, 'third', set_num)] = games

    return schedule


# ---------------------------------------------------------------------------
# Vintage Sets tab + per-jersey "Worn ..." comment dates
# ---------------------------------------------------------------------------

def _iso(mdy):
    """'m/d/yyyy' -> 'YYYY-MM-DD'."""
    mo, d, y = mdy.split('/')
    return f'{int(y):04d}-{int(mo):02d}-{int(d):02d}'


def vintage_color(color_str):
    """The colour word immediately before 'Vintage' in a tag colour, lowered.
    'Black Vintage Set 1' -> 'black'; 'Royal Blue Vintage Practice' -> 'blue'."""
    m = re.search(r'(\w+)\s+vintage', str(color_str), re.IGNORECASE)
    return m.group(1).lower() if m else ''


def parse_vintage_sheet(rows, season, tag_teams):
    """Parse a 'Vintage Sets' tab.
    Rows are '<Team> - <Color> Vintage'; columns are 'Set 1'/'Set 2'/'Set 3'
    holding comma-separated dates with parenthetical annotations.
    Returns {(team_lower, color, set_num): [{'type':'vintage','date':iso}, ...]}.
    """
    year_start = int(str(season).split('-')[0])
    team_index = build_team_index(tag_teams)

    header_idx = None
    set_cols = {}
    for i, row in enumerate(rows[:6]):
        for j, cell in enumerate(row):
            if not cell:
                continue
            m = re.fullmatch(r'set\s*([123])', str(cell).strip(), re.IGNORECASE)
            if m:
                header_idx = i
                set_cols[int(m.group(1))] = j
        if header_idx is not None:
            break
    if header_idx is None or not set_cols:
        return {}

    schedule = {}
    for row in rows[header_idx + 1:]:
        if not row or not row[0]:
            continue
        label = str(row[0]).strip()
        if ' - ' not in label or 'vintage' not in label.lower():
            continue
        team_part, rest = label.split(' - ', 1)
        color = vintage_color(rest) or re.sub(
            r'\s*vintage.*', '', rest, flags=re.IGNORECASE).strip().lower()
        full_teams = resolve_teams(team_part, team_index)
        if not full_teams:
            continue
        for set_num, col in set_cols.items():
            if len(row) <= col or not row[col]:
                continue
            dates = parse_legacy_dates(str(row[col]), year_start)
            if not dates:
                continue
            entries = [{'type': 'vintage', 'date': _iso(d)} for d in dates]
            for full_team in full_teams:
                schedule[(full_team.lower(), color, set_num)] = entries
    return schedule


# Positive verbs (jersey was worn / on the bench / played) vs negative
# (did-not-play / prepared-only -- those dates are NOT worn dates).
_POS_VERB_RE = re.compile(r'\b(worn|played|back(?:ed)?\s?up)\b', re.IGNORECASE)
_NEG_VERB_RE = re.compile(r'\b(dnp|did\s+not\s+play|prepared)\b', re.IGNORECASE)
_WORN_DATE_RE = re.compile(r'\b(\d{1,2})/(\d{1,2})\b')


def extract_worn_dates(comment, season):
    """Worn dates from a per-jersey comment. Each date is attributed to the
    nearest preceding verb: positive ('Worn'/'Played'/'Back Up') keeps it,
    negative ('DNP'/'Did Not Play'/'Prepared') drops it.
    'Worn 12/16/03 and 1/19/04' -> both; 'DNP 2/23/13, Played 3/9/13' ->
    only 3/9/13; 'Prepared for ...' -> []."""
    if not comment:
        return []
    c = str(comment).strip()
    if not _POS_VERB_RE.search(c):
        return []
    year_start = int(str(season).split('-')[0])
    pos = [m.start() for m in _POS_VERB_RE.finditer(c)]
    neg = [m.start() for m in _NEG_VERB_RE.finditer(c)]
    out = []
    for dm in _WORN_DATE_RE.finditer(c):
        i = dm.start()
        lp = max((p for p in pos if p < i), default=None)
        ln = max((p for p in neg if p < i), default=None)
        if ln is not None and (lp is None or ln > lp):
            continue  # nearest preceding verb is negative
        mo, da = int(dm.group(1)), int(dm.group(2))
        yr = year_start if mo >= 10 else year_start + 1
        iso = f'{yr:04d}-{mo:02d}-{da:02d}'
        if iso not in out:
            out.append(iso)
    return out


def enrich_vintage(entries, schedule):
    """Fill vintage jerseys' games_worn from the vintage schedule keyed
    ('vintage', team_lower, color, set_num). The _NON_RANGE_JERSEY guard left
    them empty; the per-jersey 'Worn ...' comment dates are added separately
    by the global step in the orchestrator."""
    for e in entries:
        if 'vintage' not in e.color.lower():
            continue
        set_num = parse_set_number(e.set_number)
        if set_num is None:
            continue
        color = vintage_color(e.color)
        team = e.team.lower()
        # Colour-specific key (2003-04 / 2005-06) first, then the
        # colour-agnostic accumulation key (2006-07).
        dates = (schedule.get(('vintage', team, color, set_num))
                 or schedule.get(('vintage', team, None, set_num)) or [])
        e.games_worn = list(dates)


# Special promotional sets (2012-13+) whose game date is in the colour string,
# e.g. 'Red - Promotional Game 4/27/13', 'Red - Verizon Center Set - 4/13/13',
# 'Black w/Stanley Cup Winning Banner Patch worn 1/19/13'.
PROMO_SETS = {'PROMO', 'VERIZON', 'BANNER',
              'HHOF', 'RETRO', 'OP NIGHT', 'HFC', 'KIOSK', 'GOLD-VIN'}
# Period/event special sets whose code is prefixed, e.g. 'SS-NYR-P2'
# (Stadium Series), 'HC-P1'/'HC-W' (Heritage Classic), 'MM-Per 3' (a
# Mike-Modano-Night style event). 3 jerseys/game share one date.
_PROMO_PREFIX_RE = re.compile(r'^(SS-|HC-|MM\b|MM-)', re.IGNORECASE)
_PROMO_DATE_RE = re.compile(r'\b(\d{1,2})/(\d{1,2})/(\d{2,4})\b')
# Spelled-out date, e.g. 'October 8, 2014' (validated via strptime).
_SPELLED_DATE_RE = re.compile(r'\b([A-Z][a-z]+)\s+(\d{1,2}),\s*(\d{4})\b')
_PROMO_LABELS = {
    'VERIZON': 'Verizon Center Set', 'BANNER': 'Banner',
    'HHOF': 'Hockey Hall of Fame Game', 'HFC': 'Hockey Fights Cancer',
    'OP NIGHT': 'Opening Night', 'RETRO': 'Retro', 'KIOSK': 'Kiosk Set',
    'GOLD-VIN': 'Gold Vintage',
}


def _is_promo_set(set_code):
    c = str(set_code).strip()
    return c.upper() in PROMO_SETS or bool(_PROMO_PREFIX_RE.match(c))


def _promo_label(set_code):
    c = str(set_code).strip().upper()
    if c in _PROMO_LABELS:
        return _PROMO_LABELS[c]
    if c.startswith('SS-'):
        return 'Stadium Series'
    if c.startswith('HC-'):
        return 'Heritage Classic'
    if c.startswith('MM'):
        return 'Mike Modano Night'
    return 'Promotional Game'


def _promo_color_dates(color):
    """All game dates in a special-set colour, in either form: numeric
    'm/d/yy' or spelled-out 'Month D, YYYY' (incl. multiples joined by
    ', '/' and ')."""
    s = str(color)
    out = []
    for mo, d, y in _PROMO_DATE_RE.findall(s):
        y = int(y)
        if y < 100:
            y += 2000
        iso = f'{y:04d}-{int(mo):02d}-{int(d):02d}'
        if iso not in out:
            out.append(iso)
    for mon, d, y in _SPELLED_DATE_RE.findall(s):
        try:
            iso = datetime.strptime(
                f'{mon} {int(d)} {y}', '%B %d %Y').date().isoformat()
        except ValueError:
            continue
        if iso not in out:
            out.append(iso)
    return out


def apply_promo_color_dates(entries, extras=None):
    """For PROMO / VERIZON / BANNER jerseys, take the game date from the colour
    string and assign it (non-GI, non-Warm-Up-Only); then exclude that date
    from the same team's regular set games -- the player wore the special
    jersey that game, not the normal set jersey. Opt-in per year via the
    corrections hook.

    `extras` is an optional {compiled_regex: label_string} map of per-year
    promo set-code patterns not covered by the shared PROMO_SETS /
    _PROMO_PREFIX_RE (e.g. 2015-16 'MB - *' Martin Brodeur Night)."""
    extras = extras or {}

    def is_promo(set_code):
        if _is_promo_set(set_code):
            return True
        s = str(set_code)
        return any(p.search(s) for p in extras)

    def label_for(set_code):
        s = str(set_code)
        for p, lab in extras.items():
            if p.search(s):
                return lab
        return _promo_label(set_code)

    promo_dates = {}
    for e in entries:
        if not is_promo(e.set_number):
            continue
        dates = _promo_color_dates(e.color)
        if not dates or is_game_issued(e.color) or is_warmup_only(e.color):
            continue  # no date / GI / Warm-Up Only -> stays dateless
        e.games_worn = [{'type': 'worn', 'date': d} for d in dates]
        promo_dates.setdefault(e.team.lower(), set()).update(dates)
        label = label_for(e.set_number)
        gen = e.notes.setdefault('generated', [])
        if label not in gen:
            gen.append(label)

    for e in entries:
        if is_promo(e.set_number):
            continue
        # One Game Only entries: the global OGO pass has already set their
        # date from their own colour. That date IS this jersey's identity,
        # even when another (promo) entry happens to share the same date.
        # Skip the exclusion so the OGO entry keeps its date.
        if is_one_game_only(e.color):
            continue
        dates = promo_dates.get(e.team.lower())
        if not dates or not e.games_worn:
            continue
        kept = [g for g in e.games_worn if g.get('date') not in dates]
        if len(kept) == len(e.games_worn):
            continue
        removed = sorted({g['date'] for g in e.games_worn
                          if g.get('date') in dates})
        e.games_worn = kept
        note = 'Excluded promotional date(s): ' + ', '.join(removed)
        gen = e.notes.setdefault('generated', [])
        if note not in gen:
            gen.append(note)


# ---------------------------------------------------------------------------
# Per-game two-block schedule tab ('Team Set Dates', 2005-06 style)
# ---------------------------------------------------------------------------

_END_SET_RE = re.compile(r'end\s+set\s+(\d+)\s*\(([HA])\)', re.IGNORECASE)
_END_THIRD_RE = re.compile(r'end\s+(?:.*\s)?third\s+set\s+(\d+)', re.IGNORECASE)
_END_VINT_RE = re.compile(r'end\s+vintage\s+set\s+(\d+)', re.IGNORECASE)
# 'End White Set 2', 'End Navy Set 3', 'End White Retro Set 1' (2007-08+) --
# the colour (possibly multi-word) picks the lane.
_END_COLOR_RE = re.compile(r'end\s+(.+?)\s+set\s+(\d+)\b', re.IGNORECASE)
# 'End Gray Playoffs', 'End White Playoffs' (no 'Set N'): marks the last
# playoff game of a lane. Used to populate ('playoffs', team, lane) for
# dedicated playoff-set tags when the schedule lacks a 'PLAYOFFS'
# section header (e.g. 2018-19 Vegas). The colour portion is letters
# and spaces only, so 'End White Set 2 / Playoffs' (handled by
# _END_COLOR_RE) does NOT match here -- the digit blocks it.
_END_PLAYOFFS_RE = re.compile(
    r'^end\s+([A-Za-z]+(?:\s+[A-Za-z]+)*)\s+playoffs?\s*$', re.IGNORECASE)


def _norm_opponent(s):
    """'vs Toronto' / 'at Toronto' / 'Toronto' -> 'toronto'."""
    if not s:
        return ''
    s = str(s).strip().lower()
    for prefix in ('vs ', 'at ', '@ '):
        if s.startswith(prefix):
            s = s[len(prefix):]
            break
    return s.strip()


def opponent_repetition_playoff_boundary(games, lookahead=3, min_repeats=3):
    """Index of the first playoff game within `games`, or None.

    A game starts a playoff series if its opponent appears at least
    `min_repeats` times within current + next `lookahead` games.
    Regular-season schedules rarely play the same opponent 3+ times in
    4 consecutive games; playoff series do so by construction (4-7
    games against one opponent)."""
    if not games:
        return None
    ordered = sorted(games, key=lambda g: g.get('date', ''))
    for i in range(len(ordered)):
        window = ordered[i:i + 1 + lookahead]
        if len(window) < 2:
            continue
        opp = _norm_opponent(window[0].get('opponent', ''))
        if not opp:
            continue
        matches = sum(1 for g in window
                      if _norm_opponent(g.get('opponent', '')) == opp)
        if matches >= min(min_repeats, len(window)):
            return i
    return None
# '<Color> Stanley Cup Final Set <N>' (optionally prefixed 'End '): identifies
# a row as a Stanley Cup Final game so it routes to ('scf', team, color, num)
# instead of the regular home/away/third bucket. The colour is the leading
# word(s) before 'Stanley Cup Final'.
_SCF_NOTE_RE = re.compile(
    r'(?:end\s+)?([A-Za-z][A-Za-z\s]*?)\s+stanley\s+cup\s+final\s+set\s+(\d+)',
    re.IGNORECASE)
# 'Reverse Retro' jersey (2020-21+): a special alternate jersey worn for
# a small set of games per team. Routes to ('reverse_retro', team, num)
# so RR-<TEAM>-<N> pop-report entries can look it up without polluting
# (or getting polluted by) the team's home set.
_REVERSE_RETRO_JERSEY_RE = re.compile(r'^\s*reverse\s+retro\s*$', re.IGNORECASE)
_END_RR_NOTE_RE = re.compile(
    r'end\s+reverse\s+retro\s+set\s+(\d+)', re.IGNORECASE)
# Section labels embedded in the date column ('PRESEASON', 'REGULAR SEASON',
# 'PLAYOFFS') -- the row contains only the label, no actual game data.
_SECTION_LABELS = ('preseason', 'regularseason', 'playoffs')


_WD_RE = r'(?:mon|tue|tues|wed|thu|thur|thurs|fri|sat|sun)[a-z]*'


def _parse_team_set_date(val):
    """A schedule date cell -> 'YYYY-MM-DD', or None. Handles datetime cells
    (2006-07+), 'Oct 5 2005, Wed' (weekday trailing, 2005-06) and
    'Sat Jan 19, 2013' (weekday leading, 2012-13)."""
    if val is None:
        return None
    if isinstance(val, (datetime, date)):
        return (val.date() if isinstance(val, datetime) else val).isoformat()
    s = str(val).strip()
    if not s or s.upper() == 'DATE':
        return None
    s = re.sub(r'^%s\.?,?\s+' % _WD_RE, '', s, flags=re.IGNORECASE)
    s = re.sub(r',?\s*%s\.?\s*$' % _WD_RE, '', s, flags=re.IGNORECASE)
    # Tolerate stray whitespace, incl. a space before the comma
    # ('Sep 23 , 2014' -> 'Sep 23, 2014'), and a period after a letter
    # ('Sep. 15, 2018' -> 'Sep 15, 2018'; 2018-19 schedule style).
    # Replace with a space (not nothing) so 'Mar.18, 2022' -> 'Mar 18, 2022'
    # instead of 'Mar18, 2022' (2021-22 schedule has rows with no space
    # after the period); the \s+ normalization collapses double spaces.
    s = re.sub(r'([A-Za-z])\.', r'\1 ', s)
    s = re.sub(r'\s+,', ',', re.sub(r'\s+', ' ', s)).strip().rstrip(',').strip()
    s = s.replace('Sept', 'September')  # 2005-06 schedule style; strptime doesn't recognize 'Sept'.)
    for fmt in ('%b %d %Y', '%b %d, %Y', '%B %d %Y', '%B %d, %Y',
                '%d %b %Y', '%d %b, %Y', '%d %B %Y', '%d %B, %Y'):
        try:
            return datetime.strptime(s, fmt).date().isoformat()
        except ValueError:
            pass
    return None


def parse_team_set_dates(rows, season, tag_teams, note_corrections=None):
    """Parse a per-game two-block schedule tab (2005-06 'Team Set Dates',
    2006-07 'Set Breakdowns', ...): one block per team, the season split
    across two side-by-side column groups, each group = DATE, Jersey, note,
    OPPONENT. The DATE columns and the season-marker column are auto-detected,
    so column drift between years is handled without per-year tweaks.

    Jersey colour maps to a lane (White->away, THIRD->third, else home). Each
    lane's set number starts at 1 and advances when a note marks the end of a
    set ('End Set N (H/A)' for home/away, 'End Third Set N' for third) -- the
    marked game is the last of set N. VINT rows feed the vintage schedule.

    note_corrections maps a malformed note (whitespace-normalized) to its
    corrected text -- a per-file data fix (e.g. 2007-08 Nashville's
    'End Set 1 White   Reverse Jersey' -> 'End White Set 1').

    Returns {(team_lower, 'home'|'away'|'third', set_num): [game dicts]}
    (plus ('vintage', team, color, set) keys), resolved by lookup_games.
    """
    short = short_season(season)
    start_year = int(short.split('-')[0])
    note_fixes = {re.sub(r'\s+', ' ', k).strip(): v
                  for k, v in (note_corrections or {}).items()}
    team_index = build_team_index(tag_teams)

    # Auto-detect the two DATE column groups from the header row.
    date_cols = []
    for r in rows[:12]:
        cols = [j for j, c in enumerate(r)
                if c is not None and str(c).strip().upper() == 'DATE']
        if len(cols) >= 2:
            date_cols = sorted(cols)
            break
    if len(date_cols) < 2:
        return {}

    # Team-header rows hold the short season string in some cell.
    headers = [i for i, r in enumerate(rows)
               if any(c is not None and str(c).strip() == short for c in r)]
    headers.append(len(rows))

    schedule = {}
    for hi in range(len(headers) - 1):
        start, end = headers[hi], headers[hi + 1]
        full_teams = resolve_teams(str(rows[start][0]).strip(), team_index)
        if not full_teams:
            continue

        # Preseason sub-block (2007-08 has it; 2005-06/2006-07 don't) ->
        # additive ('preseason', team) keys for the 'Preseason Only' rule.
        for key, val in _extract_preseason(rows, start, end, start_year,
                                           full_teams).items():
            schedule[key] = val

        # First DATE group is the first half of the season, second group the
        # second -- read the first fully, then the second, in row order.
        sequence = []
        for base in date_cols:
            for r in rows[start + 1:end]:
                if len(r) <= base + 3:
                    continue
                iso = _parse_team_set_date(r[base])
                if not iso:
                    continue
                jersey = str(r[base + 1]).strip() if r[base + 1] else ''
                if not jersey or jersey.upper() == 'JERSEY':
                    continue
                note = str(r[base + 2]).strip() if r[base + 2] else ''
                if note_fixes:
                    note = note_fixes.get(re.sub(r'\s+', ' ', note).strip(), note)
                opp = str(r[base + 3]).strip() if r[base + 3] else ''
                sequence.append((iso, jersey, note, opp))

        # Sets have no start marker -- a game belongs to its lane's current set
        # until a note ends it (the ended game is the last of that set).
        current = {'home': 1, 'away': 1, 'third': 1, 'vintage': 1}
        for iso, jersey, note, opp in sequence:
            if jersey.upper() == 'VINT':
                # Two vintage layouts: an explicit per-row label
                # ('White Vintage Set 1', 2005-06) -> keyed by colour+set; or
                # unlabelled rows that accumulate until 'End Vintage Set N'
                # (2006-07) -> keyed colour-agnostic (None).
                m_lbl = re.search(r'(\w+)\s+vintage\s+set\s*(\d+)', note,
                                  re.IGNORECASE)
                if m_lbl and m_lbl.group(1).lower() != 'end':
                    vcolor, vset, vkeycol = (m_lbl.group(1).lower(),
                                             int(m_lbl.group(2)), None)
                else:
                    vcolor, vset, vkeycol = None, current['vintage'], 'acc'
                for full_team in full_teams:
                    schedule.setdefault(
                        ('vintage', full_team.lower(),
                         vcolor if vkeycol is None else None, vset),
                        []).append({'type': 'vintage', 'date': iso})
                m_end = _END_VINT_RE.search(note) if note else None
                if m_end:
                    current['vintage'] = int(m_end.group(1)) + 1
                continue

            lane = jersey_home_away(jersey)
            set_num = current[lane]
            comment = note or None
            if note and (_END_SET_RE.search(note) or _END_THIRD_RE.search(note)
                         or _END_VINT_RE.search(note)
                         or _END_COLOR_RE.search(note)):
                comment = None
            for full_team in full_teams:
                schedule.setdefault((full_team, lane, set_num), []).append(
                    {'date': iso, 'opponent': opp or None, 'comment': comment})

            if not note:
                continue
            # Set-end markers, three dialects:
            #   'End Third Set N'      -> third lane
            #   'End Set N (H|A)'      -> home/away (2005-07)
            #   'End <Colour> Set N'   -> lane via colour (2007-08+)
            mt = _END_THIRD_RE.search(note)
            if mt:
                current['third'] = int(mt.group(1)) + 1
                continue
            mha = _END_SET_RE.search(note)
            if mha:
                marker_lane = 'home' if mha.group(2).upper() == 'H' else 'away'
                current[marker_lane] = int(mha.group(1)) + 1
                continue
            mc = _END_COLOR_RE.search(note)
            if mc and 'vintage' not in mc.group(1).lower():
                current[jersey_home_away(mc.group(1))] = int(mc.group(2)) + 1

    return schedule


_TABLE_RANGE_RE = re.compile(
    r'(\d{1,2})/(\d{1,2})/(\d{2,4})\s*-\s*(\d{1,2})/(\d{1,2})/(\d{2,4})')
# No-year range, e.g. Boston Third Set 1 '10/3 - 4/8'.
_TABLE_RANGE_NOYR_RE = re.compile(
    r'(\d{1,2})/(\d{1,2})\s*-\s*(\d{1,2})/(\d{1,2})(?!/?\d)')
_TABLE_DATE_RE = re.compile(r'(\d{1,2})/(\d{1,2})/(\d{2,4})')
_TABLE_GAMES_RE = re.compile(r'\((\d+)|(\d+)\s*games?\b', re.IGNORECASE)
# Team-header cell: '<Team> 2008-09 Season', '<Team> 2009-2010 Season', or
# '<Team> 2010-11' (no 'Season' word). Anchored at end so datetime cells like
# '2010-09-22 00:00:00' don't match. Excludes 'Preseason' / 'Regular Season'.
_TEAM_HDR_RE = re.compile(
    r'^(?!preseason|regular\s+season).*\b20\d\d'
    # must be a season range ('2012-13') and/or end with 'Season' --
    # NOT a bare year, so game-date strings like 'Sat Jan 19, 2013'
    # are not mistaken for team headers.
    r'(?:(?:-\d\d|-20\d\d)(?:\s+season)?|(?:-\d\d|-20\d\d)?\s+season)\s*$',
    re.IGNORECASE)
_HDR_SUFFIX_RE = re.compile(
    r'\s*\b20\d\d(?:-\d\d|-20\d\d)?(?:\s+season)?\b.*$', re.IGNORECASE)


def _mk_date(mo, d, y):
    y = int(y)
    if y < 100:
        y += 2000
    return f'{y:04d}-{int(mo):02d}-{int(d):02d}'


def _parse_table_label(text):
    """A summary-table row label -> (lane, set_num) or None. Three dialects:
    'Set N Home|Away' (2008-09), 'Third Set N' (both), '<Colour> Set N'
    (2009-10, colour -> lane via the home/away mapping)."""
    t = re.sub(r'\s*-\s*$', '', str(text).strip()).strip()
    # Per-game set-end markers ('End White Set 2', 'End Third Set 1') live in
    # the same sheet as some summary tables (2007-08); they are NOT summary
    # labels -- reject them so they aren't mistaken for the summary.
    if re.match(r'end\b', t, re.IGNORECASE):
        return None
    # Drop a trailing playoffs qualifier: '/ Playoffs', '/PO', '/ PO', etc.
    t = re.sub(r'\s*/\s*(play\w*|po)\s*$', '', t, flags=re.IGNORECASE).strip()
    m = re.match(r'set\s*(\d+)\s*(home|away)\s*$', t, re.IGNORECASE)
    if m:
        return m.group(2).lower(), int(m.group(1))
    m = re.match(r'third\s+set\s*(\d+)\s*$', t, re.IGNORECASE)
    if m:
        return 'third', int(m.group(1))
    # '<Colour ...> Set N' -- colour may be multi-word ('Blue Retro Set 1').
    m = re.match(r'(.+?)\s+set\s*(\d+)\s*$', t, re.IGNORECASE)
    if m:
        prefix = m.group(1).lower()
        # Vintage and SCF (Stanley Cup Finals) have their own dateless-special
        # handling; don't fold them into the normal home/away set keys (a
        # 'Black SCF Set 1' would otherwise collide with 'Black Set 1').
        if 'vintage' in prefix or 'scf' in prefix:
            return None
        return jersey_home_away(prefix), int(m.group(2))
    return None


def _parse_preseason_date(val, start_year):
    """A preseason per-game date cell -> 'YYYY-MM-DD'. Handles datetime cells
    (2008-09) and weekday strings 'Tue, Sep 15' (2009-10, no year -> inferred
    from the season)."""
    if val is None:
        return None
    if isinstance(val, (datetime, date)):
        return (val.date() if isinstance(val, datetime) else val).isoformat()
    s = str(val).strip()
    if not s or s.lower() == 'date':
        return None
    s = re.sub(r'^[A-Za-z]{3,9}\.?,\s*', '', s)  # drop leading weekday
    m = re.match(r'([A-Za-z]{3,9})\.?\s+(\d{1,2})$', s)
    if m:
        try:
            mo = datetime.strptime(m.group(1)[:3], '%b').month
        except ValueError:
            return None
        yr = start_year if mo >= 8 else start_year + 1
        return f'{yr:04d}-{mo:02d}-{int(m.group(2)):02d}'
    try:
        return datetime.strptime(s, '%b %d %Y').date().isoformat()
    except ValueError:
        return None


def _extract_preseason(rows, start, end, start_year, full_teams):
    """Within a team block, find the '^Preseason' label; the dates are in that
    same column until a '^Regular Season' cell. Returns
    {('preseason', team_lower): [{'date': iso}, ...]} (empty if the sheet has
    no preseason section, e.g. 2005-06 / 2006-07)."""
    pcol = None
    pre = []
    for ri in range(start, end):
        row = rows[ri]
        if pcol is None:
            for ci, c in enumerate(row):
                if c is not None and re.match(r'preseason\b',
                                              str(c).strip(), re.IGNORECASE):
                    pcol = ci
                    break
            continue
        pc = row[pcol] if pcol < len(row) else None
        if pc is not None and re.match(r'regular\s+season\b',
                                       str(pc).strip(), re.IGNORECASE):
            break
        iso = _parse_preseason_date(pc, start_year)
        if iso:
            pre.append(iso)
    if not pre:
        return {}
    seen = set()
    ded = [{'date': d} for d in pre if not (d in seen or seen.add(d))]
    return {('preseason', ft): ded for ft in full_teams}


# Compact set-end marker, e.g. 'OS2 Ends', 'WS1 Ends', 'TS2 Ends'. The leading
# letter is a colour/lane code: W -> away, T -> third, anything else -> home.
_COMPACT_END_RE = re.compile(r'\b([A-Za-z])S\s?(\d+)\s*ends?\b', re.IGNORECASE)


def _hdr_role_cols(header_row, date_cols):
    """For each DATE column, map its group's role columns. Returns
    {date_col: (jersey_col, note_col, opp_col)}. Detects 'JSY'/'Jersey',
    'Opponent', 'NOTES' from the header; falls back to the 2005-08 fixed
    offsets (date+1 jersey, date+2 note, date+3 opponent)."""
    roles = {}
    for idx, dc in enumerate(date_cols):
        nxt = date_cols[idx + 1] if idx + 1 < len(date_cols) else len(header_row)
        jcol = ocol = ncol = None
        for c in range(dc + 1, nxt):
            h = str(header_row[c]).strip().upper() if c < len(header_row) \
                and header_row[c] is not None else ''
            if h in ('JSY', 'JERSEY') and jcol is None:
                jcol = c
            elif h in ('OPPONENT', 'OPP') and ocol is None:
                ocol = c
            elif h in ('NOTES', 'NOTE', 'COMMENTS', 'COMMENT') and ncol is None:
                ncol = c
        if jcol is None:  # 2005-08 layout: Date, Jersey, <note>, Opponent
            jcol, ncol, ocol = dc + 1, dc + 2, dc + 3
        roles[dc] = (jcol, ncol if ncol is not None else dc + 2,
                     ocol if ocol is not None else dc + 3)
    return roles


def parse_pergame_schedule(rows, season, tag_teams, date_corrections=None):
    """Parse the per-game two-block schedule (the detailed, authoritative
    source: exact game dates per set). Handles column-order variants via
    header-role detection and every set-end marker dialect, including the
    compact '<C>S<n> Ends' form (2010-11). Rows flagged 'Preseason' in the
    note feed the ('preseason', team) key instead of a regular set.

    `date_corrections` is an optional {bad: good} map (whitespace-normalized
    exact match on the date cell) used to fix per-file typos that defeat the
    general date parser without losing the row's end-marker.

    Returns {(team_lower, 'home'|'away'|'third', set_num): [game dicts]}
    (plus ('preseason', team) keys).
    """
    team_index = build_team_index(tag_teams)
    date_fixes = {re.sub(r'\s+', ' ', k).strip(): v
                  for k, v in (date_corrections or {}).items()}

    date_cols = []
    header_row = None
    for r in rows[:20]:
        cols = [j for j, c in enumerate(r)
                if c is not None and str(c).strip().upper() == 'DATE']
        if cols:  # 1 group (single-block, 2012-13) or 2 (two-block)
            date_cols, header_row = sorted(cols), r
            break
    if not date_cols:
        return {}
    roles = _hdr_role_cols(header_row, date_cols)

    headers = [i for i, r in enumerate(rows)
               if any(c is not None and _TEAM_HDR_RE.match(str(c).strip())
                      for c in r)]
    headers.append(len(rows))

    schedule = {}
    for hi in range(len(headers) - 1):
        start, end = headers[hi], headers[hi + 1]
        name = ''
        for c in rows[start]:
            if c is not None and _TEAM_HDR_RE.match(str(c).strip()):
                name = _HDR_SUFFIX_RE.sub('', str(c).strip()).strip()
                break
        full_teams = resolve_teams(name, team_index)
        if not full_teams:
            continue

        # Find PRESEASON / REGULAR SEASON / PLAYOFFS section labels embedded
        # in the date column. The label row has no real date; subsequent rows
        # inherit the section. Map each in-block row index to its section.
        sections = {}
        cur_section = 'regularseason'
        for ri in range(start + 1, end):
            r = rows[ri]
            for dc in date_cols:
                if dc < len(r) and r[dc] is not None:
                    norm = str(r[dc]).strip().lower().replace(' ', '')
                    if norm in _SECTION_LABELS:
                        cur_section = norm
                        break
            sections[ri] = cur_section

        pre = []
        sequence = []
        for dc in date_cols:
            jcol, ncol, ocol = roles[dc]
            for ri in range(start + 1, end):
                r = rows[ri]
                if len(r) <= dc:
                    continue
                cell = r[dc]
                if date_fixes and cell is not None:
                    key = re.sub(r'\s+', ' ', str(cell)).strip()
                    if key in date_fixes:
                        cell = date_fixes[key]
                iso = _parse_team_set_date(cell)
                if not iso:
                    continue
                jersey = (str(r[jcol]).strip()
                          if jcol < len(r) and r[jcol] else '')
                if not jersey or jersey.upper() in ('JERSEY', 'JSY'):
                    continue
                note = (str(r[ncol]).strip()
                        if ncol < len(r) and r[ncol] else '')
                opp = (str(r[ocol]).strip()
                       if ocol < len(r) and r[ocol] else '')
                section = sections.get(ri, 'regularseason')
                if (section == 'preseason'
                        or re.match(r'preseason\b', note, re.IGNORECASE)):
                    pre.append(iso)
                    continue
                # Stanley Cup Final rows: route to ('scf', team, color, num)
                # and skip the regular set-tracking + end-marker logic so the
                # 'End <Color> Stanley Cup Final Set N' marker doesn't
                # regress current[lane].
                m_scf = _SCF_NOTE_RE.search(note) if note else None
                if m_scf:
                    scf_color = m_scf.group(1).strip().lower()
                    scf_num = int(m_scf.group(2))
                    for ft in full_teams:
                        schedule.setdefault(
                            ('scf', ft, scf_color, scf_num), []).append(
                                {'date': iso, 'opponent': opp or None,
                                 'comment': None})
                    continue
                sequence.append((iso, jersey, note, opp, section))

        if pre:
            seen = set()
            ded = [{'date': d} for d in pre if not (d in seen or seen.add(d))]
            for ft in full_teams:
                schedule[('preseason', ft)] = ded

        # ---------- Pass 1: collect End markers per home/away/third lane.
        # Reverse-pass bucketing uses these as authoritative boundaries:
        # a row's set number is the *first* End marker at-or-after this
        # row's sequence index for its lane. Rows with no End marker
        # at-or-after are intentionally orphaned (no schedule key gets
        # them), so missing markers produce dateless entries instead of
        # being silently swept into the next set.
        # End-of-playoffs markers (e.g. 'End Gray Playoffs', no 'Set N')
        # are tracked separately and used to route post-End-Set-N rows
        # into the ('playoffs', team, lane) key for dedicated playoff
        # tags when the schedule lacks a 'PLAYOFFS' section header.
        end_markers = {'home': [], 'away': [], 'third': []}
        end_playoffs = {'home': None, 'away': None, 'third': None}
        for idx, (iso, jersey, note, opp, section) in enumerate(sequence):
            if not note:
                continue
            m = _END_THIRD_RE.search(note)
            if m:
                end_markers['third'].append((idx, int(m.group(1))))
                continue
            m = _END_SET_RE.search(note)
            if m:
                lane_e = 'home' if m.group(2).upper() == 'H' else 'away'
                end_markers[lane_e].append((idx, int(m.group(1))))
                continue
            m = _COMPACT_END_RE.search(note)
            if m:
                code = m.group(1).upper()
                lane_e = ('away' if code == 'W'
                          else 'third' if code == 'T' else 'home')
                end_markers[lane_e].append((idx, int(m.group(2))))
                continue
            m = _END_PLAYOFFS_RE.match(note.strip())
            if m and 'vintage' not in m.group(1).lower():
                end_playoffs[jersey_home_away(m.group(1))] = idx
                continue
            m = _END_COLOR_RE.search(note)
            if m and 'vintage' not in m.group(1).lower():
                lane_e = jersey_home_away(m.group(1))
                end_markers[lane_e].append((idx, int(m.group(2))))
        for lane_e in end_markers:
            end_markers[lane_e].sort()

        def _set_num_for(lane_e, idx):
            """First End-marker set_num at-or-after `idx` for lane_e, or
            None if no such marker (row is orphaned). Special case: when
            the lane has NO End markers at all but does have rows, assume
            a single set and return 1 (e.g. 2012-13 Colorado 'Third' --
            no 'End Third Set' marker but the pop report has only Third
            Set 1, so all THIRD rows belong to Set 1)."""
            markers = end_markers.get(lane_e, [])
            if not markers:
                return 1
            for end_idx, end_set_num in markers:
                if idx <= end_idx:
                    return end_set_num
            return None

        # ---------- Pass 2: bucket each row.
        current = {'vintage': 1, 'reverse_retro': 1}
        for idx, (iso, jersey, note, opp, section) in enumerate(sequence):
            # Reverse Retro (2020-21+): special alternate jersey, routed
            # to its own key so it doesn't pollute home/away/third and
            # 'End Reverse Retro Set N' doesn't regress those counters.
            if _REVERSE_RETRO_JERSEY_RE.match(jersey):
                for ft in full_teams:
                    schedule.setdefault(
                        ('reverse_retro', ft, current['reverse_retro']), []
                    ).append({'date': iso, 'opponent': opp or None,
                              'comment': None})
                m_rr = _END_RR_NOTE_RE.search(note) if note else None
                if m_rr:
                    current['reverse_retro'] = int(m_rr.group(1)) + 1
                continue

            if jersey.upper() in ('VINT', 'VINTAGE'):
                # Vintage games: explicit per-row label ('White Vintage Set 1')
                # -> keyed by colour+set; else unlabelled rows accumulate until
                # 'End Vintage Set N' -> keyed colour-agnostic (None).
                m_lbl = re.search(r'(\w+)\s+vintage\s+set\s*(\d+)', note,
                                  re.IGNORECASE)
                if m_lbl and m_lbl.group(1).lower() != 'end':
                    vcolor, vset = m_lbl.group(1).lower(), int(m_lbl.group(2))
                else:
                    vcolor, vset = None, current['vintage']
                for ft in full_teams:
                    schedule.setdefault(('vintage', ft, vcolor, vset),
                                        []).append({'type': 'vintage',
                                                    'date': iso})
                m_end = _END_VINT_RE.search(note) if note else None
                if m_end:
                    current['vintage'] = int(m_end.group(1)) + 1
                continue

            lane = jersey_home_away(jersey)
            set_num = _set_num_for(lane, idx)
            is_marker = bool(note and (
                _END_SET_RE.search(note) or _END_THIRD_RE.search(note)
                or _END_VINT_RE.search(note) or _END_COLOR_RE.search(note)
                or _COMPACT_END_RE.search(note)
                or _END_PLAYOFFS_RE.match(note.strip())))
            if set_num is not None:
                for ft in full_teams:
                    schedule.setdefault((ft, lane, set_num), []).append(
                        {'date': iso, 'opponent': opp or None,
                         'comment': None if is_marker else (note or None)})
            # Dedicated 'Playoffs' set jerseys (Edmonton 2016-17, Vegas
            # 2017-18, 2018-19, ...) look up their dates by lane via this
            # key. SCF rows are routed away earlier so they don't pollute
            # this.
            # Population sources:
            #   1. Section header ('PLAYOFFS') -- any row in that section.
            #   2. End Playoffs marker -- rows ORPHANED by reverse pass
            #      (no Set N marker at-or-after) but at-or-before the End
            #      Playoffs marker for that lane are playoff rows.
            in_playoffs_span = (
                set_num is None
                and end_playoffs.get(lane) is not None
                and idx <= end_playoffs[lane])
            if section == 'playoffs' or in_playoffs_span:
                for ft in full_teams:
                    schedule.setdefault(('playoffs', ft, lane), []).append(
                        {'date': iso, 'opponent': opp or None,
                         'comment': None if is_marker else (note or None)})

        # When the End-Playoffs span included regular-season tail games
        # (rows between End Set N and the first playoff opponent series),
        # apply opponent-repetition to filter those out. Skip lanes that
        # were populated from a section header -- those rows are already
        # known to be playoffs.
        any_section_playoff = any(
            sections.get(ri) == 'playoffs' for ri in sections)
        if not any_section_playoff:
            for lane in ('home', 'away', 'third'):
                if end_playoffs.get(lane) is None:
                    continue
                for ft in full_teams:
                    pk = ('playoffs', ft, lane)
                    games = schedule.get(pk, [])
                    if not games:
                        continue
                    boundary = opponent_repetition_playoff_boundary(games)
                    if boundary is None or boundary == 0:
                        continue
                    ordered = sorted(games, key=lambda g: g.get('date', ''))
                    schedule[pk] = ordered[boundary:]
    return schedule

def parse_games_schedule(rows, season, tag_teams, date_corrections=None):
    """Parse the per-game two-block schedule (the detailed, authoritative
    source: exact game dates per set). Handles column-order variants via
    header-role detection and every set-end marker dialect, including the
    compact '<C>S<n> Ends' form (2010-11). Rows flagged 'Preseason' in the
    note feed the ('preseason', team) key instead of a regular set.

    `date_corrections` is an optional {bad: good} map (whitespace-normalized
    exact match on the date cell) used to fix per-file typos that defeat the
    general date parser without losing the row's end-marker.

    Returns {(team_lower, 'home'|'away'|'third', set_num): [game dicts]}
    (plus ('preseason', team) keys).
    """
    team_index = build_team_index(tag_teams)
    date_fixes = {re.sub(r'\s+', ' ', k).strip(): v
                  for k, v in (date_corrections or {}).items()}
    
    date_cols = []
    header_row = None
    for r in rows[:20]:
        cols = [j for j, c in enumerate(r)
                if c is not None and str(c).strip().upper() == 'DATE']
        if cols:  # 1 group (single-block, 2012-13) or 2 (two-block)
            date_cols, header_row = sorted(cols), r
            break
    if not date_cols:
        return {}
    roles = _hdr_role_cols(header_row, date_cols)

    headers = [i for i, r in enumerate(rows)
               if any(c is not None and _TEAM_HDR_RE.match(str(c).strip())
                      for c in r)]
    headers.append(len(rows))

    schedule = {}
    for hi in range(len(headers) - 1):
        start, end = headers[hi], headers[hi + 1]
        name = ''
        for c in rows[start]:
            if c is not None and _TEAM_HDR_RE.match(str(c).strip()):
                name = _HDR_SUFFIX_RE.sub('', str(c).strip()).strip()
                break
        full_teams = resolve_teams(name, team_index)
        if not full_teams:
            continue
        
        current_section = None
        games = []
        for row in rows[start+2:end]:
            if row[date_cols[0]] is not None:
                if (row[date_cols[0]].strip().lower().replace(' ', '') in _SECTION_LABELS):
                    current_section = row[date_cols[0]].strip().lower().replace(' ', '')
                    continue
                if row[roles[date_cols[0]][2]] is not None and row[roles[date_cols[0]][0]] is not None:
                    games.append({
                        'date': _parse_team_set_date(row[date_cols[0]]) if date_cols and date_cols[0] < len(row) else None,
                        'opponent': row[roles[date_cols[0]][2]] if date_cols and date_cols[0] < len(row) and roles[date_cols[0]][2] < len(row) else None,
                        'comment': row[roles[date_cols[0]][1]] if date_cols and date_cols[0] < len(row) and roles[date_cols[0]][1] < len(row) else None,
                        'color': row[roles[date_cols[0]][0]] if date_cols and date_cols[0] < len(row) and roles[date_cols[0]][0] < len(row) else None,
                        'game_type': current_section,
                        'set_num': None
                    })
        
        set_numbers = {}
        for game in reversed(games):
            if game['comment'] is not None and re.match(r'end \b', str(game['comment']), re.IGNORECASE):
                # This is an end marker; determine the lane and set number from the comment.
                set_numbers[game['color']] = str(game['comment']).lower().replace('end ', '').replace(game['color'].lower(), '').replace('set', '').strip()
            if (game['color'] in set_numbers):
                game['set_num'] = set_numbers[game['color']]
                
        for game in games:
            schedule_key = (full_teams[0], game['color'], game['set_num'])
            if schedule_key not in schedule:
                schedule[schedule_key] = []
            schedule[schedule_key].append(game)

    return schedule

def parse_set_dates_table(rows, season, tag_teams, cell_corrections=None):
    """Parse a 'Set Dates' tab whose per-team block ends with a
    'Set:' / 'Dates and Number of Games:' summary table giving a date RANGE
    (and game count) per set, e.g.
        'Set 1 Home -'  '10/10/08 - 11/28/08 (10 + Preseason)'   (2008-09)
        'Blue Set 1'    '10/3/09 - 12/12/09'  '10 Games + Pre'   (2009-10)
        'Third Set 2 -' '2/8/09 - 4/9/09 (7)'
    There are no per-game End markers these years, so this table is the
    authoritative set delimiter (the legacy range model, embedded per team).
    Returns {(team_lower, 'home'|'away'|'third', set_num):
        [{'type':'range','start','end'[,'games':N]}]}, resolved by
    lookup_games' home/away branch. 'Promotional' rows are ignored.
    """
    team_index = build_team_index(tag_teams)
    start_year = int(short_season(season).split('-')[0])
    # Per-file value-cell fixups (whitespace-normalized exact match), e.g.
    # a typo'd date range in the summary table.
    cell_fixes = {re.sub(r'\s+', ' ', k).strip(): v
                  for k, v in (cell_corrections or {}).items()}

    headers = [i for i, r in enumerate(rows)
               if any(c is not None and _TEAM_HDR_RE.match(str(c).strip())
                      for c in r)]
    headers.append(len(rows))

    schedule = {}
    for hi in range(len(headers) - 1):
        start, end = headers[hi], headers[hi + 1]
        # Team name: from the matched cell (strip the 'YYYY Season' suffix);
        # if that leaves nothing (year/Season is its own cell), fall back to
        # the first other non-empty, non-sublabel cell in the row.
        name = ''
        hrow = rows[start]
        for c in hrow:
            if c is not None and _TEAM_HDR_RE.match(str(c).strip()):
                name = _HDR_SUFFIX_RE.sub('', str(c).strip()).strip()
                break
        if not name:
            for c in hrow:
                s = str(c).strip() if c is not None else ''
                if s and not _TEAM_HDR_RE.match(s) and \
                        not re.match(r'(pre|regular)', s, re.IGNORECASE):
                    name = s
                    break
        full_teams = resolve_teams(name, team_index)
        if not full_teams:
            continue

        for key, val in _extract_preseason(rows, start, end, start_year,
                                           full_teams).items():
            schedule[key] = val

        for r in rows[start:end]:
            for j, cell in enumerate(r):
                if not cell:
                    continue
                label = _parse_table_label(cell)
                if not label:
                    continue
                lane, set_num = label
                # Value = first non-empty cell after the label (range / date
                # list / single datetime / descriptor); count is a later cell.
                raw_val = next((r[k] for k in range(j + 1, len(r))
                                if r[k] is not None and str(r[k]).strip()), None)
                if raw_val is None:
                    continue
                if isinstance(raw_val, (datetime, date)):
                    iso = (raw_val.date() if isinstance(raw_val, datetime)
                           else raw_val).isoformat()
                    for full_team in full_teams:
                        schedule[(full_team, lane, set_num)] = [{'date': iso}]
                    continue
                val = str(raw_val).strip()
                if cell_fixes:
                    val = cell_fixes.get(re.sub(r'\s+', ' ', val).strip(), val)
                games_n = None
                for k in range(j + 1, len(r)):
                    if r[k] is None:
                        continue
                    gm = _TABLE_GAMES_RE.search(str(r[k]))
                    if gm:
                        games_n = int(gm.group(1) or gm.group(2))
                        break

                rm = _TABLE_RANGE_RE.search(val)
                ny = None if rm else _TABLE_RANGE_NOYR_RE.search(val)
                if rm:
                    entry = {'type': 'range',
                             'start': _mk_date(rm.group(1), rm.group(2), rm.group(3)),
                             'end': _mk_date(rm.group(4), rm.group(5), rm.group(6))}
                    if games_n is not None:
                        entry['games'] = games_n
                    games = [entry]
                elif ny:
                    # No-year range ('10/3 - 4/8'): infer year from the season
                    # (NHL months >= 8 -> first year, else second).
                    def _yr(mo):
                        return start_year if int(mo) >= 8 else start_year + 1
                    entry = {
                        'type': 'range',
                        'start': _mk_date(ny.group(1), ny.group(2), _yr(ny.group(1))),
                        'end': _mk_date(ny.group(3), ny.group(4), _yr(ny.group(3))),
                    }
                    if games_n is not None:
                        entry['games'] = games_n
                    games = [entry]
                elif 'playoff' in val.lower():
                    # Playoffs descriptor (incl. 'Playoffs (except 4/13/11)' --
                    # the date is an exclusion, NOT a worn date): keep as a
                    # note + count, like 2002-03's Tampa 'Playoffs'.
                    entry = {'type': 'note', 'note': val}
                    if games_n is not None:
                        entry['games'] = games_n
                    games = [entry]
                elif _TABLE_DATE_RE.search(val):
                    # Discrete dates, e.g. '11/28/08 and 12/2/08' or
                    # '4/11/10 + Playoffs'.
                    games = [{'date': _mk_date(mo, d, y)}
                             for mo, d, y in _TABLE_DATE_RE.findall(val)]
                else:
                    # Descriptor with no dates ('Playoffs', ...): keep it as a
                    # note + count, same treatment as 2002-03's Tampa 'Playoffs'.
                    entry = {'type': 'note', 'note': val}
                    if games_n is not None:
                        entry['games'] = games_n
                    games = [entry]
                for full_team in full_teams:
                    schedule[(full_team, lane, set_num)] = games
    return schedule


# ---------------------------------------------------------------------------
# Legacy home/road date-range tabs
# ---------------------------------------------------------------------------

def detect_set_columns(header_row):
    """{set_num: col_index} for sets 1-4 on a home/road range tab."""
    skip_keywords = ('games:', 'games in', 'promo', 'p/o set', 'total', 'playoffs')
    col_map = {}
    for j, cell in enumerate(header_row):
        if not cell:
            continue
        h = str(cell).lower()
        # The 3rd-set header legitimately contains 'playoffs', so check it
        # before the skip gate.
        if '3rd' in h and ('regular' in h or '/ po' in h or 'playoff' in h):
            col_map[4] = j
        elif any(kw in h for kw in skip_keywords):
            continue
        elif 'preseason' in h:
            col_map[1] = j
        elif '1st' in h and 'regular' in h:
            col_map[2] = j
        elif '2nd' in h and 'regular' in h:
            col_map[3] = j
    return col_map


def detect_count_columns(header_row):
    """{set_num: col_index} for the per-set game-count columns on a home/road
    range tab. Preseason (set 1) has no count column. Set 4 prefers the
    combined 'Total: 3rd Reg/PO' column (matches set 4's combined range),
    falling back to 'Games: 3rdReg' if no total column exists."""
    col_map = {}
    for j, cell in enumerate(header_row):
        if not cell:
            continue
        h = re.sub(r'[^a-z0-9]', '', str(cell).lower())
        if 'games1streg' in h:
            col_map[2] = j
        elif 'games2ndreg' in h:
            col_map[3] = j
        elif '3rdreg' in h and ('po' in h or 'playoff' in h):
            # Combined 3rd-reg + playoffs total ('Total: 3rd Reg/PO',
            # 'Games: 3rd Reg/PO') -- matches set 4's combined range. Overrides
            # a plain 'Games: 3rdReg' captured earlier in the row.
            col_map[4] = j
        elif 'games3rdreg' in h:
            col_map.setdefault(4, j)
    return col_map


def _parse_count(cell_val):
    """Integer game count from a cell, or None if absent / zero / unparseable."""
    if cell_val is None:
        return None
    if isinstance(cell_val, bool):
        return None
    if isinstance(cell_val, (int, float)):
        n = int(cell_val)
        return n if n > 0 else None
    m = re.search(r'\d+', str(cell_val))
    if not m:
        return None
    n = int(m.group())
    return n if n > 0 else None


def parse_range_value(cell_val):
    """Parse a date-range cell into:
      ('preseason', label)        - plain preseason set; label = sheet wording
      ('preseason+', str, label)  - preseason + extra regular-season dates
      (start_date, end_date)      - explicit range
      None                        - unparseable / skip
    The preseason label preserves the exact spreadsheet text (e.g.
    'All PreSeason', 'Worn All Preseason') rather than a normalized constant.
    """
    if cell_val is None:
        return None
    if isinstance(cell_val, (int, float)):
        return None  # game count cell

    if isinstance(cell_val, datetime):
        d = cell_val.date()
        return (d, d)

    s = str(cell_val).strip()
    if not s or s == '0':
        return None
    m = _PRE_PLUS_RE.match(s)
    if m:
        return ('preseason+', m.group(1).strip(), s)
    if 'preseason' in s.lower() or 'all pre' in s.lower():
        return ('preseason', s)

    m = re.match(r'(\d{1,2})/(\d{1,2})/(\d{2,4})\s*-\s*(\d{1,2})/(\d{1,2})/(\d{2,4})', s)
    if m:
        def to_date(mo, d, y):
            y = int(y)
            if y < 100:
                y += 2000 if y < 50 else 1900
            return date(y, int(mo), int(d))
        return (to_date(m.group(1), m.group(2), m.group(3)),
                to_date(m.group(4), m.group(5), m.group(6)))
    return None


def parse_range_rows(rows, team_index):
    """Parse data rows from a home/road range tab.
    Returns (ranges, counts):
      ranges[(team_lower, 'home'|'away', set_num)] = range_value
      counts[(team_lower, 'home'|'away', set_num)] = int game count
    counts only contains keys whose game-count cell parsed to a positive int."""
    header_row = None
    header_idx = 0
    for i, row in enumerate(rows[:5]):
        if row[0] and 'team' in str(row[0]).lower():
            header_row = row
            header_idx = i
            break
    if header_row is None:
        return {}, {}

    col_map = detect_set_columns(header_row)
    if not col_map:
        return {}, {}
    count_map = detect_count_columns(header_row)

    ranges = {}
    counts = {}
    for row in rows[header_idx + 1:]:
        if not row[0]:
            continue
        raw_team = str(row[0]).strip()
        if not raw_team or raw_team.lower().startswith('team'):
            continue

        if re.search(r'-\s*home', raw_team, re.IGNORECASE):
            home_away = 'home'
        elif re.search(r'-\s*(?:away|road)', raw_team, re.IGNORECASE):
            home_away = 'away'
        else:
            continue

        full_teams = resolve_teams(raw_team, team_index)
        if not full_teams:
            continue

        for set_num, col in col_map.items():
            if col >= len(row):
                continue
            cell = row[col]
            parsed = parse_range_value(cell)
            # A non-empty cell in a known set column always means that set
            # existed, even if it isn't a parseable date range. Rather than
            # discarding the row, keep the set and carry the sheet text:
            #   set 1 (preseason) -> preseason note (no count column)
            #   other sets        -> generic note (+ game count if present)
            # e.g. LA Kings preseason 'Old Style Purple Third', or Tampa Bay
            # 3rd Reg/PO 'Playoffs'.
            if (parsed is None and cell is not None
                    and not isinstance(cell, (int, float, datetime))):
                text = str(cell).strip()
                if text and text != '0':
                    parsed = ('preseason_note', text) if set_num == 1 else ('note', text)
            if parsed is not None:
                for full_team in full_teams:
                    ranges[(full_team, home_away, set_num)] = parsed

        for set_num, col in count_map.items():
            if col >= len(row):
                continue
            n = _parse_count(row[col])
            if n is not None:
                for full_team in full_teams:
                    counts[(full_team, home_away, set_num)] = n

    return ranges, counts


def schedule_from_ranges(set_ranges, counts=None, season=None):
    """Build a schedule from range data alone (no API).
    Returns {(team_lower, 'home'|'away', set_num): [entry]} where entry is one of:
      {'type': 'range', 'start': 'YYYY-MM-DD', 'end': 'YYYY-MM-DD'[, 'games': N]}
      {'type': 'preseason', 'label': '<sheet wording>'}
      {'type': 'preseason', 'note': '<unrecognized sheet text>'}
      {'type': 'preseason+', 'extra_dates': [...], 'label': '<sheet wording>'}
      {'type': 'note', 'note': '<sheet text>'[, 'games': N]}
    The preseason 'label' is the exact spreadsheet text; 'note' is used when a
    set column held descriptor text instead of a date range (e.g. Tampa Bay's
    3rd Reg/PO = 'Playoffs'). The 'games' count is attached to range and note
    entries when available. Preseason sets have no count column.
    """
    counts = counts or {}
    schedule = {}
    for key, range_val in set_ranges.items():
        tagged = isinstance(range_val, tuple) and isinstance(range_val[0], str)
        if tagged and range_val[0] == 'preseason':
            games = [{'type': 'preseason', 'label': range_val[1]}]
        elif tagged and range_val[0] == 'preseason_note':
            games = [{'type': 'preseason', 'note': range_val[1]}]
        elif tagged and range_val[0] == 'note':
            entry = {'type': 'note', 'note': range_val[1]}
            n = counts.get(key)
            if n is not None:
                entry['games'] = n
            games = [entry]
        elif tagged and range_val[0] == 'preseason+':
            year_start = int(season.split('-')[0]) if season else 2000
            extra_strs = parse_legacy_dates(range_val[1], year_start)
            extra_dates = []
            for ds in extra_strs:
                mo, d, y = ds.split('/')
                extra_dates.append(f'{y}-{int(mo):02d}-{int(d):02d}')
            games = [{'type': 'preseason+', 'extra_dates': extra_dates,
                      'label': range_val[2]}]
        else:
            start_d, end_d = range_val
            entry = {'type': 'range', 'start': str(start_d), 'end': str(end_d)}
            n = counts.get(key)
            if n is not None:
                entry['games'] = n
            games = [entry]
        schedule[key] = games
    return schedule


# ---------------------------------------------------------------------------
# Color / jersey -> schedule-key lookup
# ---------------------------------------------------------------------------

# Jersey descriptors whose worn dates come from dedicated tabs (Vintage Sets,
# Heritage Classic & MegaStars, practice-jersey lists), NOT the home/road range
# tabs. They must never fall through to the regular home/away keys, or a
# 'White Vintage Set 1' would falsely pick up the team's preseason range.
_NON_RANGE_JERSEY = ('vintage', 'heritage', 'megastar', 'mega star', 'practice')


def color_to_schedule_jersey(color_str):
    lower = color_str.lower()
    for substring, schedule_value in COLOR_TO_SCHEDULE:
        if substring in lower:
            return schedule_value
    return None


# 'GI' token, or 'Game-Issued'/'Game Issued', or 'issued for' spelled out --
# all mean prepared/issued, not game-worn.
_GI_RE = re.compile(r'\bGI\b|game[\s-]?issued|\bissued\s+for\b', re.IGNORECASE)
_ONE_GAME_RE = re.compile(r'one\s+game\s+only', re.IGNORECASE)
_COLOR_DATE_RE = re.compile(r'(\d{1,2})/(\d{1,2})/(\d{2,4})')


def is_game_issued(color_str):
    """True if the jersey colour says it was issued but not game-worn --
    'GI', 'Game-Issued'/'Game Issued', or 'issued for <date>' -> no dates."""
    return bool(_GI_RE.search(str(color_str)))


_TRAINING_CAMP_RE = re.compile(r'training\s+camp\s+only', re.IGNORECASE)
_PRESEASON_ONLY_RE = re.compile(r'pre\s*season\s+only', re.IGNORECASE)
_WARMUP_ONLY_RE = re.compile(r'warm[-\s]?up\s+only', re.IGNORECASE)
_FLAG_RE = re.compile(
    r'(training\s+camp\s+only|pre\s*season\s+only|one\s+game\s+only'
    r'|warm[-\s]?up\s+only)',
    re.IGNORECASE)


def is_training_camp_only(color_str):
    """'Training Camp Only' -- worn only in training camp, never a game."""
    return bool(_TRAINING_CAMP_RE.search(str(color_str)))


def is_preseason_only(color_str):
    """'Preseason Only' -- worn only in preseason games."""
    return bool(_PRESEASON_ONLY_RE.search(str(color_str)))


def is_warmup_only(color_str):
    """'Warm-Up Only' / 'Warmup Only' -- worn only during pre-game warmup,
    never in the game itself."""
    return bool(_WARMUP_ONLY_RE.search(str(color_str)))


def color_flag_text(color_str):
    """The verbatim usage flag in a colour string (for the notes), e.g.
    'Training Camp Only', or '' if none."""
    m = _FLAG_RE.search(str(color_str))
    return m.group(1) if m else ''


def is_one_game_only(color_str):
    """True if the colour is flagged 'One Game Only' -- worn a single game,
    not the whole set, so the set-range schedule must not be applied."""
    return bool(_ONE_GAME_RE.search(str(color_str)))


def one_game_only_dates(color_str):
    """The explicit date(s) embedded in a 'One Game Only' colour string,
    either numeric ('Black Set 3 - One Game Only 4/8/10' -> '2010-04-08')
    or spelled-out ('White Set 1 - One Game Only - Worn November 27, 2017'
    -> '2017-11-27')."""
    return _promo_color_dates(color_str)


def jersey_home_away(color_str):
    """'third', 'away', or 'home' from a jersey color string.
    White is away; Third is thirds; everything else is home."""
    lower = color_str.lower()
    if 'third' in lower:
        return 'third'
    if 'white' in lower:
        return 'away'
    return 'home'


_SCF_LANE_COLOR_RE = re.compile(
    r'\b(white|red|gray|grey|gold|black|navy|blue|orange|green|purple)\b',
    re.IGNORECASE)


def _lookup_scf_games(schedule, team, color, set_num_int):
    """Resolve an SCF-* tag entry to the ('scf', team, color, set_num) bucket
    by matching the leading colour word in the tag's colour string against
    the schedule's SCF keys."""
    m = _SCF_LANE_COLOR_RE.search(str(color))
    if not m:
        return []
    c = m.group(1).lower()
    if c == 'grey':
        c = 'gray'
    return schedule.get(('scf', team.lower(), c, set_num_int), [])


_RR_SET_CODE_RE = re.compile(r'^RR\s*-', re.IGNORECASE)


def _lookup_reverse_retro_games(schedule, team, set_num_int):
    """Resolve an RR-<TEAM>-<N> tag entry to the ('reverse_retro', team,
    set_num) bucket built by parse_pergame_schedule from the schedule's
    'Reverse Retro' jersey rows."""
    return schedule.get(
        ('reverse_retro', team.lower(), set_num_int), [])


def lookup_games(schedule, team, color, set_num_int, set_raw=None):
    """Look up games_worn from a schedule dict.
    Tries the color-label key first, then the home/away key."""
    print(f'Looking up games for team={team}, color={color}, set_num={set_num_int}, set_raw={set_raw}')
    if set_num_int is None:
        return []

    # Stanley Cup Final jerseys: dispatch to the ('scf', team, color, num)
    # buckets that parse_pergame_schedule built from the schedule's
    # '<Color> Stanley Cup Final Set N' comment markers (2017-18+ default).
    # If no SCF key exists (older years where SCF jerseys aren't called out
    # in the schedule, e.g. SCF-PS/SCF-MGG 2002-03), return [] -- the
    # project rule is that SCF jerseys stay dateless.
    if set_raw and str(set_raw).strip().upper().startswith('SCF'):
        return _lookup_scf_games(schedule, team, color, set_num_int)

    # Reverse Retro jerseys (2020-21+): dispatch to the dedicated bucket
    # so RR-<TEAM>-<N> tag entries don't fall through to the team's home
    # set via the digit-in-set-code fallback.
    if set_raw and _RR_SET_CODE_RE.match(str(set_raw).strip()):
        return _lookup_reverse_retro_games(
            schedule, team, set_num_int)

    cl = color.lower()
    if any(w in cl for w in _NON_RANGE_JERSEY):
        return []

    sched_jersey = color_to_schedule_jersey(color)
    if sched_jersey:
        games = schedule.get((team.lower(), sched_jersey, str(set_num_int)))
        if games is not None:
            return games

    # Legacy range schedules (2002-03, 2003-04) put preseason at key 1 and
    # regular sets at 2-4, but tag data numbers regular sets 1-3 with a
    # "(Reg)" suffix. Add 1 to align. Thirds need no offset.
    ha = jersey_home_away(color)
    if ha != 'third' and set_raw and '(Reg)' in str(set_raw):
        range_key = set_num_int + 1
    else:
        range_key = set_num_int
    return schedule.get((team.lower(), ha, range_key), [])


# ---------------------------------------------------------------------------
# Generic tag-row parser (color + set columns)
# ---------------------------------------------------------------------------

def parse_entries_color_set(rows, col, header_idx, league, schedule, report, MeiGrayEntry):
    """Layout: TAG #, Team, Player, JSY #, Color, Set, Size, [Version,]
    Customizations/Comments. Tag..Size are at fixed offsets col+0..col+6; the
    comment column is located from the header (some years insert a 'Version'
    column before it, others have no comment column at all)."""
    hdr = rows[header_idx] if header_idx < len(rows) else ()
    comment_col = None
    for j in range(col, min(len(hdr), col + 12)):
        v = hdr[j]
        if v and ('CUSTOMIZATION' in str(v).upper() or 'COMMENT' in str(v).upper()):
            comment_col = j
            break

    data_rows = [
        r for r in rows[header_idx + 1:]
        if len(r) > col and r[col] and str(r[col])[:1].isalpha()
    ]
    entries = []
    for row in data_rows:
        fields = (list(row[col:col + 7]) + [None] * 7)[:7]
        tag = str(fields[0]).strip() if fields[0] else ''
        team = str(fields[1]).strip() if fields[1] else ''
        player = str(fields[2]).strip() if fields[2] else ''
        jsy_num = str(fields[3]).strip() if fields[3] is not None else ''
        color = str(fields[4]).strip() if fields[4] else ''
        set_raw = fields[5]
        size = str(fields[6]).strip() if fields[6] else ''
        comment = ''
        if comment_col is not None and comment_col < len(row) and row[comment_col]:
            comment = str(row[comment_col]).strip()
        notes = notes_struct(tag_comment=comment)

        set_num_int = parse_set_number(set_raw)
        set_number_str = format_set_number(set_raw)

        games_worn = lookup_games(schedule, team, color, set_num_int, set_raw=set_raw)

        entries.append(MeiGrayEntry(
            tag_number=tag,
            league=league,
            team=team,
            player=player,
            jersey_number=jsy_num,
            color=color,
            set_number=set_number_str,
            size=size,
            notes=notes,
            games_worn=games_worn,
            report=report,
        ))
    return entries, len(data_rows)
