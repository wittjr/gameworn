"""
MeiGray population-report parsing.

Public API:
  analyze_file(path, season, league) -> diagnostics dict (no DB writes)
  import_entries(report)             -> (deleted, created, total, duplicates,
                                          with_dates, without_dates)

Orchestration is format-agnostic: resolve the YearSpec for the season, verify
every sheet is accounted for, then delegate schedule + tag parsing to that
spec. Per-year logic lives in parsers_*.py; shared primitives in toolbox.py.
"""

from collections import Counter

from django.db import transaction

from memorabilia.meigray import toolbox
from memorabilia.meigray.registry import check_sheets, resolve, sheet

# Importing the parser modules registers their YearSpecs.
from memorabilia.meigray import parsers_2002  # noqa: F401,E402
from memorabilia.meigray import parsers_2003  # noqa: F401,E402
from memorabilia.meigray import parsers_2005  # noqa: F401,E402
from memorabilia.meigray import parsers_2006  # noqa: F401,E402
from memorabilia.meigray import parsers_2007  # noqa: F401,E402
from memorabilia.meigray import parsers_2008  # noqa: F401,E402
from memorabilia.meigray import parsers_2009  # noqa: F401,E402
from memorabilia.meigray import parsers_2010  # noqa: F401,E402
from memorabilia.meigray import parsers_2011  # noqa: F401,E402
from memorabilia.meigray import parsers_2012  # noqa: F401,E402
from memorabilia.meigray import parsers_2013  # noqa: F401,E402
from memorabilia.meigray import parsers_2014  # noqa: F401,E402
from memorabilia.meigray import parsers_2015  # noqa: F401,E402
from memorabilia.meigray import parsers_2016  # noqa: F401,E402
from memorabilia.meigray import parsers_2017  # noqa: F401,E402
from memorabilia.meigray import parsers_2018  # noqa: F401,E402
from memorabilia.meigray import parsers_2019  # noqa: F401,E402
from memorabilia.meigray import parsers_2020  # noqa: F401,E402
from memorabilia.meigray import parsers_2021  # noqa: F401,E402
from memorabilia.meigray import parsers_2024


def _is_special_set(set_number):
    """True if a set code is "special" (left dateless by design): non-empty and
    not starting with a digit, e.g. SCF-PS, Promo, HHOF. Standard sets start
    with a digit ('2 (Reg)', '1 (Pre)', '4 (PO)')."""
    return bool(set_number) and not set_number.lstrip()[:1].isdigit()


def _has_missing_source_data_note(e):
    """True if the entry carries a generated note explaining that the
    schedule source is missing data for this set (e.g. 'Population report
    is missing Set 2 boundaries, cannot determine exact dates for set').
    Such entries are expected-dateless rather than actionable."""
    notes = e.notes.get('generated', []) if isinstance(e.notes, dict) else []
    return any(str(n).startswith('Population report is missing')
               for n in notes)


def _dateless_reason(e):
    """Why a dateless entry has no dates (for the dry-run breakdown)."""
    if toolbox.is_game_issued(e.color):
        return 'GI'
    flag = toolbox.color_flag_text(e.color)
    if flag:
        return flag  # Training Camp Only / Preseason Only / One Game Only
    if 'vintage' in e.color.lower():
        return 'Vintage (no schedule)'
    if _has_missing_source_data_note(e):
        return 'missing source data'
    if _is_special_set(e.set_number):
        return 'special set'
    if not str(e.set_number).strip():
        return 'blank set'
    return 'no schedule match'


# Source tag columns compared across duplicate occurrences. games_worn is
# excluded (derived). The comment is excluded too: every distinct comment is
# already preserved in the merged notes' 'tag' list.
_DUP_COMPARE_FIELDS = (
    'team', 'player', 'jersey_number', 'color', 'set_number', 'size',
)


def _ordered_unique(seq):
    out = []
    for x in seq:
        if x and x not in out:
            out.append(x)
    return out


def _dup_merge_notes(group):
    """Merge the notes structures of duplicate rows. tag/schedule lists are
    unioned (every distinct value preserved); a 'Population Report contains
    duplicate tags' line describing the differing source columns is added to
    the 'generated' list."""
    tag, sched, gen = [], [], []
    for e in group:
        n = e.notes or {}
        tag += n.get('tag', []) or []
        sched += n.get('schedule', []) or []
        gen += n.get('generated', []) or []
    tag, sched, gen = (_ordered_unique(tag), _ordered_unique(sched),
                       _ordered_unique(gen))

    variance = []
    for field in _DUP_COMPARE_FIELDS:
        vals = []
        for e in group:
            v = str(getattr(e, field) or '').strip()
            if v and v not in vals:
                vals.append(v)
        if len(vals) > 1:
            variance.append(f"{field} " + ' vs '.join(f"'{v}'" for v in vals))
    if variance:
        msg = ('Population Report contains duplicate tags — '
               + '; '.join(variance))
        if msg not in gen:
            gen.append(msg)

    return {'tag': tag, 'schedule': sched, 'generated': gen}


