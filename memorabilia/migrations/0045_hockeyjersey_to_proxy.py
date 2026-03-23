import django.db.models.deletion
from django.db import migrations, models


def copy_hockeyjersey_to_playergear(apps, schema_editor):
    HockeyJersey = apps.get_model('memorabilia', 'HockeyJersey')
    PlayerGear = apps.get_model('memorabilia', 'PlayerGear')
    HockeyJerseyImage = apps.get_model('memorabilia', 'HockeyJerseyImage')
    PlayerGearImage = apps.get_model('memorabilia', 'PlayerGearImage')
    Collection = apps.get_model('memorabilia', 'Collection')

    pk_map = {}  # old_jersey_pk -> new_playergear_pk

    for jersey in HockeyJersey.objects.all():
        gear = PlayerGear(
            title=jersey.title,
            description=jersey.description,
            collection_id=jersey.collection_id,
            for_sale=jersey.for_sale,
            for_trade=jersey.for_trade,
            asking_price=jersey.asking_price,
            how_obtained=jersey.how_obtained,
            coa_id=jersey.coa_id,
            looking_for_id=jersey.looking_for_id,
            league=jersey.league,
            player=jersey.player,
            team=jersey.team,
            number=jersey.number,
            brand=jersey.brand,
            size=jersey.size,
            season=jersey.season,
            game_type_id=jersey.game_type_id,
            usage_type_id=jersey.usage_type_id,
            gear_type_id='JRS',
            season_set_id=jersey.season_set_id,
        )
        gear.save()
        # Preserve last_updated (auto_now bypassed via update())
        PlayerGear.objects.filter(pk=gear.pk).update(last_updated=jersey.last_updated)
        pk_map[jersey.pk] = gear.pk

        for img in HockeyJerseyImage.objects.filter(collectible_id=jersey.pk):
            PlayerGearImage.objects.create(
                collectible_id=gear.pk,
                primary=img.primary,
                image=img.image,
                link=img.link,
                flickrObject=img.flickrObject,
            )

    # Update collage_collectible_ids JSON
    for collection in Collection.objects.filter(collage_collectible_ids__isnull=False):
        updated = []
        changed = False
        for entry in collection.collage_collectible_ids:
            if entry.get('type') == 'hockeyjersey' and entry.get('id') in pk_map:
                updated.append({'type': 'hockeyjersey', 'id': pk_map[entry['id']]})
                changed = True
            else:
                updated.append(entry)
        if changed:
            collection.collage_collectible_ids = updated
            collection.save(update_fields=['collage_collectible_ids'])


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ('memorabilia', '0044_rename_loa_column_to_coa'),
    ]

    operations = [
        # 1. Add season_set to playergear table
        migrations.AddField(
            model_name='playergear',
            name='season_set',
            field=models.ForeignKey(
                blank=True,
                db_column='season_set',
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                to='memorabilia.seasonset',
                to_field='key',
            ),
        ),
        # 2. Copy data from hockeyjersey to playergear
        migrations.RunPython(copy_hockeyjersey_to_playergear, noop),
        # 3. Delete HockeyJerseyImage model
        migrations.DeleteModel(
            name='HockeyJerseyImage',
        ),
        # 4. Delete HockeyJersey concrete model
        migrations.DeleteModel(
            name='HockeyJersey',
        ),
        # 5. Create HockeyJersey as proxy of PlayerGear
        migrations.CreateModel(
            name='HockeyJersey',
            fields=[],
            options={
                'proxy': True,
                'indexes': [],
                'constraints': [],
            },
            bases=('memorabilia.playergear',),
        ),
    ]
