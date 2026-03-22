from django.db import migrations


def update_collage_type(apps, schema_editor):
    Collection = apps.get_model('memorabilia', 'Collection')
    for collection in Collection.objects.exclude(collage_collectible_ids=None):
        updated = False
        for entry in collection.collage_collectible_ids:
            if entry.get('type') == 'otheritem':
                entry['type'] = 'generalitem'
                updated = True
        if updated:
            collection.save(update_fields=['collage_collectible_ids'])


def reverse_collage_type(apps, schema_editor):
    Collection = apps.get_model('memorabilia', 'Collection')
    for collection in Collection.objects.exclude(collage_collectible_ids=None):
        updated = False
        for entry in collection.collage_collectible_ids:
            if entry.get('type') == 'generalitem':
                entry['type'] = 'otheritem'
                updated = True
        if updated:
            collection.save(update_fields=['collage_collectible_ids'])


class Migration(migrations.Migration):

    dependencies = [
        ('memorabilia', '0037_rename_otheritem_to_generalitem'),
    ]

    operations = [
        migrations.RunPython(update_collage_type, reverse_collage_type),
    ]