def _row_is_blank(row):
    """True if every cell in the row is None or whitespace-only."""
    return not any(c is not None and str(c).strip() != '' for c in row)


def _read_tag_sheet(wb, actual, manifest):
    ws = wb[sheet(actual, manifest.tag)]
    rows = list(ws.iter_rows(values_only=True))
    col = toolbox.detect_col_offset(rows)
    header_idx, headers = toolbox.find_header(rows, col)
    return rows, col, header_idx, headers


def _tag_teams(rows, col, header_idx):
    return {
        str(r[col + 1]).strip()
        for r in rows[header_idx + 1:]
        if len(r) > col + 1 and r[col + 1] and str(r[col + 1])[:1].isalpha()
    }


def _parse(wb, season, league, report):
    """Run the resolved YearSpec against an open workbook.
    Returns a bundle dict used by both analyze_file and import_entries."""
    season = toolbox.short_season(season)
    spec = resolve(league, season)
    manifest = spec.manifest
    actual = check_sheets(wb, manifest, season, league)

    rows, col, header_idx, headers = _read_tag_sheet(wb, actual, manifest)
    tag_teams = _tag_teams(rows, col, header_idx)

    schedule = spec.build_schedule(wb, actual, manifest, season, tag_teams)
    entries, total_rows = spec.parse_tags(
        rows, col, header_idx, headers, league, schedule, season, report
    )

    # Global per-jersey comment dates: any entry whose comment says the jersey
    # was worn / backed up gets those dates as separate {'type':'worn'} entries,
    # in addition to whatever schedule dates it already has. games_worn is
    # copied first because schedule lookups return shared list objects.
    for e in entries:
        worn = toolbox.extract_worn_dates(toolbox.notes_tag_text(e.notes), season)
        if not worn:
            continue
        have = {(g.get('type'), g.get('date')) for g in e.games_worn}
        added = [{'type': 'worn', 'date': d} for d in worn
                 if ('worn', d) not in have]
        if added:
            e.games_worn = list(e.games_worn) + added

    # 'One Game Only' jerseys were worn a single game, not the whole set, so
    # the set-range lookup is wrong for them. Replace it with the explicit
    # date in the colour (if any; else leave dateless), and keep the
    # 'One Game Only' note.
    for e in entries:
        if not toolbox.is_one_game_only(e.color):
            continue
        # Drop the (wrong) full set-range, but keep any single-game dates: the
        # comment-derived 'worn' entries already added globally, plus an
        # explicit date in the colour string.
        kept = [g for g in e.games_worn if g.get('type') == 'worn']
        seen = {g['date'] for g in kept}
        for d in toolbox.one_game_only_dates(e.color):
            if d not in seen:
                kept.append({'type': 'worn', 'date': d})
                seen.add(d)
        e.games_worn = kept
        gen = e.notes.setdefault('generated', [])
        if 'One Game Only' not in gen:
            gen.append('One Game Only')

    # 'Training Camp Only' -- worn only at training camp, never a game.
    for e in entries:
        if not toolbox.is_training_camp_only(e.color):
            continue
        e.games_worn = []
        ft = toolbox.color_flag_text(e.color)
        gen = e.notes.setdefault('generated', [])
        if ft and ft not in gen:
            gen.append(ft)

    # 'Preseason Only' -- only the team's preseason dates (no regular sets).
    for e in entries:
        if not toolbox.is_preseason_only(e.color):
            continue
        e.games_worn = list(schedule.get(('preseason', e.team.lower()), []))
        ft = toolbox.color_flag_text(e.color)
        gen = e.notes.setdefault('generated', [])
        if ft and ft not in gen:
            gen.append(ft)

    # 'Warm-Up Only' -- worn during pre-game warmup, never in the game itself.
    for e in entries:
        if not toolbox.is_warmup_only(e.color):
            continue
        e.games_worn = []
        ft = toolbox.color_flag_text(e.color)
        gen = e.notes.setdefault('generated', [])
        if ft and ft not in gen:
            gen.append(ft)

    # Game-Issued ('GI') jerseys were prepared but never game-worn, so they
    # have no dates regardless of what their set's schedule says.
    for e in entries:
        if toolbox.is_game_issued(e.color):
            e.games_worn = []

    # Per-file manual fixups, authoritative (run after the global passes).
    if spec.corrections:
        spec.corrections(entries)

    # Dedupe by tag number. First occurrence wins for all fields EXCEPT notes:
    # the kept entry's notes carry merged comments plus any source field that
    # differs across occurrences, with all values, so nothing is lost
    # (e.g. B06338 2003-04 differs on player, size and notes).
    groups = {}
    for e in entries:
        groups.setdefault(e.tag_number, []).append(e)

    duplicates = [tag for tag, g in groups.items() if len(g) > 1]
    unique_entries = []
    for g in groups.values():
        base = g[0]
        if len(g) > 1:
            base.notes = _dup_merge_notes(g)
        unique_entries.append(base)

    # Special set codes (SCF-PS, Promo, HHOF, WarmUp, ...) have no schedule
    # data and are left dateless by design; roll them up so they are surfaced
    # rather than silently empty.
    dateless_special = Counter(
        e.set_number for e in unique_entries
        if not e.games_worn and _is_special_set(e.set_number)
    )

    return {
        'rows': rows,
        'col': col,
        'header_idx': header_idx,
        'entries': entries,
        'unique_entries': unique_entries,
        'duplicates': duplicates,
        'total_rows': total_rows,
        'dateless_special': dateless_special,
    }


