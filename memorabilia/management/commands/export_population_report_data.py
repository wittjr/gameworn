from django.core import serializers
from django.core.management.base import BaseCommand, CommandError

from memorabilia.models import MeiGrayEntry, PopulationReport


class Command(BaseCommand):
    help = 'Export MeiGrayEntry records for a population report to a loaddata-compatible fixture'

    def add_arguments(self, parser):
        parser.add_argument('--season', type=str, required=True, help='Season label, e.g. 2024-25')
        parser.add_argument('--league', type=str, default='NHL', help='League abbreviation (default: NHL)')
        parser.add_argument('--output', type=str, help='Output file path (default: <season>-<league>.json)')

    def handle(self, *args, **options):
        season = options['season']
        league = options['league'].upper()
        output_path = options['output'] or f'{season}-{league}.json'

        try:
            report = PopulationReport.objects.get(season=season, league=league)
        except PopulationReport.DoesNotExist:
            raise CommandError(f'No population report found for {season} {league}')

        entries = MeiGrayEntry.objects.filter(report=report)
        count = entries.count()
        if count == 0:
            raise CommandError(f'No entries found for {season} {league} — run import first')

        data = serializers.serialize('json', entries, use_natural_foreign_keys=True)

        with open(output_path, 'w') as f:
            f.write(data)

        self.stdout.write(self.style.SUCCESS(
            f'Exported {count} entries to {output_path}'
        ))
