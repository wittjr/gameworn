"""
1. Make playergearitem.league nullable (DB change: allow NULL).
2. Update PlayerGearItemImage.collectible related_name 'images' → 'gear_images'
   (state-only: related_name is not stored in the database).
"""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('memorabilia', '0028_rename_playeritem_to_playergearitem'),
    ]

    operations = [
        # DB change: add NULL support to the league column
        migrations.AlterField(
            model_name='playergearitem',
            name='league',
            field=models.CharField(blank=True, max_length=5, null=True),
        ),
        # State-only change: Django does not store related_name in the DB
        migrations.AlterField(
            model_name='playergearitemimage',
            name='collectible',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='gear_images',
                to='memorabilia.playergearitem',
            ),
        ),
    ]