def analyze_file(path, season, league):
    """Parse an XLSX and return diagnostics without touching the database."""
    wb = toolbox.load_workbook(path)
    result = _parse(wb, season, league, report=None)

    rows = result['rows']
    col = result['col']
    header_idx = result['header_idx']
    entries = result['entries']
    unique_entries = result['unique_entries']
    duplicates = result['duplicates']

    all_rows = rows[header_idx + 1:]
    # Spreadsheets routinely declare a used-range far past the real data
    # (e.g. 2003-04 ends at row 9171 but the sheet claims 9725). Trim the
    # trailing run of fully-blank rows so they don't drown the skipped report.
    end = len(all_rows)
    while end > 0 and _row_is_blank(all_rows[end - 1]):
        end -= 1
    trailing_blank = len(all_rows) - end
    data_rows = all_rows[:end]

    skipped = []
    for i, r in enumerate(data_rows):
        row_num = header_idx + 2 + i  # 1-indexed spreadsheet row
        raw = r[col] if len(r) > col else None
        if not raw:
            skipped.append((row_num, raw, 'empty tag'))
        elif not str(raw)[:1].isalpha():
            skipped.append((row_num, raw, f'tag does not start with a letter: {str(raw)!r}'))

    with_dates = sum(1 for e in unique_entries if e.games_worn)
    without_dates = len(unique_entries) - with_dates
    no_dates_breakdown = Counter(
        (e.team, e.set_number) for e in unique_entries if not e.games_worn
    )
    # Per (team, set): why those dateless entries have no dates.
    no_dates_reasons = {}
    for e in unique_entries:
        if e.games_worn:
            continue
        no_dates_reasons.setdefault((e.team, e.set_number), Counter())[
            _dateless_reason(e)] += 1
    # Dateless entries that are NOT special-by-design -- standard sets that
    # should have resolved but didn't (the actionable ones to investigate).
    # Expected-dateless jerseys are excluded: GI (Game Issued), the colour
    # usage flags (Training Camp Only / Preseason Only / One Game Only /
    # Warm-Up Only), and entries flagged with a 'Population report is
    # missing ...' note (per-year explicit dateless due to missing source).
    dateless_unexpected = Counter(
        (e.team, e.set_number) for e in unique_entries
        if not e.games_worn and not _is_special_set(e.set_number)
        and not toolbox.is_game_issued(e.color)
        and not toolbox.color_flag_text(e.color)
        and not _has_missing_source_data_note(e)
    )

    return {
        'total_raw': len(data_rows),
        'trailing_blank': trailing_blank,
        'total_parsed': len(entries),
        'unique': len(unique_entries),
        'skipped': skipped,
        'duplicates': duplicates,
        'with_dates': with_dates,
        'without_dates': without_dates,
        'no_dates_breakdown': no_dates_breakdown,
        'no_dates_reasons': no_dates_reasons,
        'dateless_special': result['dateless_special'],
        'dateless_unexpected': dateless_unexpected,
    }


def import_entries(report):
    """Parse the XLSX on report.file and replace all MeiGrayEntry rows for this
    report inside a transaction. Returns (deleted, created, total_rows,
    duplicates, with_dates, without_dates, dateless_special)."""
    from memorabilia.models import MeiGrayEntry

    with report.file.open('rb') as f:
        content = f.read()

    wb = toolbox.load_workbook(content)
    result = _parse(wb, report.season, report.league, report)

    unique_entries = result['unique_entries']
    with_dates = sum(1 for e in unique_entries if e.games_worn)
    without_dates = len(unique_entries) - with_dates

    with transaction.atomic():
        deleted, _ = MeiGrayEntry.objects.filter(report=report).delete()
        MeiGrayEntry.objects.bulk_create(unique_entries)

    return (deleted, len(unique_entries), result['total_rows'],
            result['duplicates'], with_dates, without_dates,
            result['dateless_special'])
