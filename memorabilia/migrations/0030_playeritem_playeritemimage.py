"""
Create the new standalone PlayerItem and PlayerItemImage tables.
These are fresh, empty tables — existing gear data already lives in
memorabilia_playergearitem (renamed from playeritem in migration 0028).

Note: collectible_type is a class attribute on PlayerItem (not a DB column),
following the same pattern as OtherItem in migration 0027.
"""

import django.db.models.deletion
import django.utils.timezone
import rules.contrib.models
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('memorabilia', '0029_alter_playergearitem_league_and_related_name'),
    ]

    operations = [
        migrations.CreateModel(
            name='PlayerItem',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=100)),
                ('description', models.CharField(max_length=500)),
                ('for_sale', models.BooleanField(blank=True, null=True)),
                ('for_trade', models.BooleanField(blank=True, null=True)),
                ('asking_price', models.FloatField(blank=True, null=True)),
                ('last_updated', models.DateTimeField(default=django.utils.timezone.now, editable=False)),
                ('league', models.CharField(blank=True, max_length=5, null=True)),
                ('player', models.CharField(max_length=100)),
                ('team', models.CharField(blank=True, max_length=150, null=True)),
                ('number', models.IntegerField(blank=True, null=True)),
                ('collection', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    to='memorabilia.collection',
                )),
                ('looking_for', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    to='memorabilia.wanteditem',
                )),
            ],
            options={
                'abstract': False,
            },
            bases=(rules.contrib.models.RulesModelMixin, models.Model),
        ),
        migrations.CreateModel(
            name='PlayerItemImage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('primary', models.BooleanField(blank=True, null=True)),
                ('image', models.ImageField(blank=True, null=True, upload_to='images')),
                ('link', models.CharField(blank=True, max_length=255, null=True)),
                ('flickrObject', models.TextField(blank=True, null=True)),
                ('collectible', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='images',
                    to='memorabilia.playeritem',
                )),
            ],
            options={
                'abstract': False,
            },
            bases=(rules.contrib.models.RulesModelMixin, models.Model),
        ),
    ]
