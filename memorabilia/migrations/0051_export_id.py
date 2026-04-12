import uuid

from django.db import migrations, models


def populate_export_ids(apps, schema_editor):
    """Assign a unique UUID to every existing row that has export_id=None."""
    for model_name in ('Collection', 'PlayerItem', 'PlayerGear', 'GeneralItem'):
        Model = apps.get_model('memorabilia', model_name)
        rows = list(Model.objects.filter(export_id__isnull=True))
        for row in rows:
            row.export_id = uuid.uuid4()
        if rows:
            Model.objects.bulk_update(rows, ['export_id'])


class Migration(migrations.Migration):

    dependencies = [
        ('memorabilia', '0050_playergear_home_away'),
    ]

    operations = [
        # Step 1: add nullable (so existing rows don't need a value yet)
        migrations.AddField(
            model_name='collection',
            name='export_id',
            field=models.UUIDField(blank=True, null=True, editable=False),
        ),
        migrations.AddField(
            model_name='playeritem',
            name='export_id',
            field=models.UUIDField(blank=True, null=True, editable=False),
        ),
        migrations.AddField(
            model_name='playergear',
            name='export_id',
            field=models.UUIDField(blank=True, null=True, editable=False),
        ),
        migrations.AddField(
            model_name='generalitem',
            name='export_id',
            field=models.UUIDField(blank=True, null=True, editable=False),
        ),
        # Step 2: populate existing rows
        migrations.RunPython(populate_export_ids, migrations.RunPython.noop),
        # Step 3: make non-nullable and unique
        migrations.AlterField(
            model_name='collection',
            name='export_id',
            field=models.UUIDField(default=uuid.uuid4, editable=False, unique=True),
        ),
        migrations.AlterField(
            model_name='playeritem',
            name='export_id',
            field=models.UUIDField(default=uuid.uuid4, editable=False, unique=True),
        ),
        migrations.AlterField(
            model_name='playergear',
            name='export_id',
            field=models.UUIDField(default=uuid.uuid4, editable=False, unique=True),
        ),
        migrations.AlterField(
            model_name='generalitem',
            name='export_id',
            field=models.UUIDField(default=uuid.uuid4, editable=False, unique=True),
        ),
    ]
