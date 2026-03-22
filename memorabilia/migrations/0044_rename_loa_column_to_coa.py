import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('memorabilia', '0043_rename_loatype_to_coatype'),
    ]

    operations = [
        migrations.AlterField(
            model_name='playeritem',
            name='coa',
            field=models.ForeignKey(blank=True, db_column='coa', null=True, on_delete=django.db.models.deletion.PROTECT, to='memorabilia.coatype', to_field='key'),
        ),
        migrations.AlterField(
            model_name='playergear',
            name='coa',
            field=models.ForeignKey(blank=True, db_column='coa', null=True, on_delete=django.db.models.deletion.PROTECT, to='memorabilia.coatype', to_field='key'),
        ),
        migrations.AlterField(
            model_name='generalitem',
            name='coa',
            field=models.ForeignKey(blank=True, db_column='coa', null=True, on_delete=django.db.models.deletion.PROTECT, to='memorabilia.coatype', to_field='key'),
        ),
        migrations.AlterField(
            model_name='hockeyjersey',
            name='coa',
            field=models.ForeignKey(blank=True, db_column='coa', null=True, on_delete=django.db.models.deletion.PROTECT, to='memorabilia.coatype', to_field='key'),
        ),
    ]
