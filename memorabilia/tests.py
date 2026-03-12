from django.test import TestCase
from django.contrib.auth.models import User
from django.urls import reverse

from .models import Collection, PlayerItem, PlayerGearItem, OtherItem, League, GameType, UsageType


class BaseTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user(username='owner', password='testpass')
        cls.other_user = User.objects.create_user(username='other', password='testpass')

        cls.league = League.objects.create(key='NHL', name='National Hockey League')
        cls.game_type = GameType.objects.create(key='REG', name='Regular Season')
        cls.usage_type = UsageType.objects.create(key='GU', name='Game Used')

        cls.collection = Collection.objects.create(
            owner_uid=cls.owner.id,
            title='Test Collection',
        )

        cls.player_item = PlayerItem.objects.create(
            title='Test Jersey',
            description='A test jersey',
            collection=cls.collection,
            league='NHL',
            player='Wayne Gretzky',
        )

        cls.player_gear_item = PlayerGearItem.objects.create(
            title='Test Gear Jersey',
            description='A test gear jersey',
            collection=cls.collection,
            league='NHL',
            player='Wayne Gretzky',
            brand='Adidas',
            size='L',
            season='1985',
            game_type=cls.game_type,
            usage_type=cls.usage_type,
        )

        cls.other_item = OtherItem.objects.create(
            title='Test Puck',
            description='A test puck',
            collection=cls.collection,
        )

    def _player_item_post_data(self, **overrides):
        """Return valid POST data for creating/editing a PlayerItem."""
        data = {
            'collectible_type': 'PlayerItem',
            'title': 'New Jersey',
            'description': 'A new test jersey',
            'collection': self.collection.id,
            'league': 'NHL',
            'player': 'Test Player',
            'images-TOTAL_FORMS': '0',
            'images-INITIAL_FORMS': '0',
            'images-MIN_NUM_FORMS': '0',
            'images-MAX_NUM_FORMS': '1000',
        }
        data.update(overrides)
        return data

    def _player_gear_item_post_data(self, **overrides):
        """Return valid POST data for creating/editing a PlayerGearItem."""
        data = {
            'collectible_type': 'PlayerGearItem',
            'title': 'New Gear Jersey',
            'description': 'A new test gear jersey',
            'collection': self.collection.id,
            'league': 'NHL',
            'player': 'Test Player',
            'brand': 'Adidas',
            'size': 'L',
            'season': '2024',
            'game_type': 'REG',
            'usage_type': 'GU',
            'images-TOTAL_FORMS': '0',
            'images-INITIAL_FORMS': '0',
            'images-MIN_NUM_FORMS': '0',
            'images-MAX_NUM_FORMS': '1000',
        }
        data.update(overrides)
        return data

    def _other_item_post_data(self, **overrides):
        """Return valid POST data for creating/editing an OtherItem."""
        data = {
            'collectible_type': 'OtherItem',
            'title': 'New Puck',
            'description': 'A new test puck',
            'collection': self.collection.id,
            'images-TOTAL_FORMS': '0',
            'images-INITIAL_FORMS': '0',
            'images-MIN_NUM_FORMS': '0',
            'images-MAX_NUM_FORMS': '1000',
        }
        data.update(overrides)
        return data


