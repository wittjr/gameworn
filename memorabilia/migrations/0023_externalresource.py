# Generated by Django 5.2.3 on 2025-06-28 15:18

import rules.contrib.models
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('memorabilia', '0022_collectible_last_updated_collection_last_updated'),
    ]

    operations = [
        migrations.CreateModel(
            name='ExternalResource',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=100)),
                ('description', models.CharField(max_length=255)),
                ('link', models.CharField(blank=True, max_length=255, null=True)),
            ],
            options={
                'abstract': False,
            },
            bases=(rules.contrib.models.RulesModelMixin, models.Model),
        ),
    ]
