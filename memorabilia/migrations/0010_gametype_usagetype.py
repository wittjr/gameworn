# Generated by Django 5.0.7 on 2024-08-24 02:17

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('memorabilia', '0009_remove_league_id_league_key'),
    ]

    operations = [
        migrations.CreateModel(
            name='GameType',
            fields=[
                ('key', models.CharField(max_length=5, primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=100)),
            ],
        ),
        migrations.CreateModel(
            name='UsageType',
            fields=[
                ('key', models.CharField(max_length=5, primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=100)),
            ],
        ),
    ]