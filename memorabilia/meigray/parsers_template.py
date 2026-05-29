"""
Template for a new year's MeiGray parser. Copy to ``parsers_<startyear>.py``
(e.g. ``parsers_2022.py`` for 2022-23) and fill in the marked sections.

Workflow:
  1. Inspect the XLSX (`openpyxl.load_workbook(...).sheetnames`) to confirm
     the tag-sheet name, schedule-sheet name(s), and any other sheets to omit.
  2. Update MANIFEST_YYYY with those names.
  3. If the schedule sheet has a non-standard layout that
     `read_combined_schedule` doesn't recognize, call `parse_pergame_schedule`
     and/or `parse_set_dates_table` directly with the rows.
  4. Register the spec at the bottom and add
     `from . import parsers_YYYY` to `memorabilia/meigray/__init__.py`.
  5. Verify: `make check SETTINGS=dev`, then import a real file.
"""

from memorabilia.meigray import toolbox
from memorabilia.meigray.registry import SheetManifest, YearSpec, register

MANIFEST_YYYY = SheetManifest(
    tag='POP REPORT BY TAG NUMBER',
    schedule=('SET DATES - JERSEY SCHEDULES',),
    omit=('POP REPORT BY PLAYER',),
)


def parse_tags_YYYY(wb, actual, manifest, report):
    return toolbox.read_tag_rows(wb, actual, manifest, report)


def parse_schedule_YYYY(wb, actual, manifest, report, tag_teams):
    return toolbox.read_combined_schedule(
        wb, actual, 'SET DATES - JERSEY SCHEDULES', report.season, tag_teams)


# Uncomment and add the corresponding `from . import parsers_YYYY` line in
# memorabilia/meigray/__init__.py to make this register() run.
# register('NHL', 'YYYY-YY', YearSpec(MANIFEST_YYYY, parse_tags_YYYY, parse_schedule_YYYY))
