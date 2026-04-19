from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('memorabilia', '0055_populationreport_meigrayentry_report'),
    ]

    operations = [
        migrations.CreateModel(
            name='PlayerGearAuthentication',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('number', models.CharField(blank=True, default='', max_length=100)),
                ('auth_type', models.ForeignKey(blank=True, db_column='auth_type', null=True, on_delete=django.db.models.deletion.PROTECT, to='memorabilia.coatype')),
                ('collectible', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='authentications', to='memorabilia.playergear')),
                ('issuer', models.ForeignKey(blank=True, db_column='issuer', null=True, on_delete=django.db.models.deletion.SET_NULL, to='memorabilia.authsource')),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='PlayerItemAuthentication',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('number', models.CharField(blank=True, default='', max_length=100)),
                ('auth_type', models.ForeignKey(blank=True, db_column='auth_type', null=True, on_delete=django.db.models.deletion.PROTECT, to='memorabilia.coatype')),
                ('collectible', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='authentications', to='memorabilia.playeritem')),
                ('issuer', models.ForeignKey(blank=True, db_column='issuer', null=True, on_delete=django.db.models.deletion.SET_NULL, to='memorabilia.authsource')),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='GeneralItemAuthentication',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('number', models.CharField(blank=True, default='', max_length=100)),
                ('auth_type', models.ForeignKey(blank=True, db_column='auth_type', null=True, on_delete=django.db.models.deletion.PROTECT, to='memorabilia.coatype')),
                ('collectible', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='authentications', to='memorabilia.generalitem')),
                ('issuer', models.ForeignKey(blank=True, db_column='issuer', null=True, on_delete=django.db.models.deletion.SET_NULL, to='memorabilia.authsource')),
            ],
            options={
                'abstract': False,
            },
        ),
    ]