class PublicViewTests(BaseTestCase):
    def test_home_page(self):
        response = self.client.get(reverse('memorabilia:home'))
        self.assertEqual(response.status_code, 200)

    def test_list_collections(self):
        response = self.client.get(reverse('memorabilia:list_collections'))
        self.assertEqual(response.status_code, 200)

    def test_collection_detail(self):
        response = self.client.get(
            reverse('memorabilia:collection', kwargs={'pk': self.collection.id})
        )
        self.assertEqual(response.status_code, 200)

    def test_playeritem_detail(self):
        response = self.client.get(reverse(
            'memorabilia:collectible',
            kwargs={
                'collection_id': self.collection.id,
                'collectible_type': 'playeritem',
                'pk': self.player_item.id,
            },
        ))
        self.assertEqual(response.status_code, 200)

    def test_playergearitem_detail(self):
        response = self.client.get(reverse(
            'memorabilia:collectible',
            kwargs={
                'collection_id': self.collection.id,
                'collectible_type': 'playergearitem',
                'pk': self.player_gear_item.id,
            },
        ))
        self.assertEqual(response.status_code, 200)

    def test_otheritem_detail(self):
        response = self.client.get(reverse(
            'memorabilia:collectible',
            kwargs={
                'collection_id': self.collection.id,
                'collectible_type': 'otheritem',
                'pk': self.other_item.id,
            },
        ))
        self.assertEqual(response.status_code, 200)

    def test_get_teams_api(self):
        url = reverse('memorabilia:get_teams') + '?league=NHL'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('teams', data)
        self.assertIsInstance(data['teams'], list)


class CollectionCRUDTests(BaseTestCase):
    def setUp(self):
        self.client.force_login(self.owner)

    def test_create_get(self):
        response = self.client.get(reverse('memorabilia:create_collection'))
        self.assertEqual(response.status_code, 200)

    def test_create_post(self):
        response = self.client.post(
            reverse('memorabilia:create_collection'),
            {'title': 'Brand New Collection', 'header_image_1': 'https://example.com/image.jpg'},
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Collection.objects.filter(title='Brand New Collection').exists())

    def test_edit_get(self):
        response = self.client.get(
            reverse('memorabilia:edit_collection', args=[self.collection.id])
        )
        self.assertEqual(response.status_code, 200)

    def test_edit_post(self):
        response = self.client.post(
            reverse('memorabilia:edit_collection', args=[self.collection.id]),
            {'title': 'Updated Title', 'header_image_1': 'https://example.com/image.jpg'},
        )
        self.assertEqual(response.status_code, 302)
        self.collection.refresh_from_db()
        self.assertEqual(self.collection.title, 'Updated Title')

    def test_delete_post(self):
        temp = Collection.objects.create(owner_uid=self.owner.id, title='To Delete')
        response = self.client.post(
            reverse('memorabilia:delete_collection', args=[temp.id])
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Collection.objects.filter(pk=temp.id).exists())


