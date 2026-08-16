import hashlib
import hmac
import tempfile

from django.test import TestCase, override_settings
from django.contrib.auth.models import User
from django.urls import reverse
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.templatetags.static import static

from ..models import Collection, PlayerItem, PlayerGear, HockeyJersey, GeneralItem, League, GameType, UsageType, GearType, SeasonSet, UserProfile, PlayerItemImage, PlayerGearImage, GeneralItemImage, PhotoMatch, AuthSource, WantListProfile, WantList, WantListItem, WantListItemImage, OwnerInquiry, InquiryMessage, GeneralItemAuthentication
from ..relay import ingest_inbound, extract_token, strip_quoted_reply, relay_message, relay_address
from ..templatetags.memorabilia_extras import get_user_avatar_url, getmediaurl, collage_rows

from .base import BaseTestCase

class PlayerItemCRUDTests(BaseTestCase):
    def setUp(self):
        self.client.force_login(self.owner)

    def test_create_get(self):
        response = self.client.get(
            reverse('memorabilia:create_collectible', args=[self.collection.id])
        )
        self.assertEqual(response.status_code, 200)

    def test_create_post(self):
        response = self.client.post(
            reverse('memorabilia:create_collectible', args=[self.collection.id]),
            self._player_item_post_data(title='Created Jersey'),
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(PlayerItem.objects.filter(title='Created Jersey').exists())

    def test_edit_get(self):
        response = self.client.get(reverse(
            'memorabilia:edit_collectible',
            args=[self.collection.id, 'playeritem', self.player_item.id],
        ))
        self.assertEqual(response.status_code, 200)

    def test_edit_post(self):
        response = self.client.post(
            reverse('memorabilia:edit_collectible',
                    args=[self.collection.id, 'playeritem', self.player_item.id]),
            self._player_item_post_data(title='Edited Jersey'),
        )
        self.assertEqual(response.status_code, 302)
        self.player_item.refresh_from_db()
        self.assertEqual(self.player_item.title, 'Edited Jersey')

    def test_delete_post(self):
        temp = PlayerItem.objects.create(
            title='Temp Jersey', description='temp', collection=self.collection,
            league='NHL', player='P',
        )
        response = self.client.post(reverse(
            'memorabilia:delete_collectible',
            args=[self.collection.id, 'playeritem', temp.id],
        ))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(PlayerItem.objects.filter(pk=temp.id).exists())

class PlayerGearCRUDTests(BaseTestCase):
    def setUp(self):
        self.client.force_login(self.owner)

    def test_create_post(self):
        response = self.client.post(
            reverse('memorabilia:create_collectible', args=[self.collection.id]),
            self._player_gear_post_data(title='Created Gear Jersey'),
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(PlayerGear.objects.filter(title='Created Gear Jersey').exists())

    def test_edit_get(self):
        response = self.client.get(reverse(
            'memorabilia:edit_collectible',
            args=[self.collection.id, 'playergear', self.player_gear.id],
        ))
        self.assertEqual(response.status_code, 200)

    def test_edit_post(self):
        response = self.client.post(
            reverse('memorabilia:edit_collectible',
                    args=[self.collection.id, 'playergear', self.player_gear.id]),
            self._player_gear_post_data(title='Edited Gear Jersey'),
        )
        self.assertEqual(response.status_code, 302)
        self.player_gear.refresh_from_db()
        self.assertEqual(self.player_gear.title, 'Edited Gear Jersey')

    def test_delete_post(self):
        temp = PlayerGear.objects.create(
            title='Temp Gear Jersey', description='temp', collection=self.collection,
            league='NHL', player='P', brand='Adidas', size='L',
            season='2024', game_type=self.game_type, usage_type=self.usage_type,
        )
        response = self.client.post(reverse(
            'memorabilia:delete_collectible',
            args=[self.collection.id, 'playergear', temp.id],
        ))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(PlayerGear.objects.filter(pk=temp.id).exists())

class GeneralItemCRUDTests(BaseTestCase):
    def setUp(self):
        self.client.force_login(self.owner)

    def test_create_post(self):
        response = self.client.post(
            reverse('memorabilia:create_collectible', args=[self.collection.id]),
            self._general_item_post_data(title='Created Puck'),
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(GeneralItem.objects.filter(title='Created Puck').exists())

    def test_edit_get(self):
        response = self.client.get(reverse(
            'memorabilia:edit_collectible',
            args=[self.collection.id, 'generalitem', self.general_item.id],
        ))
        self.assertEqual(response.status_code, 200)

    def test_edit_post(self):
        response = self.client.post(
            reverse('memorabilia:edit_collectible',
                    args=[self.collection.id, 'generalitem', self.general_item.id]),
            self._general_item_post_data(title='Edited Puck'),
        )
        self.assertEqual(response.status_code, 302)
        self.general_item.refresh_from_db()
        self.assertEqual(self.general_item.title, 'Edited Puck')

    def test_delete_post(self):
        temp = GeneralItem.objects.create(
            title='Temp Puck', description='temp', collection=self.collection,
        )
        response = self.client.post(reverse(
            'memorabilia:delete_collectible',
            args=[self.collection.id, 'generalitem', temp.id],
        ))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(GeneralItem.objects.filter(pk=temp.id).exists())

class CollectiblePermissionTests(BaseTestCase):
    def test_edit_playeritem_requires_login(self):
        response = self.client.get(reverse(
            'memorabilia:edit_collectible',
            args=[self.collection.id, 'playeritem', self.player_item.id],
        ))
        self.assertEqual(response.status_code, 302)
        self.assertIn('login', response['Location'])

    def test_edit_playergear_requires_login(self):
        response = self.client.get(reverse(
            'memorabilia:edit_collectible',
            args=[self.collection.id, 'playergear', self.player_gear.id],
        ))
        self.assertEqual(response.status_code, 302)
        self.assertIn('login', response['Location'])

    def test_edit_playeritem_other_user_forbidden(self):
        self.client.force_login(self.other_user)
        response = self.client.get(reverse(
            'memorabilia:edit_collectible',
            args=[self.collection.id, 'playeritem', self.player_item.id],
        ))
        self.assertEqual(response.status_code, 403)

    def test_delete_playeritem_other_user_forbidden(self):
        self.client.force_login(self.other_user)
        response = self.client.post(reverse(
            'memorabilia:delete_collectible',
            args=[self.collection.id, 'playeritem', self.player_item.id],
        ))
        self.assertEqual(response.status_code, 403)

    def test_edit_playergear_other_user_forbidden(self):
        self.client.force_login(self.other_user)
        response = self.client.get(reverse(
            'memorabilia:edit_collectible',
            args=[self.collection.id, 'playergear', self.player_gear.id],
        ))
        self.assertEqual(response.status_code, 403)

    def test_delete_playergear_other_user_forbidden(self):
        self.client.force_login(self.other_user)
        response = self.client.post(reverse(
            'memorabilia:delete_collectible',
            args=[self.collection.id, 'playergear', self.player_gear.id],
        ))
        self.assertEqual(response.status_code, 403)

    def test_delete_generalitem_other_user_forbidden(self):
        self.client.force_login(self.other_user)
        response = self.client.post(reverse(
            'memorabilia:delete_collectible',
            args=[self.collection.id, 'generalitem', self.general_item.id],
        ))
        self.assertEqual(response.status_code, 403)

    def test_edit_generalitem_other_user_forbidden(self):
        self.client.force_login(self.other_user)
        response = self.client.get(reverse(
            'memorabilia:edit_collectible',
            args=[self.collection.id, 'generalitem', self.general_item.id],
        ))
        self.assertEqual(response.status_code, 403)

    def test_edit_hockeyjersey_requires_login(self):
        response = self.client.get(reverse(
            'memorabilia:edit_collectible',
            args=[self.collection.id, 'hockeyjersey', self.hockey_jersey.id],
        ))
        self.assertEqual(response.status_code, 302)
        self.assertIn('login', response['Location'])

    def test_edit_hockeyjersey_other_user_forbidden(self):
        self.client.force_login(self.other_user)
        response = self.client.get(reverse(
            'memorabilia:edit_collectible',
            args=[self.collection.id, 'hockeyjersey', self.hockey_jersey.id],
        ))
        self.assertEqual(response.status_code, 403)

    def test_delete_hockeyjersey_other_user_forbidden(self):
        self.client.force_login(self.other_user)
        response = self.client.post(reverse(
            'memorabilia:delete_collectible',
            args=[self.collection.id, 'hockeyjersey', self.hockey_jersey.id],
        ))
        self.assertEqual(response.status_code, 403)

    def test_create_collectible_in_other_collection_forbidden(self):
        other_collection = Collection.objects.create(owner_uid=self.other_user.id, title='Other')
        self.client.force_login(self.owner)
        response = self.client.post(
            reverse('memorabilia:create_collectible', args=[other_collection.id]),
            self._player_item_post_data(collection=other_collection.id),
        )
        self.assertEqual(response.status_code, 403)

class CollectibleTypeConversionTests(BaseTestCase):
    def setUp(self):
        self.client.force_login(self.owner)

    def test_playeritem_to_playergear(self):
        item = PlayerItem.objects.create(
            title='Convert Me', description='desc', collection=self.collection,
            league='NHL', player='P',
        )
        old_pk = item.pk
        response = self.client.post(
            reverse('memorabilia:edit_collectible', args=[self.collection.id, 'playeritem', item.id]),
            self._player_gear_post_data(title='Convert Me'),
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(PlayerItem.objects.filter(pk=old_pk).exists())
        self.assertTrue(PlayerGear.objects.filter(title='Convert Me', collection=self.collection).exists())

    def test_playeritem_to_generalitem(self):
        item = PlayerItem.objects.create(
            title='Convert To Other', description='desc', collection=self.collection,
            league='NHL', player='P',
        )
        old_pk = item.pk
        response = self.client.post(
            reverse('memorabilia:edit_collectible', args=[self.collection.id, 'playeritem', item.id]),
            self._general_item_post_data(title='Convert To Other'),
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(PlayerItem.objects.filter(pk=old_pk).exists())
        self.assertTrue(GeneralItem.objects.filter(title='Convert To Other', collection=self.collection).exists())

    def test_playergear_to_playeritem(self):
        item = PlayerGear.objects.create(
            title='Gear To Player', description='desc', collection=self.collection,
            league='NHL', player='P', brand='Nike', size='M', season='2020',
            game_type=self.game_type, usage_type=self.usage_type,
        )
        old_pk = item.pk
        response = self.client.post(
            reverse('memorabilia:edit_collectible', args=[self.collection.id, 'playergear', item.id]),
            self._player_item_post_data(title='Gear To Player'),
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(PlayerGear.objects.filter(pk=old_pk).exists())
        self.assertTrue(PlayerItem.objects.filter(title='Gear To Player', collection=self.collection).exists())

    def test_playergear_to_generalitem(self):
        item = PlayerGear.objects.create(
            title='Gear To Other', description='desc', collection=self.collection,
            league='NHL', player='P', brand='Nike', size='M', season='2020',
            game_type=self.game_type, usage_type=self.usage_type,
        )
        old_pk = item.pk
        response = self.client.post(
            reverse('memorabilia:edit_collectible', args=[self.collection.id, 'playergear', item.id]),
            self._general_item_post_data(title='Gear To Other'),
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(PlayerGear.objects.filter(pk=old_pk).exists())
        self.assertTrue(GeneralItem.objects.filter(title='Gear To Other', collection=self.collection).exists())

    def test_generalitem_to_playeritem(self):
        item = GeneralItem.objects.create(
            title='Other To Player', description='desc', collection=self.collection,
        )
        old_pk = item.pk
        response = self.client.post(
            reverse('memorabilia:edit_collectible', args=[self.collection.id, 'generalitem', item.id]),
            self._player_item_post_data(title='Other To Player'),
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(GeneralItem.objects.filter(pk=old_pk).exists())
        self.assertTrue(PlayerItem.objects.filter(title='Other To Player', collection=self.collection).exists())

    def test_generalitem_to_playergear(self):
        item = GeneralItem.objects.create(
            title='Other To Gear', description='desc', collection=self.collection,
        )
        old_pk = item.pk
        response = self.client.post(
            reverse('memorabilia:edit_collectible', args=[self.collection.id, 'generalitem', item.id]),
            self._player_gear_post_data(title='Other To Gear'),
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(GeneralItem.objects.filter(pk=old_pk).exists())
        self.assertTrue(PlayerGear.objects.filter(title='Other To Gear', collection=self.collection).exists())

    def test_type_conversion_invalid_data_returns_form(self):
        """Invalid data during type conversion should not delete the original and should return 200."""
        item = PlayerItem.objects.create(
            title='Stay Safe', description='desc', collection=self.collection,
            league='NHL', player='P',
        )
        old_pk = item.pk
        # Post PlayerGear type but omit required gear fields
        response = self.client.post(
            reverse('memorabilia:edit_collectible', args=[self.collection.id, 'playeritem', item.id]),
            {'collectible_type': 'PlayerGear', 'title': '', 'collection': self.collection.id,
             'images-TOTAL_FORMS': '0', 'images-INITIAL_FORMS': '0',
             'images-MIN_NUM_FORMS': '0', 'images-MAX_NUM_FORMS': '1000'},
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(PlayerItem.objects.filter(pk=old_pk).exists())

class BulkEditViewTests(BaseTestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        # Dedicated collection for bulk edit so we control exactly what's in the formsets
        cls.bulk_collection = Collection.objects.create(owner_uid=cls.owner.id, title='Bulk Collection')
        cls.bulk_gear = PlayerGear.objects.create(
            title='Bulk Gear', description='desc', collection=cls.bulk_collection,
            league='NHL', player='P', brand='Nike', size='M', season='2020',
            game_type=cls.game_type, usage_type=cls.usage_type,
        )
        cls.bulk_player = PlayerItem.objects.create(
            title='Bulk Player', description='desc', collection=cls.bulk_collection,
            league='NHL', player='Q',
        )
        cls.bulk_other = GeneralItem.objects.create(
            title='Bulk Other', description='desc', collection=cls.bulk_collection,
        )

    def _empty_formset(self, prefix):
        return {
            f'{prefix}-TOTAL_FORMS': '0',
            f'{prefix}-INITIAL_FORMS': '0',
            f'{prefix}-MIN_NUM_FORMS': '0',
            f'{prefix}-MAX_NUM_FORMS': '1000',
        }

    def _gear_formset(self, item, **overrides):
        data = {
            'gear-TOTAL_FORMS': '1', 'gear-INITIAL_FORMS': '1',
            'gear-MIN_NUM_FORMS': '0', 'gear-MAX_NUM_FORMS': '1000',
            'gear-0-id': str(item.pk),
            'gear-0-title': item.title,
            'gear-0-league': item.league,
            'gear-0-player': item.player,
            'gear-0-brand': item.brand,
            'gear-0-size': item.size,
            'gear-0-season': item.season,
            'gear-0-game_type': item.game_type_id,
            'gear-0-usage_type': item.usage_type_id,
            'gear-0-description': item.description,
        }
        data.update(overrides)
        return data

    def _player_formset(self, item, **overrides):
        data = {
            'player-TOTAL_FORMS': '1', 'player-INITIAL_FORMS': '1',
            'player-MIN_NUM_FORMS': '0', 'player-MAX_NUM_FORMS': '1000',
            'player-0-id': str(item.pk),
            'player-0-title': item.title,
            'player-0-league': item.league,
            'player-0-player': item.player,
            'player-0-description': item.description,
        }
        data.update(overrides)
        return data

    def _other_formset(self, item, **overrides):
        data = {
            'other-TOTAL_FORMS': '1', 'other-INITIAL_FORMS': '1',
            'other-MIN_NUM_FORMS': '0', 'other-MAX_NUM_FORMS': '1000',
            'other-0-id': str(item.pk),
            'other-0-title': item.title,
            'other-0-description': item.description,
        }
        data.update(overrides)
        return data

    def _bulk_url(self):
        return reverse('memorabilia:bulk_edit_collectibles', args=[self.bulk_collection.id])

    def test_get_requires_login(self):
        response = self.client.get(self._bulk_url())
        self.assertEqual(response.status_code, 302)
        self.assertIn('login', response['Location'])

    def test_get_other_user_forbidden(self):
        self.client.force_login(self.other_user)
        response = self.client.get(self._bulk_url())
        self.assertEqual(response.status_code, 403)

    def test_get_owner(self):
        self.client.force_login(self.owner)
        response = self.client.get(self._bulk_url())
        self.assertEqual(response.status_code, 200)
        self.assertIn('gear_formset', response.context)
        self.assertIn('player_formset', response.context)
        self.assertIn('other_formset', response.context)

    def test_post_save_gear_title(self):
        self.client.force_login(self.owner)
        post = (
            self._gear_formset(self.bulk_gear, **{'gear-0-title': 'Updated Gear'})
            | self._empty_formset('hockeyjersey')
            | self._empty_formset('player')
            | self._empty_formset('other')
        )
        response = self.client.post(self._bulk_url(), post)
        self.assertEqual(response.status_code, 302)
        self.bulk_gear.refresh_from_db()
        self.assertEqual(self.bulk_gear.title, 'Updated Gear')

    def test_post_save_player_title(self):
        self.client.force_login(self.owner)
        post = (
            self._empty_formset('gear')
            | self._empty_formset('hockeyjersey')
            | self._player_formset(self.bulk_player, **{'player-0-title': 'Updated Player'})
            | self._empty_formset('other')
        )
        response = self.client.post(self._bulk_url(), post)
        self.assertEqual(response.status_code, 302)
        self.bulk_player.refresh_from_db()
        self.assertEqual(self.bulk_player.title, 'Updated Player')

    def test_post_save_other_title(self):
        self.client.force_login(self.owner)
        post = (
            self._empty_formset('gear')
            | self._empty_formset('hockeyjersey')
            | self._empty_formset('player')
            | self._other_formset(self.bulk_other, **{'other-0-title': 'Updated Other'})
        )
        response = self.client.post(self._bulk_url(), post)
        self.assertEqual(response.status_code, 302)
        self.bulk_other.refresh_from_db()
        self.assertEqual(self.bulk_other.title, 'Updated Other')

    def test_post_delete_selected(self):
        self.client.force_login(self.owner)
        to_delete = PlayerItem.objects.create(
            title='Delete Me', description='desc', collection=self.bulk_collection, league='NHL', player='X',
        )
        response = self.client.post(self._bulk_url(), {
            'action': 'delete_selected',
            'delete_ids': [f'playeritem:{to_delete.pk}'],
        })
        self.assertEqual(response.status_code, 302)
        self.assertFalse(PlayerItem.objects.filter(pk=to_delete.pk).exists())

    def test_post_delete_other_collection_item_ignored(self):
        """delete_selected must not delete items from a different collection."""
        self.client.force_login(self.owner)
        other_item = PlayerItem.objects.create(
            title='Hands Off', description='desc', collection=self.collection, league='NHL', player='X',
        )
        self.client.post(self._bulk_url(), {
            'action': 'delete_selected',
            'delete_ids': [f'playeritem:{other_item.pk}'],
        })
        self.assertTrue(PlayerItem.objects.filter(pk=other_item.pk).exists())

    def test_post_type_conversion_gear_to_player(self):
        self.client.force_login(self.owner)
        item = PlayerGear.objects.create(
            title='Gear2Player', description='desc', collection=self.bulk_collection,
            league='NHL', player='R', brand='Nike', size='M', season='2020',
            game_type=self.game_type, usage_type=self.usage_type,
        )
        old_pk = item.pk
        post = (
            self._gear_formset(item, **{'item_type_gear-0': 'playeritem'})
            | self._empty_formset('hockeyjersey')
            | self._empty_formset('player')
            | self._empty_formset('other')
        )
        response = self.client.post(self._bulk_url(), post)
        self.assertEqual(response.status_code, 302)
        self.assertFalse(PlayerGear.objects.filter(pk=old_pk).exists())
        self.assertTrue(PlayerItem.objects.filter(title='Gear2Player', collection=self.bulk_collection).exists())

    def test_post_type_conversion_gear_to_general(self):
        self.client.force_login(self.owner)
        item = PlayerGear.objects.create(
            title='Gear2Other', description='desc', collection=self.bulk_collection,
            league='NHL', player='S', brand='Nike', size='M', season='2020',
            game_type=self.game_type, usage_type=self.usage_type,
        )
        old_pk = item.pk
        post = (
            self._gear_formset(item, **{'item_type_gear-0': 'generalitem'})
            | self._empty_formset('hockeyjersey')
            | self._empty_formset('player')
            | self._empty_formset('other')
        )
        response = self.client.post(self._bulk_url(), post)
        self.assertEqual(response.status_code, 302)
        self.assertFalse(PlayerGear.objects.filter(pk=old_pk).exists())
        self.assertTrue(GeneralItem.objects.filter(title='Gear2Other', collection=self.bulk_collection).exists())

    def test_post_type_conversion_player_to_general(self):
        self.client.force_login(self.owner)
        item = PlayerItem.objects.create(
            title='Player2Other', description='desc', collection=self.bulk_collection,
            league='NHL', player='T',
        )
        old_pk = item.pk
        post = (
            self._empty_formset('gear')
            | self._empty_formset('hockeyjersey')
            | self._player_formset(item, **{'item_type_player-0': 'generalitem'})
            | self._empty_formset('other')
        )
        response = self.client.post(self._bulk_url(), post)
        self.assertEqual(response.status_code, 302)
        self.assertFalse(PlayerItem.objects.filter(pk=old_pk).exists())
        self.assertTrue(GeneralItem.objects.filter(title='Player2Other', collection=self.bulk_collection).exists())

    def test_post_type_conversion_general_to_player(self):
        self.client.force_login(self.owner)
        item = GeneralItem.objects.create(
            title='Other2Player', description='desc', collection=self.bulk_collection,
        )
        old_pk = item.pk
        post = (
            self._empty_formset('gear')
            | self._empty_formset('hockeyjersey')
            | self._empty_formset('player')
            | self._other_formset(item, **{
                'item_type_other-0': 'playeritem',
                'other-0-league': 'NHL',
                'other-0-player': 'U',
            })
        )
        response = self.client.post(self._bulk_url(), post)
        self.assertEqual(response.status_code, 302)
        self.assertFalse(GeneralItem.objects.filter(pk=old_pk).exists())
        self.assertTrue(PlayerItem.objects.filter(title='Other2Player', collection=self.bulk_collection).exists())

    def test_post_type_conversion_gear_to_hockeyjersey_no_duplication(self):
        """Converting a PlayerGear to HockeyJersey must create exactly 1 new item."""
        self.client.force_login(self.owner)
        gear_type_other, _ = GearType.objects.get_or_create(key='OTH', defaults={'name': 'Other'})
        GearType.objects.get_or_create(key='JRS', defaults={'name': 'Jersey'})
        item = PlayerGear.objects.create(
            title='GearToJersey', description='desc', collection=self.bulk_collection,
            league='NHL', player='V', brand='Nike', size='L', season='2021',
            game_type=self.game_type, usage_type=self.usage_type,
            gear_type=gear_type_other,
        )
        old_pk = item.pk
        # Include coa='' to trigger the ModelChoiceField.has_changed(None, '') edge case
        post = (
            self._gear_formset(item, **{
                'item_type_gear-0': 'hockeyjersey',
                'gear-0-gear_type': 'OTH',
                'gear-0-coa': '',
            })
            | self._empty_formset('hockeyjersey')
            | self._empty_formset('player')
            | self._empty_formset('other')
        )
        response = self.client.post(self._bulk_url(), post)
        self.assertEqual(response.status_code, 302)
        # Old PlayerGear row should be gone
        self.assertFalse(PlayerGear.objects.filter(pk=old_pk).exists())
        # Exactly 1 HockeyJersey with this title
        jerseys = HockeyJersey.objects.filter(title='GearToJersey', collection=self.bulk_collection)
        self.assertEqual(jerseys.count(), 1)
        # No stray PlayerGear
        self.assertFalse(PlayerGear.objects.filter(title='GearToJersey', collection=self.bulk_collection).exclude(gear_type_id='JRS').exists())

class CollectibleDetailContextTests(BaseTestCase):
    def test_playeritem_detail_context_has_league(self):
        response = self.client.get(reverse(
            'memorabilia:collectible',
            kwargs={'collection_id': self.collection.id, 'collectible_type': 'playeritem', 'pk': self.player_item.id},
        ))
        self.assertIn('league', response.context)

    def test_playergear_detail_context_has_league_and_image(self):
        response = self.client.get(reverse(
            'memorabilia:collectible',
            kwargs={'collection_id': self.collection.id, 'collectible_type': 'playergear', 'pk': self.player_gear.id},
        ))
        self.assertIn('league', response.context)
        self.assertIn('primary_image', response.context)

    def test_generalitem_detail_no_league_in_context(self):
        response = self.client.get(reverse(
            'memorabilia:collectible',
            kwargs={'collection_id': self.collection.id, 'collectible_type': 'generalitem', 'pk': self.general_item.id},
        ))
        self.assertNotIn('league', response.context)

    def test_playeritem_uses_correct_template(self):
        response = self.client.get(reverse(
            'memorabilia:collectible',
            kwargs={'collection_id': self.collection.id, 'collectible_type': 'playeritem', 'pk': self.player_item.id},
        ))
        self.assertTemplateUsed(response, 'memorabilia/playeritem_detail.html')

    def test_playergear_uses_correct_template(self):
        response = self.client.get(reverse(
            'memorabilia:collectible',
            kwargs={'collection_id': self.collection.id, 'collectible_type': 'playergear', 'pk': self.player_gear.id},
        ))
        self.assertTemplateUsed(response, 'memorabilia/playergear_detail.html')

    def test_generalitem_uses_correct_template(self):
        response = self.client.get(reverse(
            'memorabilia:collectible',
            kwargs={'collection_id': self.collection.id, 'collectible_type': 'generalitem', 'pk': self.general_item.id},
        ))
        self.assertTemplateUsed(response, 'memorabilia/generalitem_detail.html')

class Collectible404Tests(BaseTestCase):
    def test_playeritem_wrong_pk(self):
        response = self.client.get(reverse(
            'memorabilia:collectible',
            kwargs={'collection_id': self.collection.id, 'collectible_type': 'playeritem', 'pk': 999999},
        ))
        self.assertEqual(response.status_code, 404)

    def test_playeritem_wrong_collection(self):
        other_collection = Collection.objects.create(owner_uid=self.owner.id, title='Other')
        response = self.client.get(reverse(
            'memorabilia:collectible',
            kwargs={'collection_id': other_collection.id, 'collectible_type': 'playeritem', 'pk': self.player_item.id},
        ))
        self.assertEqual(response.status_code, 404)

    def test_playergear_wrong_pk(self):
        response = self.client.get(reverse(
            'memorabilia:collectible',
            kwargs={'collection_id': self.collection.id, 'collectible_type': 'playergear', 'pk': 999999},
        ))
        self.assertEqual(response.status_code, 404)

    def test_generalitem_wrong_pk(self):
        response = self.client.get(reverse(
            'memorabilia:collectible',
            kwargs={'collection_id': self.collection.id, 'collectible_type': 'generalitem', 'pk': 999999},
        ))
        self.assertEqual(response.status_code, 404)

    def test_playergear_wrong_collection(self):
        other_collection = Collection.objects.create(owner_uid=self.owner.id, title='Other')
        response = self.client.get(reverse(
            'memorabilia:collectible',
            kwargs={'collection_id': other_collection.id, 'collectible_type': 'playergear', 'pk': self.player_gear.id},
        ))
        self.assertEqual(response.status_code, 404)

    def test_generalitem_wrong_collection(self):
        other_collection = Collection.objects.create(owner_uid=self.owner.id, title='Other')
        response = self.client.get(reverse(
            'memorabilia:collectible',
            kwargs={'collection_id': other_collection.id, 'collectible_type': 'generalitem', 'pk': self.general_item.id},
        ))
        self.assertEqual(response.status_code, 404)

    def test_hockeyjersey_wrong_pk(self):
        response = self.client.get(reverse(
            'memorabilia:collectible',
            kwargs={'collection_id': self.collection.id, 'collectible_type': 'hockeyjersey', 'pk': 999999},
        ))
        self.assertEqual(response.status_code, 404)

    def test_hockeyjersey_wrong_collection(self):
        other_collection = Collection.objects.create(owner_uid=self.owner.id, title='Other')
        response = self.client.get(reverse(
            'memorabilia:collectible',
            kwargs={'collection_id': other_collection.id, 'collectible_type': 'hockeyjersey', 'pk': self.hockey_jersey.id},
        ))
        self.assertEqual(response.status_code, 404)

    def test_unrecognized_collectible_type_404(self):
        """CollectibleView.get_object() falls through to Http404 for a type
        it doesn't recognize — unlike edit/delete_collectible, which default
        to PlayerItem (see CollectibleDispatchFallbackTests). Both behaviors
        are pre-existing; this locks in the CollectibleView side before the
        collectible_type -> model dispatch is consolidated onto a registry."""
        response = self.client.get(reverse(
            'memorabilia:collectible',
            kwargs={'collection_id': self.collection.id, 'collectible_type': 'bogus', 'pk': self.player_item.id},
        ))
        self.assertEqual(response.status_code, 404)

class CollectiblePdfTests(BaseTestCase):
    """collectible_pdf had no prior test coverage. Added ahead of the
    collectible_type -> model dispatch consolidation (SOLID #1) so a
    regression in the refactored fetch/prefetch logic fails loudly."""

    def _pdf_url(self, collectible_type, pk):
        return reverse('memorabilia:collectible_pdf', kwargs={
            'collection_id': self.collection.id, 'collectible_type': collectible_type, 'pk': pk,
        })

    def test_playeritem_pdf_owner_200(self):
        self.client.force_login(self.owner)
        response = self.client.get(self._pdf_url('playeritem', self.player_item.id))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')

    def test_playergear_pdf_owner_200(self):
        PlayerGearImage.objects.create(collectible=self.player_gear, link='https://example.com/g.jpg', primary=True)
        self.client.force_login(self.owner)
        response = self.client.get(self._pdf_url('playergear', self.player_gear.id))
        self.assertEqual(response.status_code, 200)

    def test_hockeyjersey_pdf_owner_200(self):
        PlayerGearImage.objects.create(collectible=self.hockey_jersey, link='https://example.com/j.jpg', primary=True)
        self.client.force_login(self.owner)
        response = self.client.get(self._pdf_url('hockeyjersey', self.hockey_jersey.id))
        self.assertEqual(response.status_code, 200)

    def test_generalitem_pdf_owner_200(self):
        self.client.force_login(self.owner)
        response = self.client.get(self._pdf_url('generalitem', self.general_item.id))
        self.assertEqual(response.status_code, 200)

    def test_wrong_pk_404(self):
        self.client.force_login(self.owner)
        response = self.client.get(self._pdf_url('playeritem', 999999))
        self.assertEqual(response.status_code, 404)

    def test_unrecognized_collectible_type_404(self):
        self.client.force_login(self.owner)
        response = self.client.get(self._pdf_url('bogus', self.player_item.id))
        self.assertEqual(response.status_code, 404)

    def test_non_owner_forbidden(self):
        self.client.force_login(self.other_user)
        response = self.client.get(self._pdf_url('playeritem', self.player_item.id))
        self.assertEqual(response.status_code, 403)

    def test_requires_login(self):
        response = self.client.get(self._pdf_url('playeritem', self.player_item.id))
        self.assertEqual(response.status_code, 302)

class CollectibleDispatchFallbackTests(BaseTestCase):
    """delete_collectible and edit_collectible both default an unrecognized
    collectible_type to PlayerItem rather than 404ing (unlike CollectibleView/
    collectible_pdf). This is pre-existing, inconsistent-but-real behavior for
    the collectible-fetch dispatch — locked in here so it doesn't silently
    change.

    edit_collectible used to 500 for an unrecognized type: its collectible-
    fetch dispatch defaults to PlayerItem, but _get_auth_formset_class()
    defaulted unrecognized types to GeneralItemAuthenticationFormSet —
    building that formset against the PlayerItem instance raised
    ValueError('Cannot query ...: Must be "GeneralItem" instance.'). Fixed by
    giving _get_auth_formset_class() an explicit 'generalitem' branch (it
    previously relied on the catch-all for that, same as the bug case) and
    making its catch-all default PlayerItem, matching _get_image_formset_class
    and the COLLECTIBLE_MODELS registry."""

    def test_delete_collectible_unrecognized_type_falls_back_to_playeritem(self):
        self.client.force_login(self.owner)
        response = self.client.post(reverse(
            'memorabilia:delete_collectible',
            kwargs={'collection_id': self.collection.id, 'collectible_type': 'bogus', 'collectible_id': self.player_item.id},
        ))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(PlayerItem.objects.filter(pk=self.player_item.id).exists())

    def test_edit_collectible_unrecognized_type_falls_back_to_playeritem_without_crashing(self):
        self.client.force_login(self.owner)
        response = self.client.get(reverse(
            'memorabilia:edit_collectible',
            kwargs={'collection_id': self.collection.id, 'collectible_type': 'bogus', 'collectible_id': self.player_item.id},
        ))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['collectible'], self.player_item)

    def test_edit_collectible_generalitem_still_uses_generalitem_auth_formset(self):
        """Regression guard: generalitem previously reached
        GeneralItemAuthenticationFormSet only via _get_auth_formset_class's
        catch-all branch. Fixing the catch-all to default to PlayerItem must
        not break this — generalitem needs its own explicit branch."""
        self.client.force_login(self.owner)
        response = self.client.get(reverse(
            'memorabilia:edit_collectible',
            kwargs={'collection_id': self.collection.id, 'collectible_type': 'generalitem', 'collectible_id': self.general_item.id},
        ))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['collectible'], self.general_item)
        self.assertEqual(response.context['auth_formset'].model, GeneralItemAuthentication)

class CollectibleFormValidationTests(BaseTestCase):
    def setUp(self):
        self.client.force_login(self.owner)

    def test_create_playeritem_missing_title_returns_200(self):
        response = self.client.post(
            reverse('memorabilia:create_collectible', args=[self.collection.id]),
            self._player_item_post_data(title=''),
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(PlayerItem.objects.filter(title='').exists())

    def test_create_playergear_missing_title_returns_200(self):
        response = self.client.post(
            reverse('memorabilia:create_collectible', args=[self.collection.id]),
            self._player_gear_post_data(title=''),
        )
        self.assertEqual(response.status_code, 200)

    def test_edit_playeritem_missing_title_returns_200(self):
        response = self.client.post(
            reverse('memorabilia:edit_collectible', args=[self.collection.id, 'playeritem', self.player_item.id]),
            self._player_item_post_data(title=''),
        )
        self.assertEqual(response.status_code, 200)
        self.player_item.refresh_from_db()
        self.assertNotEqual(self.player_item.title, '')

    def test_edit_playergear_missing_title_returns_200(self):
        response = self.client.post(
            reverse('memorabilia:edit_collectible', args=[self.collection.id, 'playergear', self.player_gear.id]),
            self._player_gear_post_data(title=''),
        )
        self.assertEqual(response.status_code, 200)
        self.player_gear.refresh_from_db()
        self.assertNotEqual(self.player_gear.title, '')

    def test_create_generalitem_missing_title_returns_200(self):
        response = self.client.post(
            reverse('memorabilia:create_collectible', args=[self.collection.id]),
            self._general_item_post_data(title=''),
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(GeneralItem.objects.filter(title='').exists())

    def test_edit_generalitem_missing_title_returns_200(self):
        response = self.client.post(
            reverse('memorabilia:edit_collectible', args=[self.collection.id, 'generalitem', self.general_item.id]),
            self._general_item_post_data(title=''),
        )
        self.assertEqual(response.status_code, 200)
        self.general_item.refresh_from_db()
        self.assertNotEqual(self.general_item.title, '')

class CollectiblePrimaryImageTests(BaseTestCase):
    """Regression tests for Collectible.get_images()/get_primary_image_obj()/get_primary_image()
    and per-type detail_queryset() — covers the DRY fix that unified the
    previously-duplicated 'primary image, else first' logic across PlayerItem,
    PlayerGear, HockeyJersey (proxy of PlayerGear), and GeneralItem."""

    # --- get_primary_image() / get_images() ---

    def test_no_images_returns_none_for_every_type(self):
        self.assertIsNone(self.player_item.get_primary_image())
        self.assertIsNone(self.player_gear.get_primary_image())
        self.assertIsNone(self.hockey_jersey.get_primary_image())
        self.assertIsNone(self.general_item.get_primary_image())

    def test_single_image_with_no_primary_flag_is_returned(self):
        PlayerItemImage.objects.create(collectible=self.player_item, link='https://example.com/a.jpg')
        self.assertEqual(self.player_item.get_primary_image(), 'https://example.com/a.jpg')

    def test_flagged_primary_image_preferred_over_first(self):
        PlayerGearImage.objects.create(collectible=self.player_gear, link='https://example.com/first.jpg')
        PlayerGearImage.objects.create(collectible=self.player_gear, link='https://example.com/primary.jpg', primary=True)
        self.assertEqual(self.player_gear.get_primary_image(), 'https://example.com/primary.jpg')

    def test_hockey_jersey_reads_gear_images_via_proxy_inheritance(self):
        """HockeyJersey is a proxy model of PlayerGear — it must resolve images
        through the inherited gear_images relation, not the base 'images' relation."""
        PlayerGearImage.objects.create(collectible=self.hockey_jersey, link='https://example.com/jersey.jpg', primary=True)
        self.assertEqual(self.hockey_jersey.get_primary_image(), 'https://example.com/jersey.jpg')
        self.assertEqual(list(self.hockey_jersey.get_images()), list(self.hockey_jersey.gear_images.all()))

    def test_get_images_uses_images_relation_for_general_item(self):
        GeneralItemImage.objects.create(collectible=self.general_item, link='https://example.com/g.jpg')
        self.assertEqual(list(self.general_item.get_images()), list(self.general_item.images.all()))

    def test_get_primary_image_obj_returns_the_image_instance_not_its_value(self):
        img = PlayerItemImage.objects.create(collectible=self.player_item, link='https://example.com/a.jpg', primary=True)
        self.assertEqual(self.player_item.get_primary_image_obj(), img)

    # --- detail_queryset() ---

    def test_detail_queryset_fetches_the_right_instance_per_type(self):
        self.assertEqual(PlayerItem.detail_queryset().get(pk=self.player_item.pk), self.player_item)
        self.assertEqual(PlayerGear.detail_queryset().get(pk=self.player_gear.pk), self.player_gear)
        self.assertEqual(HockeyJersey.detail_queryset().get(pk=self.hockey_jersey.pk), self.hockey_jersey)
        self.assertEqual(GeneralItem.detail_queryset().get(pk=self.general_item.pk), self.general_item)

    def test_detail_queryset_prefetches_avoid_extra_queries_on_touch(self):
        """Touching the relations detail_queryset() is supposed to prefetch must not
        issue additional queries beyond the initial fetch + one per prefetched
        relation group (gear_images, authentications, photomatches) — regression
        guard against silently dropping a prefetch_related()/select_related() call
        in a future edit. select_related fields (game_type/usage_type/gear_type/
        season_set) are joined into the first query, so they add no extra queries."""
        PlayerGearImage.objects.create(collectible=self.player_gear, link='https://example.com/g.jpg')
        with self.assertNumQueries(4):
            obj = PlayerGear.detail_queryset().get(pk=self.player_gear.pk)
            list(obj.gear_images.all())
            list(obj.authentications.all())
            list(obj.photomatches.all())
            obj.game_type
            obj.usage_type
            obj.gear_type

        PlayerGearImage.objects.create(collectible=self.hockey_jersey, link='https://example.com/j.jpg')
        with self.assertNumQueries(4):
            obj = HockeyJersey.detail_queryset().get(pk=self.hockey_jersey.pk)
            list(obj.gear_images.all())
            list(obj.authentications.all())
            list(obj.photomatches.all())
            obj.game_type
            obj.usage_type
            obj.gear_type
            obj.season_set

class UploadedImageEditDisplayTests(BaseTestCase):
    """Regression: uploaded images must render as <img> tags on the edit form, not as a file input widget."""

    # Minimal 1×1 red PNG — valid enough for ImageField
    PNG_1PX = (
        b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01'
        b'\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00'
        b'\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82'
    )

    def setUp(self):
        self.client.force_login(self.owner)

    @override_settings(MEDIA_ROOT=tempfile.mkdtemp())
    def test_uploaded_image_renders_as_img_tag_on_edit(self):
        from memorabilia.models import PlayerItemImage
        img_file = SimpleUploadedFile('test.png', self.PNG_1PX, content_type='image/png')
        image_record = PlayerItemImage.objects.create(
            collectible=self.player_item,
            image=img_file,
            primary=True,
        )
        response = self.client.get(reverse(
            'memorabilia:edit_collectible',
            args=[self.collection.id, 'playeritem', self.player_item.id],
        ))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, image_record.image.url)

    @override_settings(MEDIA_ROOT=tempfile.mkdtemp())
    def test_uploaded_image_does_not_render_as_file_input_only(self):
        """The image field value must not be surfaced as a bare ClearableFileInput on the edit page."""
        from memorabilia.models import PlayerItemImage
        img_file = SimpleUploadedFile('test2.png', self.PNG_1PX, content_type='image/png')
        PlayerItemImage.objects.create(
            collectible=self.player_item,
            image=img_file,
            primary=True,
        )
        response = self.client.get(reverse(
            'memorabilia:edit_collectible',
            args=[self.collection.id, 'playeritem', self.player_item.id],
        ))
        # The file input for an existing image should be hidden, not the primary visible element.
        # If it were rendered as a visible widget, the label tag would appear prominently.
        self.assertNotContains(response, 'Image:</label>')

class ImageFileDeletionTests(BaseTestCase):
    """
    File cleanup: calling .delete() on an image record with an uploaded file must
    remove the file from disk. This covers the formset "Keep" un-check path, which
    calls obj.delete() directly on each marked instance.

    Note: Django's CASCADE delete (when the parent collectible is deleted) uses SQL
    bulk deletes that bypass the Python delete() method, so cascade paths do NOT
    trigger file cleanup. That is a known limitation and a separate concern.
    """

    PNG_1PX = (
        b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01'
        b'\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00'
        b'\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82'
    )

    def _upload(self, name='test.png'):
        return SimpleUploadedFile(name, self.PNG_1PX, content_type='image/png')

    @override_settings(MEDIA_ROOT=tempfile.mkdtemp())
    def test_player_item_image_delete_removes_file(self):
        import os
        record = PlayerItemImage.objects.create(
            collectible=self.player_item,
            image=self._upload('pi.png'),
        )
        path = record.image.path
        self.assertTrue(os.path.exists(path))
        record.delete()
        self.assertFalse(os.path.exists(path))

    @override_settings(MEDIA_ROOT=tempfile.mkdtemp())
    def test_player_gear_image_delete_removes_file(self):
        import os
        record = PlayerGearImage.objects.create(
            collectible=self.player_gear,
            image=self._upload('pg.png'),
        )
        path = record.image.path
        self.assertTrue(os.path.exists(path))
        record.delete()
        self.assertFalse(os.path.exists(path))

    @override_settings(MEDIA_ROOT=tempfile.mkdtemp())
    def test_general_item_image_delete_removes_file(self):
        import os
        record = GeneralItemImage.objects.create(
            collectible=self.general_item,
            image=self._upload('gi.png'),
        )
        path = record.image.path
        self.assertTrue(os.path.exists(path))
        record.delete()
        self.assertFalse(os.path.exists(path))

    @override_settings(MEDIA_ROOT=tempfile.mkdtemp())
    def test_photomatch_delete_removes_file(self):
        import os, datetime
        record = PhotoMatch.objects.create(
            collectible=self.player_gear,
            image=self._upload('pm.png'),
            game_date=datetime.date(2024, 1, 1),
        )
        path = record.image.path
        self.assertTrue(os.path.exists(path))
        record.delete()
        self.assertFalse(os.path.exists(path))

    @override_settings(MEDIA_ROOT=tempfile.mkdtemp())
    def test_link_only_image_delete_does_not_crash(self):
        """An image record with only a Flickr link (no uploaded file) must be deletable without error."""
        record = PlayerItemImage.objects.create(
            collectible=self.player_item,
            link='https://live.staticflickr.com/example/photo.jpg',
        )
        record.delete()  # must not raise
        self.assertFalse(PlayerItemImage.objects.filter(pk=record.pk).exists())

    @override_settings(MEDIA_ROOT=tempfile.mkdtemp())
    def test_photomatch_link_only_delete_does_not_crash(self):
        """A PhotoMatch with only a link (no uploaded file) must be deletable without error."""
        import datetime
        record = PhotoMatch.objects.create(
            collectible=self.player_gear,
            link='https://live.staticflickr.com/example/photo.jpg',
            game_date=datetime.date(2024, 1, 1),
        )
        record.delete()  # must not raise
        self.assertFalse(PhotoMatch.objects.filter(pk=record.pk).exists())

class HockeyJerseyCRUDTests(BaseTestCase):
    def setUp(self):
        self.client.force_login(self.owner)

    def test_create_get(self):
        response = self.client.get(
            reverse('memorabilia:create_collectible', args=[self.collection.id])
        )
        self.assertEqual(response.status_code, 200)

    def test_create_post(self):
        response = self.client.post(
            reverse('memorabilia:create_collectible', args=[self.collection.id]),
            self._hockey_jersey_post_data(title='Created Hockey Jersey'),
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(HockeyJersey.objects.filter(title='Created Hockey Jersey').exists())

    def test_create_post_auto_sets_gear_type_jrs(self):
        self.client.post(
            reverse('memorabilia:create_collectible', args=[self.collection.id]),
            self._hockey_jersey_post_data(title='Auto GearType Jersey'),
        )
        jersey = HockeyJersey.objects.get(title='Auto GearType Jersey')
        self.assertEqual(jersey.gear_type_id, 'JRS')

    def test_edit_get(self):
        response = self.client.get(reverse(
            'memorabilia:edit_collectible',
            args=[self.collection.id, 'hockeyjersey', self.hockey_jersey.id],
        ))
        self.assertEqual(response.status_code, 200)

    def test_edit_post(self):
        response = self.client.post(
            reverse('memorabilia:edit_collectible',
                    args=[self.collection.id, 'hockeyjersey', self.hockey_jersey.id]),
            self._hockey_jersey_post_data(title='Edited Hockey Jersey'),
        )
        self.assertEqual(response.status_code, 302)
        self.hockey_jersey.refresh_from_db()
        self.assertEqual(self.hockey_jersey.title, 'Edited Hockey Jersey')

    def test_edit_post_preserves_gear_type_jrs(self):
        self.client.post(
            reverse('memorabilia:edit_collectible',
                    args=[self.collection.id, 'hockeyjersey', self.hockey_jersey.id]),
            self._hockey_jersey_post_data(title='Still JRS'),
        )
        self.hockey_jersey.refresh_from_db()
        self.assertEqual(self.hockey_jersey.gear_type_id, 'JRS')

    def test_edit_post_with_season_set(self):
        response = self.client.post(
            reverse('memorabilia:edit_collectible',
                    args=[self.collection.id, 'hockeyjersey', self.hockey_jersey.id]),
            self._hockey_jersey_post_data(title='Jersey With Season Set', season_set=self.season_set.key),
        )
        self.assertEqual(response.status_code, 302)
        self.hockey_jersey.refresh_from_db()
        self.assertEqual(self.hockey_jersey.season_set_id, self.season_set.key)

    def test_delete_post(self):
        temp = HockeyJersey.objects.create(
            title='Temp Hockey Jersey', description='temp', collection=self.collection,
            league='NHL', player='P', brand='CCM', size='54',
            season='2024', game_type=self.game_type, usage_type=self.usage_type,
        )
        response = self.client.post(reverse(
            'memorabilia:delete_collectible',
            args=[self.collection.id, 'hockeyjersey', temp.id],
        ))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(HockeyJersey.objects.filter(pk=temp.id).exists())

    def test_detail_get(self):
        response = self.client.get(reverse(
            'memorabilia:collectible',
            kwargs={
                'collection_id': self.collection.id,
                'collectible_type': 'hockeyjersey',
                'pk': self.hockey_jersey.id,
            },
        ))
        self.assertEqual(response.status_code, 200)

class BulkCollectibleFormTests(BaseTestCase):
    """Tests that BulkCollectibleForm instantiates correctly after duplicate __init__ removal."""

    def test_bulk_collectible_form_instantiates_without_error(self):
        from memorabilia.forms import BulkCollectibleForm
        form = BulkCollectibleForm()
        self.assertIsNotNone(form)

    def test_bulk_collectible_form_has_allow_featured_field(self):
        from memorabilia.forms import BulkCollectibleForm
        form = BulkCollectibleForm()
        self.assertIn('allow_featured', form.fields)

    def test_bulk_collectible_form_allow_featured_initial_true_for_featured_instance(self):
        from memorabilia.forms import BulkCollectibleForm
        self.player_item.allow_featured = True
        self.player_item.save(update_fields=['allow_featured'])
        form = BulkCollectibleForm(instance=self.player_item)
        self.assertEqual(form.initial['allow_featured'], 'true')

    def test_bulk_collectible_form_allow_featured_initial_false_for_non_featured_instance(self):
        from memorabilia.forms import BulkCollectibleForm
        self.player_item.allow_featured = False
        self.player_item.save(update_fields=['allow_featured'])
        form = BulkCollectibleForm(instance=self.player_item)
        self.assertEqual(form.initial['allow_featured'], 'false')

    def test_bulk_collectible_form_allow_featured_initial_empty_for_new_instance(self):
        from memorabilia.forms import BulkCollectibleForm
        form = BulkCollectibleForm()
        self.assertEqual(form.initial.get('allow_featured', ''), '')

    def test_bulk_collectible_form_league_widget_has_placeholder(self):
        from memorabilia.forms import BulkCollectibleForm
        form = BulkCollectibleForm()
        placeholder = form.fields['league'].widget.attrs.get('placeholder', '')
        self.assertIn('NHL', placeholder)

    def test_bulk_collectible_form_team_widget_has_placeholder(self):
        from memorabilia.forms import BulkCollectibleForm
        form = BulkCollectibleForm()
        placeholder = form.fields['team'].widget.attrs.get('placeholder', '')
        self.assertIn('team', placeholder.lower())


# ── Want List Tests ────────────────────────────────────────────────────────────

class ImageSizeValidationTests(TestCase):
    """Unit tests for ImageSizeValidationMixin.

    The mixin's clean_image() runs after ImageField's own Pillow validation.
    We test it by calling clean_image() directly on a form instance with
    pre-populated cleaned_data, which isolates our size-check logic from
    the Pillow image-content check.
    """

    MAX_BYTES = 10 * 1024 * 1024  # 10 MB

    def _make_fake_upload(self, size_bytes, name='test.jpg'):
        """Return a SimpleUploadedFile whose .size attribute equals size_bytes."""
        upload = SimpleUploadedFile(name, b'', content_type='image/jpeg')
        upload.size = size_bytes
        return upload

    def _apply_mixin_directly(self, form_class, upload):
        """
        Instantiate form_class, set cleaned_data['image'] to upload, and
        call clean_image(). Returns (result, raised_exception).
        """
        from django.core.exceptions import ValidationError
        form = form_class.__new__(form_class)
        form.cleaned_data = {'image': upload}
        try:
            result = form.clean_image()
            return result, None
        except ValidationError as exc:
            return None, exc

    # ── CollectibleImageForm (PlayerItemImage) ────────────────────────────────

    def test_collectible_image_form_rejects_oversized_file(self):
        from ..forms import CollectibleImageForm
        upload = self._make_fake_upload(self.MAX_BYTES + 1)
        _, exc = self._apply_mixin_directly(CollectibleImageForm, upload)
        self.assertIsNotNone(exc, "Expected ValidationError for oversized image")
        self.assertIn('too large', exc.message)

    def test_collectible_image_form_accepts_small_file(self):
        from ..forms import CollectibleImageForm
        upload = self._make_fake_upload(1 * 1024 * 1024)
        result, exc = self._apply_mixin_directly(CollectibleImageForm, upload)
        self.assertIsNone(exc, f"Unexpected ValidationError for small image: {exc}")
        self.assertEqual(result, upload)

    def test_collectible_image_form_accepts_exactly_10mb(self):
        from ..forms import CollectibleImageForm
        upload = self._make_fake_upload(self.MAX_BYTES)
        result, exc = self._apply_mixin_directly(CollectibleImageForm, upload)
        self.assertIsNone(exc, "Exactly 10 MB should be accepted")

    def test_collectible_image_form_no_image_passes(self):
        from ..forms import CollectibleImageForm
        form = CollectibleImageForm.__new__(CollectibleImageForm)
        form.cleaned_data = {'image': None}
        result = form.clean_image()
        self.assertIsNone(result)

    # ── GeneralItemImageForm ──────────────────────────────────────────────────

    def test_general_item_image_form_rejects_oversized_file(self):
        from ..forms import GeneralItemImageForm
        upload = self._make_fake_upload(self.MAX_BYTES + 1)
        _, exc = self._apply_mixin_directly(GeneralItemImageForm, upload)
        self.assertIsNotNone(exc)
        self.assertIn('too large', exc.message)

    def test_general_item_image_form_accepts_small_file(self):
        from ..forms import GeneralItemImageForm
        upload = self._make_fake_upload(1 * 1024 * 1024)
        result, exc = self._apply_mixin_directly(GeneralItemImageForm, upload)
        self.assertIsNone(exc)
        self.assertEqual(result, upload)

    # ── PlayerGearImageForm ───────────────────────────────────────────────────

    def test_player_gear_image_form_rejects_oversized_file(self):
        from ..forms import PlayerGearImageForm
        upload = self._make_fake_upload(self.MAX_BYTES + 1)
        _, exc = self._apply_mixin_directly(PlayerGearImageForm, upload)
        self.assertIsNotNone(exc)
        self.assertIn('too large', exc.message)

    def test_player_gear_image_form_accepts_small_file(self):
        from ..forms import PlayerGearImageForm
        upload = self._make_fake_upload(1 * 1024 * 1024)
        result, exc = self._apply_mixin_directly(PlayerGearImageForm, upload)
        self.assertIsNone(exc)
        self.assertEqual(result, upload)

    # ── WantListItemImageForm ─────────────────────────────────────────────────

    def test_want_list_item_image_form_rejects_oversized_file(self):
        from ..forms import WantListItemImageForm
        upload = self._make_fake_upload(self.MAX_BYTES + 1)
        _, exc = self._apply_mixin_directly(WantListItemImageForm, upload)
        self.assertIsNotNone(exc)
        self.assertIn('too large', exc.message)

    def test_want_list_item_image_form_accepts_small_file(self):
        from ..forms import WantListItemImageForm
        upload = self._make_fake_upload(1 * 1024 * 1024)
        result, exc = self._apply_mixin_directly(WantListItemImageForm, upload)
        self.assertIsNone(exc)
        self.assertEqual(result, upload)

    # ── Object without .size attribute should be returned as-is ──────────────

    def test_object_without_size_attribute_passes(self):
        """clean_image should not crash on an object that lacks .size (e.g. a URL string)."""
        from ..forms import CollectibleImageForm
        form = CollectibleImageForm.__new__(CollectibleImageForm)
        form.cleaned_data = {'image': 'https://example.com/photo.jpg'}
        result = form.clean_image()
        self.assertEqual(result, 'https://example.com/photo.jpg')

class ForSaleTradeFormTests(BaseTestCase):
    """The for_sale / for_trade / asking_price fields are now editable via the create/edit forms."""

    def setUp(self):
        self.client.force_login(self.owner)

    def test_create_player_item_for_sale_with_price(self):
        response = self.client.post(
            reverse('memorabilia:create_collectible', args=[self.collection.id]),
            self._player_item_post_data(title='Sale Item', for_sale='on', asking_price='150'),
        )
        self.assertEqual(response.status_code, 302)
        item = PlayerItem.objects.get(title='Sale Item')
        self.assertTrue(item.for_sale)
        self.assertEqual(item.asking_price, 150)

    def test_create_general_item_for_trade(self):
        response = self.client.post(
            reverse('memorabilia:create_collectible', args=[self.collection.id]),
            self._general_item_post_data(title='Trade Puck', for_trade='on'),
        )
        self.assertEqual(response.status_code, 302)
        item = GeneralItem.objects.get(title='Trade Puck')
        self.assertTrue(item.for_trade)

    def test_create_hockey_jersey_for_sale(self):
        response = self.client.post(
            reverse('memorabilia:create_collectible', args=[self.collection.id]),
            self._hockey_jersey_post_data(title='Sale Jersey', for_sale='on', asking_price='999.5'),
        )
        self.assertEqual(response.status_code, 302)
        item = HockeyJersey.objects.get(title='Sale Jersey')
        self.assertTrue(item.for_sale)
        self.assertEqual(item.asking_price, 999.5)

    def test_edit_form_shows_price_two_decimals_and_currency(self):
        self.player_item.for_sale = True
        self.player_item.asking_price = 50
        self.player_item.currency = 'CAD'
        self.player_item.save()
        response = self.client.get(reverse(
            'memorabilia:edit_collectible',
            args=[self.collection.id, 'playeritem', self.player_item.id],
        ))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['form'].initial['asking_price'], '50.00')
        self.assertEqual(response.context['form'].initial['currency'], 'CAD')

    def test_edit_clears_for_sale_when_unchecked(self):
        self.player_item.for_sale = True
        self.player_item.asking_price = 50
        self.player_item.save()
        # Unchecked checkbox is simply absent from the POST.
        response = self.client.post(
            reverse('memorabilia:edit_collectible',
                    args=[self.collection.id, 'playeritem', self.player_item.id]),
            self._player_item_post_data(title=self.player_item.title),
        )
        self.assertEqual(response.status_code, 302)
        self.player_item.refresh_from_db()
        self.assertFalse(self.player_item.for_sale)

class CollectibleDetailSaleTradeTests(BaseTestCase):
    """The detail page shows For Sale / For Trade indicators, and the For Trade
    row links to the collection owner's want list when one exists."""

    def _detail_url(self, obj):
        return reverse('memorabilia:collectible', kwargs={
            'collection_id': self.collection.id,
            'collectible_type': obj.collectible_type,
            'pk': obj.id,
        })

    def test_for_trade_indicator_shown(self):
        self.player_item.for_trade = True
        self.player_item.save()
        response = self.client.get(self._detail_url(self.player_item))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'For Trade')

    def test_for_sale_indicator_with_price(self):
        self.general_item.for_sale = True
        self.general_item.asking_price = 75
        self.general_item.save()
        response = self.client.get(self._detail_url(self.general_item))
        self.assertContains(response, 'For Sale')
        self.assertContains(response, '$75.00 USD')

    def test_for_trade_links_to_owner_want_list(self):
        profile = WantListProfile.objects.create(user=self.owner, slug='owner-wants', visibility='public')
        WantList.objects.create(profile=profile, title='My Wants')
        self.player_item.for_trade = True
        self.player_item.save()
        response = self.client.get(self._detail_url(self.player_item))
        self.assertEqual(
            response.context['owner_want_list_url'],
            reverse('memorabilia:want_list_public', kwargs={'slug': 'owner-wants'}),
        )
        self.assertContains(response, 'View want list')

    def test_no_want_list_link_when_owner_has_none(self):
        self.player_item.for_trade = True
        self.player_item.save()
        response = self.client.get(self._detail_url(self.player_item))
        self.assertIsNone(response.context['owner_want_list_url'])
        self.assertNotContains(response, 'View want list')

    def test_for_trade_links_to_specific_want_list(self):
        profile = WantListProfile.objects.create(user=self.owner, slug='owner-wants', visibility='public')
        WantList.objects.create(profile=profile, title='My Wants')
        favorites = WantList.objects.create(profile=profile, title='Favorite Players')
        self.player_item.for_trade = True
        self.player_item.trade_want_list = favorites
        self.player_item.save()
        response = self.client.get(self._detail_url(self.player_item))
        specific_url = reverse('memorabilia:want_list_public_single',
                               kwargs={'slug': 'owner-wants', 'list_slug': 'favorite-players'})
        self.assertEqual(response.context['owner_want_list_url'], specific_url)
        self.assertContains(response, specific_url)
