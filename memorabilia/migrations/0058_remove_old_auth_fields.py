from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('memorabilia', '0057_migrate_auth_data'),
    ]

    operations = [
        # Remove from PlayerGear (concrete table)
        migrations.RemoveField(model_name='playergear', name='team_inventory_number'),
        migrations.RemoveField(model_name='playergear', name='auth_tag_number'),
        migrations.RemoveField(model_name='playergear', name='auth_source'),
        # Remove coa from all concrete Collectible tables (abstract base field)
        migrations.RemoveField(model_name='playergear', name='coa'),
        migrations.RemoveField(model_name='playeritem', name='coa'),
        migrations.RemoveField(model_name='generalitem', name='coa'),
    ]
