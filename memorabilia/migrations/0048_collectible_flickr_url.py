from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('memorabilia', '0047_userprofile'),
    ]

    operations = [
        migrations.AddField(
            model_name='generalitem',
            name='flickr_url',
            field=models.CharField(blank=True, default='', max_length=255),
        ),
        migrations.AddField(
            model_name='playergear',
            name='flickr_url',
            field=models.CharField(blank=True, default='', max_length=255),
        ),
        migrations.AddField(
            model_name='playeritem',
            name='flickr_url',
            field=models.CharField(blank=True, default='', max_length=255),
        ),
    ]