class CollectionPermissionTests(BaseTestCase):
    def test_edit_requires_login(self):
        response = self.client.get(
            reverse('memorabilia:edit_collection', args=[self.collection.id])
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn('login', response['Location'])

    def test_edit_other_user_forbidden(self):
        self.client.force_login(self.other_user)
        response = self.client.post(
            reverse('memorabilia:edit_collection', args=[self.collection.id]),
            {'title': 'Hacked', 'header_image_1': 'https://example.com/img.jpg'},
        )
        self.assertEqual(response.status_code, 403)

    def test_delete_other_user_forbidden(self):
        self.client.force_login(self.other_user)
        response = self.client.post(
            reverse('memorabilia:delete_collection', args=[self.collection.id])
        )
        self.assertEqual(response.status_code, 403)


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


class PlayerGearItemCRUDTests(BaseTestCase):
    def setUp(self):
        self.client.force_login(self.owner)

    def test_create_post(self):
        response = self.client.post(
            reverse('memorabilia:create_collectible', args=[self.collection.id]),
            self._player_gear_item_post_data(title='Created Gear Jersey'),
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(PlayerGearItem.objects.filter(title='Created Gear Jersey').exists())

    def test_edit_get(self):
        response = self.client.get(reverse(
            'memorabilia:edit_collectible',
            args=[self.collection.id, 'playergearitem', self.player_gear_item.id],
        ))
        self.assertEqual(response.status_code, 200)

    def test_edit_post(self):
        response = self.client.post(
            reverse('memorabilia:edit_collectible',
                    args=[self.collection.id, 'playergearitem', self.player_gear_item.id]),
            self._player_gear_item_post_data(title='Edited Gear Jersey'),
        )
        self.assertEqual(response.status_code, 302)
        self.player_gear_item.refresh_from_db()
        self.assertEqual(self.player_gear_item.title, 'Edited Gear Jersey')

    def test_delete_post(self):
        temp = PlayerGearItem.objects.create(
            title='Temp Gear Jersey', description='temp', collection=self.collection,
            league='NHL', player='P', brand='Adidas', size='L',
            season='2024', game_type=self.game_type, usage_type=self.usage_type,
        )
        response = self.client.post(reverse(
            'memorabilia:delete_collectible',
            args=[self.collection.id, 'playergearitem', temp.id],
        ))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(PlayerGearItem.objects.filter(pk=temp.id).exists())


class OtherItemCRUDTests(BaseTestCase):
    def setUp(self):
        self.client.force_login(self.owner)

    def test_create_post(self):
        response = self.client.post(
            reverse('memorabilia:create_collectible', args=[self.collection.id]),
            self._other_item_post_data(title='Created Puck'),
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(OtherItem.objects.filter(title='Created Puck').exists())

    def test_edit_get(self):
        response = self.client.get(reverse(
            'memorabilia:edit_collectible',
            args=[self.collection.id, 'otheritem', self.other_item.id],
        ))
        self.assertEqual(response.status_code, 200)

    def test_edit_post(self):
        response = self.client.post(
            reverse('memorabilia:edit_collectible',
                    args=[self.collection.id, 'otheritem', self.other_item.id]),
            self._other_item_post_data(title='Edited Puck'),
        )
        self.assertEqual(response.status_code, 302)
        self.other_item.refresh_from_db()
        self.assertEqual(self.other_item.title, 'Edited Puck')

    def test_delete_post(self):
        temp = OtherItem.objects.create(
            title='Temp Puck', description='temp', collection=self.collection,
        )
        response = self.client.post(reverse(
            'memorabilia:delete_collectible',
            args=[self.collection.id, 'otheritem', temp.id],
        ))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(OtherItem.objects.filter(pk=temp.id).exists())


class CollectiblePermissionTests(BaseTestCase):
    def test_edit_playeritem_requires_login(self):
        response = self.client.get(reverse(
            'memorabilia:edit_collectible',
            args=[self.collection.id, 'playeritem', self.player_item.id],
        ))
        self.assertEqual(response.status_code, 302)
        self.assertIn('login', response['Location'])

    def test_edit_playergearitem_requires_login(self):
        response = self.client.get(reverse(
            'memorabilia:edit_collectible',
            args=[self.collection.id, 'playergearitem', self.player_gear_item.id],
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

    def test_edit_playergearitem_other_user_forbidden(self):
        self.client.force_login(self.other_user)
        response = self.client.get(reverse(
            'memorabilia:edit_collectible',
            args=[self.collection.id, 'playergearitem', self.player_gear_item.id],
        ))
        self.assertEqual(response.status_code, 403)

    def test_delete_playergearitem_other_user_forbidden(self):
        self.client.force_login(self.other_user)
        response = self.client.post(reverse(
            'memorabilia:delete_collectible',
            args=[self.collection.id, 'playergearitem', self.player_gear_item.id],
        ))
        self.assertEqual(response.status_code, 403)

    def test_delete_otheritem_other_user_forbidden(self):
        self.client.force_login(self.other_user)
        response = self.client.post(reverse(
            'memorabilia:delete_collectible',
            args=[self.collection.id, 'otheritem', self.other_item.id],
        ))
        self.assertEqual(response.status_code, 403)

    def test_edit_otheritem_other_user_forbidden(self):
        self.client.force_login(self.other_user)
        response = self.client.get(reverse(
            'memorabilia:edit_collectible',
            args=[self.collection.id, 'otheritem', self.other_item.id],
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

    def test_playeritem_to_playergearitem(self):
        item = PlayerItem.objects.create(
            title='Convert Me', description='desc', collection=self.collection,
            league='NHL', player='P',
        )
        old_pk = item.pk
        response = self.client.post(
            reverse('memorabilia:edit_collectible', args=[self.collection.id, 'playeritem', item.id]),
            self._player_gear_item_post_data(title='Convert Me'),
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(PlayerItem.objects.filter(pk=old_pk).exists())
        self.assertTrue(PlayerGearItem.objects.filter(title='Convert Me', collection=self.collection).exists())

    def test_playeritem_to_otheritem(self):
        item = PlayerItem.objects.create(
            title='Convert To Other', description='desc', collection=self.collection,
            league='NHL', player='P',
        )
        old_pk = item.pk
        response = self.client.post(
            reverse('memorabilia:edit_collectible', args=[self.collection.id, 'playeritem', item.id]),
            self._other_item_post_data(title='Convert To Other'),
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(PlayerItem.objects.filter(pk=old_pk).exists())
        self.assertTrue(OtherItem.objects.filter(title='Convert To Other', collection=self.collection).exists())

    def test_playergearitem_to_playeritem(self):
        item = PlayerGearItem.objects.create(
            title='Gear To Player', description='desc', collection=self.collection,
            league='NHL', player='P', brand='Nike', size='M', season='2020',
            game_type=self.game_type, usage_type=self.usage_type,
        )
        old_pk = item.pk
        response = self.client.post(
            reverse('memorabilia:edit_collectible', args=[self.collection.id, 'playergearitem', item.id]),
            self._player_item_post_data(title='Gear To Player'),
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(PlayerGearItem.objects.filter(pk=old_pk).exists())
        self.assertTrue(PlayerItem.objects.filter(title='Gear To Player', collection=self.collection).exists())

    def test_playergearitem_to_otheritem(self):
        item = PlayerGearItem.objects.create(
            title='Gear To Other', description='desc', collection=self.collection,
            league='NHL', player='P', brand='Nike', size='M', season='2020',
            game_type=self.game_type, usage_type=self.usage_type,
        )
        old_pk = item.pk
        response = self.client.post(
            reverse('memorabilia:edit_collectible', args=[self.collection.id, 'playergearitem', item.id]),
            self._other_item_post_data(title='Gear To Other'),
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(PlayerGearItem.objects.filter(pk=old_pk).exists())
        self.assertTrue(OtherItem.objects.filter(title='Gear To Other', collection=self.collection).exists())

    def test_otheritem_to_playeritem(self):
        item = OtherItem.objects.create(
            title='Other To Player', description='desc', collection=self.collection,
        )
        old_pk = item.pk
        response = self.client.post(
            reverse('memorabilia:edit_collectible', args=[self.collection.id, 'otheritem', item.id]),
            self._player_item_post_data(title='Other To Player'),
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(OtherItem.objects.filter(pk=old_pk).exists())
        self.assertTrue(PlayerItem.objects.filter(title='Other To Player', collection=self.collection).exists())

    def test_otheritem_to_playergearitem(self):
        item = OtherItem.objects.create(
            title='Other To Gear', description='desc', collection=self.collection,
        )
        old_pk = item.pk
        response = self.client.post(
            reverse('memorabilia:edit_collectible', args=[self.collection.id, 'otheritem', item.id]),
            self._player_gear_item_post_data(title='Other To Gear'),
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(OtherItem.objects.filter(pk=old_pk).exists())
        self.assertTrue(PlayerGearItem.objects.filter(title='Other To Gear', collection=self.collection).exists())

    def test_type_conversion_invalid_data_returns_form(self):
        """Invalid data during type conversion should not delete the original and should return 200."""
        item = PlayerItem.objects.create(
            title='Stay Safe', description='desc', collection=self.collection,
            league='NHL', player='P',
        )
        old_pk = item.pk
        # Post PlayerGearItem type but omit required gear fields
        response = self.client.post(
            reverse('memorabilia:edit_collectible', args=[self.collection.id, 'playeritem', item.id]),
            {'collectible_type': 'PlayerGearItem', 'title': '', 'collection': self.collection.id,
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
        cls.bulk_gear = PlayerGearItem.objects.create(
            title='Bulk Gear', description='desc', collection=cls.bulk_collection,
            league='NHL', player='P', brand='Nike', size='M', season='2020',
            game_type=cls.game_type, usage_type=cls.usage_type,
        )
        cls.bulk_player = PlayerItem.objects.create(
            title='Bulk Player', description='desc', collection=cls.bulk_collection,
            league='NHL', player='Q',
        )
        cls.bulk_other = OtherItem.objects.create(
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
        item = PlayerGearItem.objects.create(
            title='Gear2Player', description='desc', collection=self.bulk_collection,
            league='NHL', player='R', brand='Nike', size='M', season='2020',
            game_type=self.game_type, usage_type=self.usage_type,
        )
        old_pk = item.pk
        post = (
            self._gear_formset(item, **{'item_type_gear-0': 'playeritem'})
            | self._empty_formset('player')
            | self._empty_formset('other')
        )
        response = self.client.post(self._bulk_url(), post)
        self.assertEqual(response.status_code, 302)
        self.assertFalse(PlayerGearItem.objects.filter(pk=old_pk).exists())
        self.assertTrue(PlayerItem.objects.filter(title='Gear2Player', collection=self.bulk_collection).exists())

    def test_post_type_conversion_gear_to_other(self):
        self.client.force_login(self.owner)
        item = PlayerGearItem.objects.create(
            title='Gear2Other', description='desc', collection=self.bulk_collection,
            league='NHL', player='S', brand='Nike', size='M', season='2020',
            game_type=self.game_type, usage_type=self.usage_type,
        )
        old_pk = item.pk
        post = (
            self._gear_formset(item, **{'item_type_gear-0': 'otheritem'})
            | self._empty_formset('player')
            | self._empty_formset('other')
        )
        response = self.client.post(self._bulk_url(), post)
        self.assertEqual(response.status_code, 302)
        self.assertFalse(PlayerGearItem.objects.filter(pk=old_pk).exists())
        self.assertTrue(OtherItem.objects.filter(title='Gear2Other', collection=self.bulk_collection).exists())

    def test_post_type_conversion_player_to_other(self):
        self.client.force_login(self.owner)
        item = PlayerItem.objects.create(
            title='Player2Other', description='desc', collection=self.bulk_collection,
            league='NHL', player='T',
        )
        old_pk = item.pk
        post = (
            self._empty_formset('gear')
            | self._player_formset(item, **{'item_type_player-0': 'otheritem'})
            | self._empty_formset('other')
        )
        response = self.client.post(self._bulk_url(), post)
        self.assertEqual(response.status_code, 302)
        self.assertFalse(PlayerItem.objects.filter(pk=old_pk).exists())
        self.assertTrue(OtherItem.objects.filter(title='Player2Other', collection=self.bulk_collection).exists())

    def test_post_type_conversion_other_to_player(self):
        self.client.force_login(self.owner)
        item = OtherItem.objects.create(
            title='Other2Player', description='desc', collection=self.bulk_collection,
        )
        old_pk = item.pk
        post = (
            self._empty_formset('gear')
            | self._empty_formset('player')
            | self._other_formset(item, **{
                'item_type_other-0': 'playeritem',
                'other-0-league': 'NHL',
                'other-0-player': 'U',
            })
        )
        response = self.client.post(self._bulk_url(), post)
        self.assertEqual(response.status_code, 302)
        self.assertFalse(OtherItem.objects.filter(pk=old_pk).exists())
        self.assertTrue(PlayerItem.objects.filter(title='Other2Player', collection=self.bulk_collection).exists())


class CollectibleDetailContextTests(BaseTestCase):
    def test_playeritem_detail_context_has_league(self):
        response = self.client.get(reverse(
            'memorabilia:collectible',
            kwargs={'collection_id': self.collection.id, 'collectible_type': 'playeritem', 'pk': self.player_item.id},
        ))
        self.assertIn('league', response.context)

    def test_playergearitem_detail_context_has_league_and_image(self):
        response = self.client.get(reverse(
            'memorabilia:collectible',
            kwargs={'collection_id': self.collection.id, 'collectible_type': 'playergearitem', 'pk': self.player_gear_item.id},
        ))
        self.assertIn('league', response.context)
        self.assertIn('primary_image', response.context)

    def test_otheritem_detail_no_league_in_context(self):
        response = self.client.get(reverse(
            'memorabilia:collectible',
            kwargs={'collection_id': self.collection.id, 'collectible_type': 'otheritem', 'pk': self.other_item.id},
        ))
        self.assertNotIn('league', response.context)

    def test_playeritem_uses_correct_template(self):
        response = self.client.get(reverse(
            'memorabilia:collectible',
            kwargs={'collection_id': self.collection.id, 'collectible_type': 'playeritem', 'pk': self.player_item.id},
        ))
        self.assertTemplateUsed(response, 'memorabilia/playeritem_detail.html')

    def test_playergearitem_uses_correct_template(self):
        response = self.client.get(reverse(
            'memorabilia:collectible',
            kwargs={'collection_id': self.collection.id, 'collectible_type': 'playergearitem', 'pk': self.player_gear_item.id},
        ))
        self.assertTemplateUsed(response, 'memorabilia/playergearitem_detail.html')

    def test_otheritem_uses_correct_template(self):
        response = self.client.get(reverse(
            'memorabilia:collectible',
            kwargs={'collection_id': self.collection.id, 'collectible_type': 'otheritem', 'pk': self.other_item.id},
        ))
        self.assertTemplateUsed(response, 'memorabilia/otheritem_detail.html')


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

    def test_playergearitem_wrong_pk(self):
        response = self.client.get(reverse(
            'memorabilia:collectible',
            kwargs={'collection_id': self.collection.id, 'collectible_type': 'playergearitem', 'pk': 999999},
        ))
        self.assertEqual(response.status_code, 404)

    def test_otheritem_wrong_pk(self):
        response = self.client.get(reverse(
            'memorabilia:collectible',
            kwargs={'collection_id': self.collection.id, 'collectible_type': 'otheritem', 'pk': 999999},
        ))
        self.assertEqual(response.status_code, 404)

    def test_playergearitem_wrong_collection(self):
        other_collection = Collection.objects.create(owner_uid=self.owner.id, title='Other')
        response = self.client.get(reverse(
            'memorabilia:collectible',
            kwargs={'collection_id': other_collection.id, 'collectible_type': 'playergearitem', 'pk': self.player_gear_item.id},
        ))
        self.assertEqual(response.status_code, 404)

    def test_otheritem_wrong_collection(self):
        other_collection = Collection.objects.create(owner_uid=self.owner.id, title='Other')
        response = self.client.get(reverse(
            'memorabilia:collectible',
            kwargs={'collection_id': other_collection.id, 'collectible_type': 'otheritem', 'pk': self.other_item.id},
        ))
        self.assertEqual(response.status_code, 404)


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

    def test_create_playergearitem_missing_title_returns_200(self):
        response = self.client.post(
            reverse('memorabilia:create_collectible', args=[self.collection.id]),
            self._player_gear_item_post_data(title=''),
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

    def test_edit_playergearitem_missing_title_returns_200(self):
        response = self.client.post(
            reverse('memorabilia:edit_collectible', args=[self.collection.id, 'playergearitem', self.player_gear_item.id]),
            self._player_gear_item_post_data(title=''),
        )
        self.assertEqual(response.status_code, 200)
        self.player_gear_item.refresh_from_db()
        self.assertNotEqual(self.player_gear_item.title, '')

    def test_create_otheritem_missing_title_returns_200(self):
        response = self.client.post(
            reverse('memorabilia:create_collectible', args=[self.collection.id]),
            self._other_item_post_data(title=''),
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(OtherItem.objects.filter(title='').exists())

    def test_edit_otheritem_missing_title_returns_200(self):
        response = self.client.post(
            reverse('memorabilia:edit_collectible', args=[self.collection.id, 'otheritem', self.other_item.id]),
            self._other_item_post_data(title=''),
        )
        self.assertEqual(response.status_code, 200)
        self.other_item.refresh_from_db()
        self.assertNotEqual(self.other_item.title, '')
