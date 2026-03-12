"""
Convert flickrObject from TextField to JSONField on all three image tables.

Existing data was written with str(dict) (Python repr, not valid JSON).
The data migration uses ast.literal_eval to parse those values and re-save
them as proper JSON. Rows whose values cannot be parsed are set to NULL.
"""

import ast
import json

from django.db import migrations, models


def convert_flickrobject_to_json(apps, schema_editor):
    for model_name in ('PlayerItemImage', 'PlayerGearItemImage', 'OtherItemImage'):
        Model = apps.get_model('memorabilia', model_name)
        for img in Model.objects.exclude(flickrObject=None).exclude(flickrObject=''):
            try:
                json.loads(img.flickrObject)
                # Already valid JSON — no action needed
            except (json.JSONDecodeError, TypeError, ValueError):
                try:
                    parsed = ast.literal_eval(img.flickrObject)
                    img.flickrObject = json.dumps(parsed)
                    img.save(update_fields=['flickrObject'])
                except Exception:
                    img.flickrObject = None
                    img.save(update_fields=['flickrObject'])


class Migration(migrations.Migration):

    dependencies = [
        ('memorabilia', '0032_game_type_usage_type_fk'),
    ]

    operations = [
        migrations.RunPython(convert_flickrobject_to_json, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='playeritemimage',
            name='flickrObject',
            field=models.JSONField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='playergearitemimage',
            name='flickrObject',
            field=models.JSONField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='otheritemimage',
            name='flickrObject',
            field=models.JSONField(blank=True, null=True),
        ),
    ]
