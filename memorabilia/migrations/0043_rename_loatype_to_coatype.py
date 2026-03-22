from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ('memorabilia', '0042_seasonset_hockeyjersey_hockeyjerseyimage_and_more'),
    ]
    operations = [
        migrations.RenameModel(old_name='LoaType', new_name='CoaType'),
        migrations.RenameField(model_name='playeritem', old_name='loa', new_name='coa'),
        migrations.RenameField(model_name='playergear', old_name='loa', new_name='coa'),
        migrations.RenameField(model_name='generalitem', old_name='loa', new_name='coa'),
        migrations.RenameField(model_name='hockeyjersey', old_name='loa', new_name='coa'),
    ]
