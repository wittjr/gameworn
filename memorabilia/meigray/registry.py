"""
Season -> parser registry.

Every supported report is one YearSpec: a sheet manifest plus the two callables
that turn that year's workbook into tag rows and schedule rows. A season with
no exact entry inherits the most recent earlier season's spec ("assume the
next year uses this format until it doesn't"). When a year's format diverges,
add a new YearSpec for it; earlier years are untouched.
"""

from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class SheetManifest:
    """Exhaustive accounting of every sheet a year's workbook may contain.

    tag       -- the population-report (tag) sheet
    schedule  -- sheets that carry team schedule data
    omit      -- sheets deliberately ignored (alternate sort orders, etc.)

    Any sheet in the workbook not covered by one of these is a hard error, so a
    new tab in a future file fails loudly instead of being silently dropped or
    silently treated as schedule data.
    """
    tag: str
    schedule: tuple = ()
    omit: tuple = ()


@dataclass(frozen=True)
class YearSpec:
    manifest: SheetManifest
    # (wb, actual, manifest, report) -> list of MeiGrayTagEntry (unsaved)
    parse_tags: Callable
    # (wb, actual, manifest, report, tag_teams) -> ([game dicts], [set-range dicts])
    # Each dict carries a 'team' key; the orchestrator groups by team.
    parse_schedule: Callable


# Populated by parsers_*.py at import time via register().
REPORTS: dict = {}


def register(league, season, spec):
    REPORTS[(league.upper(), season)] = spec


def resolve(league, season):
    """Exact (league, season) match, else the most recent earlier season for
    that league. Raises if nothing applies."""
    league = league.upper()
    key = (league, season)
    if key in REPORTS:
        return REPORTS[key]
    earlier = sorted(s for (lg, s) in REPORTS if lg == league and s <= season)
    if not earlier:
        raise ValueError(
            f'No parser registered for {season} {league} '
            f'(and no earlier {league} season to inherit from). '
            f'Add a YearSpec in memorabilia/meigray/parsers_*.py.'
        )
    print(f'No exact parser for {season} {league}; using {earlier[-1]} spec.')
    return REPORTS[(league, earlier[-1])]


def check_sheets(wb, manifest, season, league):
    """Verify every workbook sheet is accounted for and every manifest sheet
    exists. Returns {normalized name -> actual sheet name} for lookups.
    Raises ValueError on any unrecognized or missing sheet."""
    from memorabilia.meigray.toolbox import norm_sheet

    actual = {norm_sheet(n): n for n in wb.sheetnames}
    declared = {norm_sheet(manifest.tag)}
    declared |= {norm_sheet(s) for s in manifest.schedule}
    declared |= {norm_sheet(s) for s in manifest.omit}

    unknown = set(actual) - declared
    if unknown:
        names = sorted(actual[u] for u in unknown)
        raise ValueError(
            f'{season} {league}: unrecognized sheet(s) {names}. '
            f'Add each to the YearSpec manifest -- to "schedule" if it carries '
            f'worn dates, or to "omit" if it should be ignored.'
        )

    missing = declared - set(actual)
    if missing:
        raise ValueError(
            f'{season} {league}: manifest references sheet(s) not in the file: '
            f'{sorted(missing)}. Sheets present: {sorted(actual.values())}.'
        )
    return actual


def sheet(actual, name):
    """Resolve a manifest sheet name to the workbook's actual sheet name."""
    from memorabilia.meigray.toolbox import norm_sheet
    return actual[norm_sheet(name)]
