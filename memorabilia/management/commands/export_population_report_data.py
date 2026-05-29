from itertools import chain

from django.core import serializers
from django.core.management.base import BaseCommand, CommandError

from memorabilia.models import (
    MeiGrayScheduleEntry,
    MeiGrayScheduleGameEntry,
    MeiGrayScheduleSetEntry,
    MeiGrayTagEntry,
    MeiGrayPopulationReport,
)


class Command(BaseCommand):
    help = ('Export a population report and all its schedule + tag rows to a '
            'loaddata-compatible fixture')

    def add_arguments(self, parser):
        parser.add_argument('--season', type=str, required=True, help='Season label, e.g. 2024-25')
        parser.add_argument('--league', type=str, default='NHL', help='League abbreviation (default: NHL)')
        parser.add_argument('--output', type=str, help='Output file path (default: <season>-<league>.json)')

    def handle(self, *args, **options):
        season = options['season']
        league = options['league'].upper()
        output_path = options['output'] or f'./memorabilia/fixtures/{season}-{league}.json'

        try:
            report = MeiGrayPopulationReport.objects.get(season=season, league=league)
        except MeiGrayPopulationReport.DoesNotExist:
            raise CommandError(f'No population report found for {season} {league}')

        schedules = MeiGrayScheduleEntry.objects.filter(report=report)
        games = MeiGrayScheduleGameEntry.objects.filter(schedule__in=schedules)
        set_ranges = MeiGrayScheduleSetEntry.objects.filter(schedule__in=schedules)
        tags = MeiGrayTagEntry.objects.filter(report=report)

        objects = chain([report], schedules, games, set_ranges, tags)
        data = serializers.serialize('json', objects, use_natural_foreign_keys=True)

        with open(output_path, 'w') as f:
            f.write(data)

        self.stdout.write(self.style.SUCCESS(
            f'Exported 1 report, {schedules.count()} schedule(s), '
            f'{games.count()} game(s), {set_ranges.count()} set-range(s), '
            f'{tags.count()} tag(s) to {output_path}'
        ))
