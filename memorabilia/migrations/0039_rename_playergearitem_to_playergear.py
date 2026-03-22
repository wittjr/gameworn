from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('memorabilia', '0038_update_collage_otheritem_to_generalitem'),
    ]

    operations = [
        migrations.RenameModel(
            old_name='PlayerGearItem',
            new_name='PlayerGear',
        ),
        migrations.RenameModel(
            old_name='PlayerGearItemImage',
            new_name='PlayerGearImage',
        ),
        migrations.RenameIndex(
            model_name='playergear',
            new_name='mem_playergear_updated_idx',
            old_name='mem_playergearitem_updated_idx',
        ),
    ]
