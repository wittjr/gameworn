"""
Data migration: insert 'printed' CoaType, then migrate existing auth fields into
the new PlayerGearAuthentication, PlayerItemAuthentication, and GeneralItemAuthentication
tables.

Mapping rules for PlayerGear rows:
  - auth_tag_number non-empty OR coa set  → PlayerGearAuthentication(auth_type=coa,
      number=auth_tag_number, issuer=auth_source)
  - team_inventory_number non-empty       → PlayerGearAuthentication(auth_type='printed',
      number=team_inventory_number, issuer='TEAM')

Both conditions may fire independently, producing up to two records per item.

PlayerItem / GeneralItem rows:
  - coa set → one auth record (auth_type=coa, number='', issuer=None)
"""

from django.db import migrations


def migrate_auth_forward(apps, schema_editor):
    CoaType = apps.get_model('memorabilia', 'CoaType')
    AuthSource = apps.get_model('memorabilia', 'AuthSource')
    PlayerGear = apps.get_model('memorabilia', 'PlayerGear')
    PlayerItem = apps.get_model('memorabilia', 'PlayerItem')
    GeneralItem = apps.get_model('memorabilia', 'GeneralItem')
    PlayerGearAuthentication = apps.get_model('memorabilia', 'PlayerGearAuthentication')
    PlayerItemAuthentication = apps.get_model('memorabilia', 'PlayerItemAuthentication')
    GeneralItemAuthentication = apps.get_model('memorabilia', 'GeneralItemAuthentication')

    CoaType.objects.get_or_create(key='printed', defaults={'name': 'Printed on Jersey'})

    printed = CoaType.objects.get(key='printed')
    try:
        team_source = AuthSource.objects.get(pk='TEAM')
    except AuthSource.DoesNotExist:
        team_source = None

    for gear in PlayerGear.objects.all():
        auth_tag = (gear.auth_tag_number or '').strip()
        team_inv = (gear.team_inventory_number or '').strip()
        coa = gear.coa
        source = gear.auth_source

        if auth_tag or coa:
            PlayerGearAuthentication.objects.create(
                collectible=gear,
                auth_type=coa,
                number=auth_tag,
                issuer=source,
            )

        if team_inv:
            PlayerGearAuthentication.objects.create(
                collectible=gear,
                auth_type=printed,
                number=team_inv,
                issuer=team_source,
            )

    for item in PlayerItem.objects.all():
        if item.coa:
            PlayerItemAuthentication.objects.create(
                collectible=item,
                auth_type=item.coa,
                number='',
                issuer=None,
            )

    for item in GeneralItem.objects.all():
        if item.coa:
            GeneralItemAuthentication.objects.create(
                collectible=item,
                auth_type=item.coa,
                number='',
                issuer=None,
            )


def migrate_auth_backward(apps, schema_editor):
    PlayerGearAuthentication = apps.get_model('memorabilia', 'PlayerGearAuthentication')
    PlayerItemAuthentication = apps.get_model('memorabilia', 'PlayerItemAuthentication')
    GeneralItemAuthentication = apps.get_model('memorabilia', 'GeneralItemAuthentication')
    CoaType = apps.get_model('memorabilia', 'CoaType')
    PlayerGear = apps.get_model('memorabilia', 'PlayerGear')
    PlayerItem = apps.get_model('memorabilia', 'PlayerItem')
    GeneralItem = apps.get_model('memorabilia', 'GeneralItem')

    for auth in PlayerGearAuthentication.objects.select_related('auth_type', 'issuer').all():
        gear = auth.collectible
        if auth.auth_type and auth.auth_type.key == 'printed':
            gear.team_inventory_number = auth.number
        else:
            gear.coa = auth.auth_type
            gear.auth_tag_number = auth.number
            gear.auth_source = auth.issuer
        gear.save()

    for auth in PlayerItemAuthentication.objects.select_related('auth_type').all():
        item = auth.collectible
        item.coa = auth.auth_type
        item.save()

    for auth in GeneralItemAuthentication.objects.select_related('auth_type').all():
        item = auth.collectible
        item.coa = auth.auth_type
        item.save()

    PlayerGearAuthentication.objects.all().delete()
    PlayerItemAuthentication.objects.all().delete()
    GeneralItemAuthentication.objects.all().delete()
    CoaType.objects.filter(key='printed').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('memorabilia', '0056_add_authentication_tables'),
    ]

    operations = [
        migrations.RunPython(migrate_auth_forward, migrate_auth_backward),
    ]
