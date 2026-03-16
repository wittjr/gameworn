from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('memorabilia', '0034_collage_collectible_ids'),
    ]

    operations = [
        migrations.AddIndex(
            model_name='collection',
            index=models.Index(fields=['owner_uid'], name='mem_collection_owner_idx'),
        ),
        migrations.AddIndex(
            model_name='playergearitem',
            index=models.Index(fields=['last_updated'], name='mem_playergearitem_updated_idx'),
        ),
        migrations.AddIndex(
            model_name='playeritem',
            index=models.Index(fields=['last_updated'], name='mem_playeritem_updated_idx'),
        ),
        migrations.AddIndex(
            model_name='otheritem',
            index=models.Index(fields=['last_updated'], name='mem_otheritem_updated_idx'),
        ),
    ]
