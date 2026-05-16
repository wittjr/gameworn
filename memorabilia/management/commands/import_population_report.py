import os

from django.core.files import File
from django.core.management.base import BaseCommand, CommandError

from memorabilia.meigray_import import analyze_file, import_entries
from memorabilia.models import PopulationReport


class Command(BaseCommand):
    help = 'Import MeiGray population report from an Excel file'

    def add_arguments(self, parser):
        parser.add_argument('xlsx_path', type=str, help='Path to the .xlsx file')
        parser.add_argument('--season', type=str, required=True, help='Season label, e.g. 2024-25')
        parser.add_argument('--league', type=str, default='NHL', help='League abbreviation (default: NHL)')
        parser.add_argument('--dry-run', action='store_true', help='Parse and report without writing to the database')

    def handle(self, *args, **options):
        path = options['xlsx_path']
        season = options['season']
        league = options['league'].upper()

        if not os.path.exists(path):
            raise CommandError(f'File not found: {path}')

        if options['dry_run']:
            self._dry_run(path, season, league)
            return

        self.stdout.write('Saving report file...')
        filename = os.path.basename(path)
        report = PopulationReport.objects.filter(season=season, league=league).first()
        with open(path, 'rb') as f:
            if report:
                report.file.delete(save=False)
                report.file.save(filename, File(f), save=True)
            else:
                report = PopulationReport(season=season, league=league)
                report.file.save(filename, File(f), save=True)

        self.stdout.write('Importing entries...')
        try:
            deleted, created, total, duplicates, with_dates, without_dates = import_entries(report)
        except ValueError as e:
            raise CommandError(str(e))
        except Exception as e:
            raise CommandError(f'Could not parse file: {e}')

        if duplicates:
            self.stdout.write(self.style.WARNING(
                f'Duplicate tag numbers in file (last occurrence kept): {", ".join(duplicates)}'
            ))
        self.stdout.write(self.style.SUCCESS(
            f'Done. {deleted} removed, {created} created from {total} records '
            f'(season: {season}, league: {league}). '
            f'Dates: {with_dates} with, {without_dates} without.'
        ))

    def _dry_run(self, path, season, league):
        self.stdout.write(self.style.WARNING(
            f'DRY RUN — {season} {league} (no data written)\n'
        ))
        try:
            result = analyze_file(path, season, league)
        except ValueError as e:
            raise CommandError(str(e))
        except Exception as e:
            raise CommandError(f'Could not parse file: {e}')

        skipped = result['skipped']
        duplicates = result['duplicates']
        w = self.stdout.write

        # --- Counts ---
        w('Records')
        w(f"  Raw rows after header : {result['total_raw']}")
        w(f"  Passed tag filter     : {result['total_parsed']}"
          + (f"  ({len(skipped)} skipped)" if skipped else ''))
        w(f"  Unique entries        : {result['unique']}"
          + (f"  ({len(duplicates)} duplicate)" if duplicates else ''))
        w('')

        # --- Skipped rows ---
        if skipped:
            w(self.style.WARNING(f'Skipped rows ({len(skipped)}):'))
            for row_num, raw, reason in skipped:
                w(f'  Row {row_num:<6} {str(raw)!r:<20} {reason}')
        else:
            w('Skipped rows: none')
        w('')

        # --- Duplicates ---
        if duplicates:
            w(self.style.WARNING(f'Duplicates ({len(duplicates)}, last occurrence kept):'))
            for tag in duplicates:
                w(f'  {tag}')
        else:
            w('Duplicates: none')
        w('')

        # --- Dates summary ---
        w('Dates')
        w(f"  With dates    : {result['with_dates']}")
        w(f"  Without dates : {result['without_dates']}")
        w('')

        # --- No-dates breakdown ---
        if result['no_dates_breakdown']:
            w(f"Without-dates breakdown ({result['without_dates']} entries):")
            rows = sorted(result['no_dates_breakdown'].items(), key=lambda x: (-x[1], x[0]))
            for (team, set_num), count in rows:
                w(f'  {team:<45} {set_num:<20} {count}')
