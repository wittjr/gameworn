"""
MeiGray population-report parsing.

Public API:
  import_report(report) -> dict of counts

Each tag row from the population-report sheet becomes one MeiGrayTagEntry, and
each game from the schedule sheet(s) becomes one MeiGrayScheduleGameEntry
(or MeiGrayScheduleSetEntry for legacy set-range data). Tags and schedules are
joined only by (team, season, league) for display; no per-game match.

Orchestration resolves the YearSpec for the season, verifies every sheet is
accounted for, then delegates tag + schedule parsing to that spec. Per-year
logic lives in parsers_*.py; shared primitives in toolbox.py.
"""

from django.db import transaction

from memorabilia.meigray import toolbox
from memorabilia.meigray.registry import check_sheets, resolve

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
from memorabilia.meigray import parsers_2023  # noqa: F401,E402


def import_report(report):
    """Parse the XLSX on report.file and replace all schedule + tag rows for
    this report inside a transaction. Returns a dict of counts."""
    from memorabilia.models import (
        MeiGrayScheduleEntry,
        MeiGrayScheduleGameEntry,
        MeiGrayScheduleSetEntry,
        MeiGrayTagEntry,
    )

    with transaction.atomic():
        with report.file.open('rb') as f:
            content = f.read()

        wb = toolbox.load_workbook(content)
        season = toolbox.short_season(report.season)
        spec = resolve(report.league, season)
        actual = check_sheets(wb, spec.manifest, report.season, report.league)

        tag_entries = spec.parse_tags(wb, actual, spec.manifest, report)
        tag_teams = toolbox.collect_tag_teams(tag_entries)
        games, set_ranges = spec.parse_schedule(wb, actual, spec.manifest, report, tag_teams)

        schedule_teams = set(tag_teams)
        schedule_teams |= {g['team'] for g in games}
        schedule_teams |= {s['team'] for s in set_ranges}

        MeiGrayTagEntry.objects.filter(report=report).delete()
        MeiGrayScheduleEntry.objects.filter(report=report).delete()

        schedules = MeiGrayScheduleEntry.objects.bulk_create([
            MeiGrayScheduleEntry(
                season=report.season,
                league=report.league,
                team=team,
                report=report,
            ) for team in sorted(schedule_teams)
        ])
        team_to_schedule = {s.team: s for s in schedules}

        MeiGrayScheduleGameEntry.objects.bulk_create([
            MeiGrayScheduleGameEntry(
                schedule=team_to_schedule[g['team']],
                opponent=g['opponent'],
                game_date=g['date'],
                jersey=g['jersey'],
                home_game=g['home_game'],
                comment=g['comment'] or None,
                game_type=g['game_type'] or None,
            ) for g in games if g['team'] in team_to_schedule
        ], ignore_conflicts=True)

        MeiGrayScheduleSetEntry.objects.bulk_create([
            MeiGrayScheduleSetEntry(
                schedule=team_to_schedule[s['team']],
                set_label=s['set_label'],
                game_count=s['game_count'],
                dates=s['dates'],
            ) for s in set_ranges if s['team'] in team_to_schedule
        ])

        for e in tag_entries:
            e.schedule = team_to_schedule.get(e.team)

        # tag_number is the PK across all reports. Surface conflicts with a
        # clear error rather than a bare 'UNIQUE constraint failed'.
        batch_numbers = [e.tag_number for e in tag_entries]
        existing = sorted(MeiGrayTagEntry.objects
                          .filter(tag_number__in=batch_numbers)
                          .exclude(report=report)
                          .values_list('tag_number', flat=True))
        if existing:
            raise ValueError(
                f'tag_number(s) already imported on a different report: {existing}'
            )

        MeiGrayTagEntry.objects.bulk_create(tag_entries)

    return {
        'tags': len(tag_entries),
        'schedules': len(schedules),
        'games': len(games),
        'set_ranges': len(set_ranges),
    }
