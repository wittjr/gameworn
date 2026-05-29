import os

from django.core.files import File
from django.core.management.base import BaseCommand, CommandError

from memorabilia.meigray import import_report
from memorabilia.models import MeiGrayPopulationReport


class Command(BaseCommand):
    help = 'Import MeiGray population report from an Excel file'

    def add_arguments(self, parser):
        parser.add_argument('xlsx_path', type=str, help='Path to the .xlsx file')
        parser.add_argument('--season', type=str, required=True, help='Season label, e.g. 2024-25')
        parser.add_argument('--league', type=str, default='NHL', help='League abbreviation (default: NHL)')

    def handle(self, *args, **options):
        path = options['xlsx_path']
        season = options['season']
        league = options['league'].upper()

        if not os.path.exists(path):
            raise CommandError(f'File not found: {path}')

        self.stdout.write('Saving report file...')
        filename = os.path.basename(path)
        existing = MeiGrayPopulationReport.objects.filter(season=season, league=league).first()
        is_new = existing is None
        # On re-import: save the new file alongside the old one (storage
        # auto-renames on collision) so the old file is preserved if the
        # import fails. The old file is only deleted after import succeeds.
        old_file_name = None if is_new else existing.file.name
        report = MeiGrayPopulationReport(season=season, league=league) if is_new else existing
        with open(path, 'rb') as f:
            report.file.save(filename, File(f), save=True)
        new_file_name = report.file.name

        self.stdout.write('Importing entries...')
        try:
            counts = import_report(report)
        except Exception as e:
            # Roll back: delete the newly-saved file. If new report, drop the
            # row; if re-import, restore the original file reference.
            report.file.storage.delete(new_file_name)
            if is_new:
                report.delete()
            else:
                report.file.name = old_file_name
                report.save()
            if isinstance(e, ValueError):
                raise CommandError(str(e))
            raise CommandError(f'Could not parse file: {e}')

        # Success: clean up the old file (if any).
        if old_file_name and old_file_name != new_file_name:
            report.file.storage.delete(old_file_name)

        self.stdout.write(self.style.SUCCESS(
            f"Done ({season} {league}). "
            f"{counts['tags']} tag(s), {counts['schedules']} schedule(s), "
            f"{counts['games']} game(s), {counts['set_ranges']} set-range(s)."
        ))
