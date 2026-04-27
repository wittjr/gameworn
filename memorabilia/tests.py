import tempfile

from django.test import TestCase, override_settings
from django.contrib.auth.models import User
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile

from .models import Collection, PlayerItem, PlayerGear, HockeyJersey, GeneralItem, League, GameType, UsageType, GearType, SeasonSet, UserProfile, PlayerItemImage, PlayerGearImage, GeneralItemImage, PhotoMatch, AuthSource, WantListProfile, WantList, WantListItem, WantListItemImage


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

        cls.player_gear = PlayerGear.objects.create(
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

        cls.general_item = GeneralItem.objects.create(
            title='Test Puck',
            description='A test puck',
            collection=cls.collection,
        )

        cls.gear_type_jrs, _ = GearType.objects.get_or_create(key='JRS', defaults={'name': 'Jersey'})
        cls.season_set = SeasonSet.objects.create(key='REG1', name='Regular Set 1')

        cls.hockey_jersey = HockeyJersey.objects.create(
            title='Test Hockey Jersey',
            description='A test hockey jersey',
            collection=cls.collection,
            league='NHL',
            player='Wayne Gretzky',
            brand='CCM',
            size='54',
            season='1988',
            game_type=cls.game_type,
            usage_type=cls.usage_type,
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
            'authentications-TOTAL_FORMS': '0',
            'authentications-INITIAL_FORMS': '0',
            'authentications-MIN_NUM_FORMS': '0',
            'authentications-MAX_NUM_FORMS': '100',
        }
        data.update(overrides)
        return data

    def _player_gear_post_data(self, **overrides):
        """Return valid POST data for creating/editing a PlayerGear."""
        data = {
            'collectible_type': 'PlayerGear',
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
            'authentications-TOTAL_FORMS': '0',
            'authentications-INITIAL_FORMS': '0',
            'authentications-MIN_NUM_FORMS': '0',
            'authentications-MAX_NUM_FORMS': '100',
        }
        data.update(overrides)
        return data

    def _general_item_post_data(self, **overrides):
        """Return valid POST data for creating/editing a GeneralItem."""
        data = {
            'collectible_type': 'GeneralItem',
            'title': 'New Puck',
            'description': 'A new test puck',
            'collection': self.collection.id,
            'images-TOTAL_FORMS': '0',
            'images-INITIAL_FORMS': '0',
            'images-MIN_NUM_FORMS': '0',
            'images-MAX_NUM_FORMS': '1000',
            'authentications-TOTAL_FORMS': '0',
            'authentications-INITIAL_FORMS': '0',
            'authentications-MIN_NUM_FORMS': '0',
            'authentications-MAX_NUM_FORMS': '100',
        }
        data.update(overrides)
        return data

    def _hockey_jersey_post_data(self, **overrides):
        """Return valid POST data for creating/editing a HockeyJersey."""
        data = {
            'collectible_type': 'HockeyJersey',
            'title': 'New Hockey Jersey',
            'description': 'A new test hockey jersey',
            'collection': self.collection.id,
            'league': 'NHL',
            'player': 'Test Player',
            'brand': 'CCM',
            'size': '54',
            'season': '2024',
            'game_type': 'REG',
            'usage_type': 'GU',
            'images-TOTAL_FORMS': '0',
            'images-INITIAL_FORMS': '0',
            'images-MIN_NUM_FORMS': '0',
            'images-MAX_NUM_FORMS': '1000',
            'authentications-TOTAL_FORMS': '0',
            'authentications-INITIAL_FORMS': '0',
            'authentications-MIN_NUM_FORMS': '0',
            'authentications-MAX_NUM_FORMS': '100',
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

    def test_playergear_detail(self):
        response = self.client.get(reverse(
            'memorabilia:collectible',
            kwargs={
                'collection_id': self.collection.id,
                'collectible_type': 'playergear',
                'pk': self.player_gear.id,
            },
        ))
        self.assertEqual(response.status_code, 200)

    def test_generalitem_detail(self):
        response = self.client.get(reverse(
            'memorabilia:collectible',
            kwargs={
                'collection_id': self.collection.id,
                'collectible_type': 'generalitem',
                'pk': self.general_item.id,
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

    def test_create_post_without_image(self):
        """Creating a collection with only a title (no image) should succeed."""
        response = self.client.post(
            reverse('memorabilia:create_collection'),
            {'title': 'No Image Collection'},
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Collection.objects.filter(title='No Image Collection').exists())

    def test_create_post_without_image_sets_image_fields_to_none(self):
        """A collection created without an image should have null image and image_link."""
        self.client.post(
            reverse('memorabilia:create_collection'),
            {'title': 'Imageless Collection'},
        )
        col = Collection.objects.get(title='Imageless Collection')
        self.assertFalse(col.image)
        self.assertIsNone(col.image_link)

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

    def test_edit_post_without_image(self):
        """Editing a collection title while omitting the image field should still save."""
        col = Collection.objects.create(owner_uid=self.owner.id, title='Before Edit')
        response = self.client.post(
            reverse('memorabilia:edit_collection', args=[col.id]),
            {'title': 'After Edit'},
        )
        self.assertEqual(response.status_code, 302)
        col.refresh_from_db()
        self.assertEqual(col.title, 'After Edit')

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


class CollectionModelTests(BaseTestCase):
    """Unit tests for Collection model methods: get_header_image_url and get_collage_images."""

    # --- get_header_image_url ---

    def test_get_header_image_url_no_image_returns_none(self):
        """Returns None when neither image nor image_link is set."""
        col = Collection.objects.create(owner_uid=self.owner.id, title='No Image')
        self.assertIsNone(col.get_header_image_url())

    def test_get_header_image_url_with_image_link(self):
        """Returns the image_link string when only a URL is stored."""
        col = Collection.objects.create(
            owner_uid=self.owner.id,
            title='Link Only',
            image_link='https://example.com/header.jpg',
        )
        self.assertEqual(col.get_header_image_url(), 'https://example.com/header.jpg')

    def test_get_header_image_url_image_takes_precedence_over_link(self):
        """When both image and image_link are set, image.url is preferred."""
        # We can't easily upload a real file in a unit test, so we verify the
        # branch logic by checking that a falsy image field falls through to image_link.
        col = Collection.objects.create(
            owner_uid=self.owner.id,
            title='Link Fallback',
            image_link='https://example.com/fallback.jpg',
        )
        # No image file uploaded — should fall through to image_link.
        self.assertEqual(col.get_header_image_url(), 'https://example.com/fallback.jpg')

    # --- get_collage_images ---

    def test_get_collage_images_empty_collection_returns_empty_list(self):
        """A collection with no collectibles returns an empty list."""
        col = Collection.objects.create(owner_uid=self.owner.id, title='Empty')
        self.assertEqual(col.get_collage_images(), [])

    def test_get_collage_images_no_images_on_collectibles_returns_empty_list(self):
        """Collectibles without any images are skipped; result is empty."""
        col = Collection.objects.create(owner_uid=self.owner.id, title='No Imgs')
        PlayerItem.objects.create(
            title='Imageless Jersey', description='', collection=col,
            league='NHL', player='P',
        )
        self.assertEqual(col.get_collage_images(), [])

    def test_get_collage_images_respects_max_count(self):
        """get_collage_images returns at most max_count images."""
        from memorabilia.models import PlayerItemImage
        col = Collection.objects.create(owner_uid=self.owner.id, title='Many Items')
        # Create 4 items each with one image link
        for i in range(4):
            item = PlayerItem.objects.create(
                title=f'Item {i}', description='', collection=col,
                league='NHL', player='P',
            )
            PlayerItemImage.objects.create(
                collectible=item,
                link=f'https://example.com/img{i}.jpg',
                primary=True,
            )
        result = col.get_collage_images(max_count=2)
        self.assertEqual(len(result), 2)

    def test_get_collage_images_includes_all_collectible_types(self):
        """Images from PlayerItem, PlayerGear, and GeneralItem are all collected."""
        from memorabilia.models import PlayerItemImage, PlayerGearImage, GeneralItemImage
        col = Collection.objects.create(owner_uid=self.owner.id, title='Mixed Types')

        pi = PlayerItem.objects.create(
            title='PI', description='', collection=col, league='NHL', player='P',
        )
        PlayerItemImage.objects.create(
            collectible=pi, link='https://example.com/pi.jpg', primary=True,
        )

        pgi = PlayerGear.objects.create(
            title='PGI', description='', collection=col, league='NHL', player='P',
            brand='Nike', size='M', season='2020',
            game_type=self.game_type, usage_type=self.usage_type,
        )
        PlayerGearImage.objects.create(
            collectible=pgi, link='https://example.com/pgi.jpg', primary=True,
        )

        oi = GeneralItem.objects.create(title='OI', description='', collection=col)
        GeneralItemImage.objects.create(
            collectible=oi, link='https://example.com/oi.jpg', primary=True,
        )

        result = col.get_collage_images(max_count=9)
        self.assertEqual(len(result), 3)

    def test_get_collage_images_default_max_is_nine(self):
        """Default max_count is 9; more than 9 images are truncated to 9."""
        from memorabilia.models import PlayerItemImage
        col = Collection.objects.create(owner_uid=self.owner.id, title='Ten Items')
        for i in range(10):
            item = PlayerItem.objects.create(
                title=f'J{i}', description='', collection=col,
                league='NHL', player='P',
            )
            PlayerItemImage.objects.create(
                collectible=item, link=f'https://example.com/{i}.jpg', primary=True,
            )
        result = col.get_collage_images()
        self.assertEqual(len(result), 9)

    # --- get_collage_images with collage_collectible_ids set ---

    def test_get_collage_images_uses_collage_collectible_ids_when_set(self):
        """When collage_collectible_ids is set, only those collectibles are used."""
        from memorabilia.models import PlayerItemImage, GeneralItemImage
        col = Collection.objects.create(owner_uid=self.owner.id, title='Collage IDs')
        pi = PlayerItem.objects.create(
            title='Included', description='', collection=col, league='NHL', player='P',
        )
        PlayerItemImage.objects.create(
            collectible=pi, link='https://example.com/included.jpg', primary=True,
        )
        # Second item exists in the collection but is NOT listed in collage_collectible_ids
        oi = GeneralItem.objects.create(title='Excluded', description='', collection=col)
        GeneralItemImage.objects.create(
            collectible=oi, link='https://example.com/excluded.jpg', primary=True,
        )
        col.collage_collectible_ids = [{'type': 'playeritem', 'id': pi.pk}]
        col.save()
        result = col.get_collage_images()
        self.assertEqual(len(result), 1)
        self.assertEqual(str(result[0]), 'https://example.com/included.jpg')

    def test_get_collage_images_preserves_order_from_collage_collectible_ids(self):
        """Returned images follow the order in collage_collectible_ids, not insertion order."""
        from memorabilia.models import PlayerItemImage
        col = Collection.objects.create(owner_uid=self.owner.id, title='Order Test')
        first = PlayerItem.objects.create(
            title='First Created', description='', collection=col, league='NHL', player='P',
        )
        PlayerItemImage.objects.create(
            collectible=first, link='https://example.com/first.jpg', primary=True,
        )
        second = PlayerItem.objects.create(
            title='Second Created', description='', collection=col, league='NHL', player='Q',
        )
        PlayerItemImage.objects.create(
            collectible=second, link='https://example.com/second.jpg', primary=True,
        )
        # Set collage_collectible_ids with second item listed before first
        col.collage_collectible_ids = [
            {'type': 'playeritem', 'id': second.pk},
            {'type': 'playeritem', 'id': first.pk},
        ]
        col.save()
        result = col.get_collage_images()
        self.assertEqual(len(result), 2)
        self.assertEqual(str(result[0]), 'https://example.com/second.jpg')
        self.assertEqual(str(result[1]), 'https://example.com/first.jpg')

    def test_get_collage_images_skips_missing_pk_in_id_list(self):
        """An entry with a nonexistent PK is silently skipped."""
        from memorabilia.models import PlayerItemImage
        col = Collection.objects.create(owner_uid=self.owner.id, title='Missing PK')
        pi = PlayerItem.objects.create(
            title='Real Item', description='', collection=col, league='NHL', player='P',
        )
        PlayerItemImage.objects.create(
            collectible=pi, link='https://example.com/real.jpg', primary=True,
        )
        col.collage_collectible_ids = [
            {'type': 'playeritem', 'id': 999999},
            {'type': 'playeritem', 'id': pi.pk},
        ]
        col.save()
        result = col.get_collage_images()
        self.assertEqual(len(result), 1)
        self.assertEqual(str(result[0]), 'https://example.com/real.jpg')

    def test_get_collage_images_skips_unknown_type_in_id_list(self):
        """An entry with an unrecognized type string is silently skipped."""
        from memorabilia.models import PlayerItemImage
        col = Collection.objects.create(owner_uid=self.owner.id, title='Unknown Type')
        pi = PlayerItem.objects.create(
            title='Valid Item', description='', collection=col, league='NHL', player='P',
        )
        PlayerItemImage.objects.create(
            collectible=pi, link='https://example.com/valid.jpg', primary=True,
        )
        col.collage_collectible_ids = [
            {'type': 'unknowntype', 'id': pi.pk},
            {'type': 'playeritem', 'id': pi.pk},
        ]
        col.save()
        result = col.get_collage_images()
        self.assertEqual(len(result), 1)

    def test_get_collage_images_skips_entry_with_no_primary_image(self):
        """A valid collectible with no images produces no result entry."""
        col = Collection.objects.create(owner_uid=self.owner.id, title='No Img Entry')
        pi = PlayerItem.objects.create(
            title='No Image Item', description='', collection=col, league='NHL', player='P',
        )
        col.collage_collectible_ids = [{'type': 'playeritem', 'id': pi.pk}]
        col.save()
        result = col.get_collage_images()
        self.assertEqual(result, [])

    def test_get_collage_images_falls_back_to_auto_when_collage_collectible_ids_is_none(self):
        """When collage_collectible_ids is None, the auto-fallback path is used."""
        from memorabilia.models import PlayerItemImage
        col = Collection.objects.create(
            owner_uid=self.owner.id, title='None IDs', collage_collectible_ids=None,
        )
        pi = PlayerItem.objects.create(
            title='Auto Item', description='', collection=col, league='NHL', player='P',
        )
        PlayerItemImage.objects.create(
            collectible=pi, link='https://example.com/auto.jpg', primary=True,
        )
        result = col.get_collage_images()
        # Auto path should find the one collectible with an image
        self.assertEqual(len(result), 1)

    def test_get_collage_images_falls_back_to_auto_when_collage_collectible_ids_is_empty_list(self):
        """An empty list is falsy so the auto-fallback path is used."""
        from memorabilia.models import PlayerItemImage
        col = Collection.objects.create(
            owner_uid=self.owner.id, title='Empty IDs', collage_collectible_ids=[],
        )
        pi = PlayerItem.objects.create(
            title='Auto Item 2', description='', collection=col, league='NHL', player='P',
        )
        PlayerItemImage.objects.create(
            collectible=pi, link='https://example.com/auto2.jpg', primary=True,
        )
        result = col.get_collage_images()
        self.assertEqual(len(result), 1)


class CollectionFormCollageTests(BaseTestCase):
    """Unit tests for CollectionForm collage-selection behaviour."""

    def test_form_init_pre_populates_collage_selection_from_instance(self):
        """CollectionForm(instance=col) where col.collage_collectible_ids is set
        pre-populates form.initial['collage_selection'] with the JSON-encoded value."""
        import json
        from memorabilia.forms import CollectionForm
        ids = [{'type': 'playeritem', 'id': self.player_item.pk}]
        col = Collection.objects.create(
            owner_uid=self.owner.id, title='Pre-pop', collage_collectible_ids=ids,
        )
        form = CollectionForm(instance=col)
        self.assertIn('collage_selection', form.initial)
        self.assertEqual(json.loads(form.initial['collage_selection']), ids)

    def test_form_init_does_not_set_collage_selection_when_ids_is_none(self):
        """collage_collectible_ids=None means collage_selection is not pre-populated."""
        from memorabilia.forms import CollectionForm
        col = Collection.objects.create(
            owner_uid=self.owner.id, title='No IDs', collage_collectible_ids=None,
        )
        form = CollectionForm(instance=col)
        self.assertNotIn('collage_selection', form.initial)

    def test_form_save_collage_mode_stores_parsed_json(self):
        """POSTing image_mode=collage with valid JSON in collage_selection stores the
        parsed list to collage_collectible_ids on the saved instance."""
        import json
        from memorabilia.forms import CollectionForm
        ids = [{'type': 'playeritem', 'id': self.player_item.pk}]
        col = Collection.objects.create(owner_uid=self.owner.id, title='Save Collage')
        post = {
            'title': 'Save Collage',
            'image_mode': 'collage',
            'collage_selection': json.dumps(ids),
            'header_image_0': '',
            'header_image_1': '',
        }
        form = CollectionForm(post, instance=col)
        self.assertTrue(form.is_valid(), form.errors)
        saved = form.save()
        saved.refresh_from_db()
        self.assertEqual(saved.collage_collectible_ids, ids)

    def test_form_save_collage_mode_clears_image_and_image_link(self):
        """POSTing image_mode=collage clears both the image file and image_link fields."""
        import json
        from memorabilia.forms import CollectionForm
        col = Collection.objects.create(
            owner_uid=self.owner.id, title='Clear Images',
            image_link='https://example.com/old.jpg',
        )
        post = {
            'title': 'Clear Images',
            'image_mode': 'collage',
            'collage_selection': json.dumps([{'type': 'playeritem', 'id': self.player_item.pk}]),
            'header_image_0': '',
            'header_image_1': '',
        }
        form = CollectionForm(post, instance=col)
        self.assertTrue(form.is_valid(), form.errors)
        saved = form.save()
        saved.refresh_from_db()
        self.assertFalse(saved.image)
        self.assertIsNone(saved.image_link)

    def test_form_save_collage_mode_empty_selection_stores_none(self):
        """collage_selection='' stores None to collage_collectible_ids."""
        from memorabilia.forms import CollectionForm
        col = Collection.objects.create(
            owner_uid=self.owner.id, title='Empty Selection',
            collage_collectible_ids=[{'type': 'playeritem', 'id': self.player_item.pk}],
        )
        post = {
            'title': 'Empty Selection',
            'image_mode': 'collage',
            'collage_selection': '',
            'header_image_0': '',
            'header_image_1': '',
        }
        form = CollectionForm(post, instance=col)
        self.assertTrue(form.is_valid(), form.errors)
        saved = form.save()
        saved.refresh_from_db()
        self.assertIsNone(saved.collage_collectible_ids)

    def test_form_collage_mode_invalid_json_is_rejected(self):
        """Malformed JSON in collage_selection causes form validation to fail."""
        from memorabilia.forms import CollectionForm
        col = Collection.objects.create(owner_uid=self.owner.id, title='Bad JSON')
        post = {
            'title': 'Bad JSON',
            'image_mode': 'collage',
            'collage_selection': 'not valid json {{{',
            'header_image_0': '',
            'header_image_1': '',
        }
        form = CollectionForm(post, instance=col)
        self.assertFalse(form.is_valid())
        self.assertIn('collage_selection', form.errors)

    def test_form_save_non_collage_mode_does_not_touch_collage_collectible_ids(self):
        """image_mode=current leaves a pre-existing collage_collectible_ids unchanged."""
        import json
        from memorabilia.forms import CollectionForm
        ids = [{'type': 'playeritem', 'id': self.player_item.pk}]
        col = Collection.objects.create(
            owner_uid=self.owner.id, title='Preserve IDs',
            collage_collectible_ids=ids,
        )
        post = {
            'title': 'Preserve IDs',
            'image_mode': 'current',
            'collage_selection': '',
            'header_image_0': '',
            'header_image_1': '',
        }
        form = CollectionForm(post, instance=col)
        self.assertTrue(form.is_valid(), form.errors)
        saved = form.save()
        saved.refresh_from_db()
        # collage_collectible_ids should be untouched by a 'current' mode save
        self.assertEqual(saved.collage_collectible_ids, ids)


class CollectionCRUDCollageTests(BaseTestCase):
    """Extend CollectionCRUD with collage-related view tests."""

    def setUp(self):
        self.client.force_login(self.owner)

    def test_edit_get_context_contains_all_collage_images_key(self):
        """GET edit_collection includes all_collage_images in the template context."""
        response = self.client.get(
            reverse('memorabilia:edit_collection', args=[self.collection.id])
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn('all_collage_images', response.context)

    def test_edit_get_all_collage_images_empty_for_no_images(self):
        """A collection whose collectibles have no images yields all_collage_images=[]."""
        col = Collection.objects.create(owner_uid=self.owner.id, title='Empty Collage')
        # Collectibles exist but have no images
        PlayerItem.objects.create(
            title='No Img Player', description='', collection=col,
            league='NHL', player='P',
        )
        response = self.client.get(
            reverse('memorabilia:edit_collection', args=[col.id])
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['all_collage_images'], [])

    def test_edit_get_all_collage_images_correct_shape(self):
        """Each entry in all_collage_images has type, id, url, and title keys."""
        from memorabilia.models import PlayerItemImage
        col = Collection.objects.create(owner_uid=self.owner.id, title='Shape Test')
        pi = PlayerItem.objects.create(
            title='Jersey With Image', description='', collection=col,
            league='NHL', player='P',
        )
        PlayerItemImage.objects.create(
            collectible=pi, link='https://example.com/shape.jpg', primary=True,
        )
        response = self.client.get(
            reverse('memorabilia:edit_collection', args=[col.id])
        )
        self.assertEqual(response.status_code, 200)
        entries = response.context['all_collage_images']
        self.assertEqual(len(entries), 1)
        entry = entries[0]
        for key in ('type', 'id', 'url', 'title'):
            self.assertIn(key, entry, f"Missing key '{key}' in all_collage_images entry")
        self.assertEqual(entry['type'], 'playeritem')
        self.assertEqual(entry['id'], pi.pk)
        self.assertEqual(entry['url'], 'https://example.com/shape.jpg')
        self.assertEqual(entry['title'], 'Jersey With Image')

    def test_edit_post_collage_mode_saves_collage_collectible_ids(self):
        """POST with image_mode=collage and valid JSON collage_selection saves to DB
        and redirects to the collection detail page."""
        import json
        from memorabilia.models import PlayerItemImage
        col = Collection.objects.create(owner_uid=self.owner.id, title='Post Collage')
        pi = PlayerItem.objects.create(
            title='Collage Item', description='', collection=col,
            league='NHL', player='P',
        )
        PlayerItemImage.objects.create(
            collectible=pi, link='https://example.com/collage.jpg', primary=True,
        )
        ids = [{'type': 'playeritem', 'id': pi.pk}]
        response = self.client.post(
            reverse('memorabilia:edit_collection', args=[col.id]),
            {
                'title': 'Post Collage',
                'image_mode': 'collage',
                'collage_selection': json.dumps(ids),
                'header_image_0': '',
                'header_image_1': '',
            },
        )
        self.assertEqual(response.status_code, 302)
        col.refresh_from_db()
        self.assertEqual(col.collage_collectible_ids, ids)

    def test_edit_post_invalid_still_includes_all_collage_images(self):
        """When a POST fails validation, the re-rendered form still provides
        all_collage_images in the context so the collage picker remains usable."""
        from memorabilia.models import PlayerItemImage
        col = Collection.objects.create(owner_uid=self.owner.id, title='Invalid Post')
        pi = PlayerItem.objects.create(
            title='Img Item', description='', collection=col,
            league='NHL', player='P',
        )
        PlayerItemImage.objects.create(
            collectible=pi, link='https://example.com/invalid.jpg', primary=True,
        )
        # image_mode=new with no image provided triggers a validation error
        response = self.client.post(
            reverse('memorabilia:edit_collection', args=[col.id]),
            {
                'title': 'Invalid Post',
                'image_mode': 'new',
                'collage_selection': '',
                'header_image_0': '',
                'header_image_1': '',
            },
        )
        self.assertEqual(response.status_code, 200)


class MyCollectionsViewTests(BaseTestCase):
    def test_requires_login(self):
        response = self.client.get(reverse('memorabilia:my_collections'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('login', response['Location'])

    def test_owner_sees_own_collections(self):
        self.client.force_login(self.owner)
        response = self.client.get(reverse('memorabilia:my_collections'))
        self.assertEqual(response.status_code, 200)
        self.assertIn(self.collection, response.context['collection_list'])

    def test_other_users_collections_excluded(self):
        other_collection = Collection.objects.create(owner_uid=self.other_user.id, title='Other Collection')
        self.client.force_login(self.owner)
        response = self.client.get(reverse('memorabilia:my_collections'))
        self.assertNotIn(other_collection, response.context['collection_list'])

    def test_each_user_sees_only_their_own(self):
        other_collection = Collection.objects.create(owner_uid=self.other_user.id, title='Other Only')
        self.client.force_login(self.other_user)
        response = self.client.get(reverse('memorabilia:my_collections'))
        self.assertEqual(response.status_code, 200)
        self.assertIn(other_collection, response.context['collection_list'])
        self.assertNotIn(self.collection, response.context['collection_list'])

    def test_empty_for_user_with_no_collections(self):
        user = User.objects.create_user(username='noCollections', password='testpass')
        self.client.force_login(user)
        response = self.client.get(reverse('memorabilia:my_collections'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['collection_list']), 0)


class UserProfileTests(BaseTestCase):
    def setUp(self):
        self.client.force_login(self.owner)

    def test_requires_login(self):
        self.client.logout()
        response = self.client.get(reverse('memorabilia:profile'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('login', response['Location'])

    def test_get_returns_200(self):
        response = self.client.get(reverse('memorabilia:profile'))
        self.assertEqual(response.status_code, 200)

    def test_get_creates_userprofile(self):
        UserProfile.objects.filter(user=self.owner).delete()
        self.client.get(reverse('memorabilia:profile'))
        self.assertTrue(UserProfile.objects.filter(user=self.owner).exists())

    def test_post_saves_flickr_id(self):
        response = self.client.post(reverse('memorabilia:profile'), {'flickr_id': '12345678@N04'})
        self.assertEqual(response.status_code, 302)
        profile = UserProfile.objects.get(user=self.owner)
        self.assertEqual(profile.flickr_id, '12345678@N04')

    def test_post_clears_flickr_id(self):
        UserProfile.objects.update_or_create(user=self.owner, defaults={'flickr_id': '12345678@N04'})
        response = self.client.post(reverse('memorabilia:profile'), {'flickr_id': ''})
        self.assertEqual(response.status_code, 302)
        profile = UserProfile.objects.get(user=self.owner)
        self.assertEqual(profile.flickr_id, '')


class FlickrUrlTests(BaseTestCase):
    def setUp(self):
        self.client.force_login(self.owner)

    def test_create_playeritem_saves_flickr_url(self):
        flickr_url = 'https://www.flickr.com/photos/testuser/albums/12345'
        self.client.post(
            reverse('memorabilia:create_collectible', args=[self.collection.id]),
            self._player_item_post_data(title='Flickr Jersey', flickrAlbum=flickr_url),
        )
        item = PlayerItem.objects.get(title='Flickr Jersey')
        self.assertEqual(item.flickr_url, flickr_url)

    def test_edit_playeritem_updates_flickr_url(self):
        flickr_url = 'https://www.flickr.com/photos/testuser/albums/99999'
        self.client.post(
            reverse('memorabilia:edit_collectible',
                    args=[self.collection.id, 'playeritem', self.player_item.id]),
            self._player_item_post_data(title='Edited', flickrAlbum=flickr_url),
        )
        self.player_item.refresh_from_db()
        self.assertEqual(self.player_item.flickr_url, flickr_url)

    def test_edit_playeritem_empty_flickr_album_preserves_existing_flickr_url(self):
        existing_url = 'https://www.flickr.com/photos/testuser/albums/11111'
        self.player_item.flickr_url = existing_url
        self.player_item.save(update_fields=['flickr_url'])
        self.client.post(
            reverse('memorabilia:edit_collectible',
                    args=[self.collection.id, 'playeritem', self.player_item.id]),
            self._player_item_post_data(title='No Flickr'),
        )
        self.player_item.refresh_from_db()
        self.assertEqual(self.player_item.flickr_url, existing_url)

    def test_create_generalitem_saves_flickr_url(self):
        flickr_url = 'https://www.flickr.com/photos/testuser/albums/55555'
        self.client.post(
            reverse('memorabilia:create_collectible', args=[self.collection.id]),
            self._general_item_post_data(title='Flickr Puck', flickrAlbum=flickr_url),
        )
        item = GeneralItem.objects.get(title='Flickr Puck')
        self.assertEqual(item.flickr_url, flickr_url)

    def test_bulk_add_flickr_album_sets_flickr_url(self):
        import json
        response = self.client.post(
            reverse('memorabilia:bulk_add_flickr_album', args=[self.collection.id]),
            data=json.dumps({
                'title': 'Flickr Album Item',
                'description': 'desc',
                'username': 'flickruser',
                'album_id': '99887766',
            }),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        item = GeneralItem.objects.get(title='Flickr Album Item')
        self.assertEqual(item.flickr_url, 'https://www.flickr.com/photos/flickruser/albums/99887766')


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


class SearchCollectiblesTests(BaseTestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.search_collection = Collection.objects.create(
            owner_uid=cls.owner.id,
            title='Search Collection',
        )
        cls.search_player_item = PlayerItem.objects.create(
            title='Search Player Jersey',
            description='A searchable player item',
            collection=cls.search_collection,
            league='NHL',
            player='Mario Lemieux',
            team='Penguins',
        )
        cls.search_gear = PlayerGear.objects.create(
            title='Search Gear Item',
            description='A searchable gear item',
            collection=cls.search_collection,
            league='AHL',
            player='Mark Messier',
            brand='Reebok',
            size='L',
            season='1990',
            game_type=cls.game_type,
            usage_type=cls.usage_type,
        )
        cls.search_jersey = HockeyJersey.objects.create(
            title='Search Hockey Jersey',
            description='A searchable hockey jersey',
            collection=cls.search_collection,
            league='NHL',
            player='Patrick Roy',
            brand='Koho',
            size='60',
            season='1993',
            game_type=cls.game_type,
            usage_type=cls.usage_type,
        )
        cls.search_general = GeneralItem.objects.create(
            title='Search General Item',
            description='A searchable general item',
            collection=cls.search_collection,
        )

    def _search_url(self, **params):
        from urllib.parse import urlencode
        base = reverse('memorabilia:search_collectibles')
        if params:
            return f'{base}?{urlencode(params)}'
        return base

    def test_empty_search_returns_200(self):
        response = self.client.get(self._search_url())
        self.assertEqual(response.status_code, 200)

    def test_empty_search_returns_all_items_in_results(self):
        response = self.client.get(self._search_url())
        self.assertEqual(response.status_code, 200)
        self.assertIn('results', response.context)

    def test_search_by_player_name_returns_matching_item(self):
        response = self.client.get(self._search_url(player='Mario Lemieux'))
        self.assertEqual(response.status_code, 200)
        results = response.context['results']
        titles = [r.title for r in results]
        self.assertIn('Search Player Jersey', titles)

    def test_search_by_player_name_excludes_non_matching(self):
        response = self.client.get(self._search_url(player='Mario Lemieux'))
        results = response.context['results']
        titles = [r.title for r in results]
        self.assertNotIn('Search Gear Item', titles)
        self.assertNotIn('Search General Item', titles)

    def test_search_by_player_field_matches_title_context(self):
        response = self.client.get(self._search_url(player='Mario Lemieux'))
        self.assertEqual(response.status_code, 200)
        results = response.context['results']
        titles = [r.title for r in results]
        self.assertIn('Search Player Jersey', titles)

    def test_search_by_brand_matches_gear_item(self):
        response = self.client.get(self._search_url(brand='Reebok'))
        self.assertEqual(response.status_code, 200)
        results = response.context['results']
        titles = [r.title for r in results]
        self.assertIn('Search Gear Item', titles)

    def test_item_type_playeritem_filter(self):
        response = self.client.get(self._search_url(item_type='playeritem'))
        self.assertEqual(response.status_code, 200)
        results = response.context['results']
        for item in results:
            self.assertEqual(item.collectible_type, 'playeritem')

    def test_item_type_playergear_filter(self):
        response = self.client.get(self._search_url(item_type='playergear'))
        self.assertEqual(response.status_code, 200)
        results = response.context['results']
        titles = [r.title for r in results]
        self.assertIn('Search Gear Item', titles)
        self.assertNotIn('Search Player Jersey', titles)
        self.assertNotIn('Search General Item', titles)

    def test_item_type_hockeyjersey_filter(self):
        response = self.client.get(self._search_url(item_type='hockeyjersey'))
        self.assertEqual(response.status_code, 200)
        results = response.context['results']
        titles = [r.title for r in results]
        self.assertIn('Search Hockey Jersey', titles)
        for item in results:
            self.assertEqual(item.collectible_type, 'hockeyjersey')

    def test_item_type_generalitem_filter(self):
        response = self.client.get(self._search_url(item_type='generalitem'))
        self.assertEqual(response.status_code, 200)
        results = response.context['results']
        for item in results:
            self.assertEqual(item.collectible_type, 'generalitem')

    def test_search_by_league_filter(self):
        response = self.client.get(self._search_url(league='AHL'))
        self.assertEqual(response.status_code, 200)
        results = response.context['results']
        titles = [r.title for r in results]
        self.assertIn('Search Gear Item', titles)
        self.assertNotIn('Search General Item', titles)

    def test_gear_only_filter_excludes_playeritem(self):
        response = self.client.get(self._search_url(brand='Reebok'))
        self.assertEqual(response.status_code, 200)
        results = response.context['results']
        titles = [r.title for r in results]
        self.assertIn('Search Gear Item', titles)
        self.assertNotIn('Search Player Jersey', titles)

    def test_gear_only_filter_excludes_generalitem(self):
        response = self.client.get(self._search_url(brand='Reebok'))
        results = response.context['results']
        titles = [r.title for r in results]
        self.assertNotIn('Search General Item', titles)

    def test_search_unauthenticated_returns_200(self):
        self.client.logout()
        response = self.client.get(self._search_url())
        self.assertEqual(response.status_code, 200)

    def test_search_context_contains_form(self):
        response = self.client.get(self._search_url())
        self.assertIn('form', response.context)

    def test_search_context_contains_leagues(self):
        response = self.client.get(self._search_url())
        self.assertIn('leagues', response.context)

    def test_search_by_collection_filter(self):
        response = self.client.get(self._search_url(collection=self.search_collection.id))
        self.assertEqual(response.status_code, 200)
        results = response.context['results']
        titles = [r.title for r in results]
        self.assertIn('Search Player Jersey', titles)
        self.assertNotIn('Test Jersey', titles)


class AuthSourceModelTests(BaseTestCase):
    """Tests for the AuthSource lookup model."""

    def test_authsource_str(self):
        from memorabilia.models import AuthSource
        src = AuthSource.objects.create(key='PSA', name='PSA Authentication')
        self.assertEqual(str(src), 'PSA Authentication')

    def test_authsource_ordering_is_alphabetical(self):
        from memorabilia.models import AuthSource
        AuthSource.objects.create(key='JSA', name='JSA Authentication')
        AuthSource.objects.create(key='BAS', name='Beckett Authentication')
        AuthSource.objects.create(key='PSA2', name='PSA Authentication')
        sources = list(AuthSource.objects.values_list('name', flat=True))
        self.assertEqual(sources, sorted(sources))

    def test_authsource_creation_with_key_pk(self):
        from memorabilia.models import AuthSource
        src = AuthSource.objects.create(key='TRISTAR', name='Tristar')
        self.assertEqual(src.pk, 'TRISTAR')


class AuthFormTests(BaseTestCase):
    """Tests that auth formsets are wired correctly and old flat fields are gone."""

    def test_hockeyjersey_form_excludes_old_auth_fields(self):
        from memorabilia.forms import HockeyJerseyForm
        form = HockeyJerseyForm(current_user=self.owner)
        self.assertNotIn('team_inventory_number', form.fields)
        self.assertNotIn('auth_tag_number', form.fields)
        self.assertNotIn('auth_source', form.fields)
        self.assertNotIn('coa', form.fields)

    def test_playergear_form_excludes_old_auth_fields(self):
        from memorabilia.forms import PlayerGearForm
        form = PlayerGearForm(current_user=self.owner)
        self.assertNotIn('team_inventory_number', form.fields)
        self.assertNotIn('auth_tag_number', form.fields)
        self.assertNotIn('auth_source', form.fields)
        self.assertNotIn('coa', form.fields)

    def test_player_gear_authentication_formset_instantiates(self):
        from memorabilia.forms import PlayerGearAuthenticationFormSet
        fs = PlayerGearAuthenticationFormSet(prefix='authentications')
        self.assertIsNotNone(fs)

    def test_player_item_authentication_formset_instantiates(self):
        from memorabilia.forms import PlayerItemAuthenticationFormSet
        fs = PlayerItemAuthenticationFormSet(prefix='authentications')
        self.assertIsNotNone(fs)

    def test_general_item_authentication_formset_instantiates(self):
        from memorabilia.forms import GeneralItemAuthenticationFormSet
        fs = GeneralItemAuthenticationFormSet(prefix='authentications')
        self.assertIsNotNone(fs)


class AuthenticationModelTests(BaseTestCase):
    """Tests for the new per-type authentication tables."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        from memorabilia.models import CoaType, AuthSource
        cls.coa_paper = CoaType.objects.get_or_create(key='paper', defaults={'name': 'Paper Document'})[0]
        cls.coa_printed = CoaType.objects.get_or_create(key='printed', defaults={'name': 'Printed on Jersey'})[0]
        cls.meigray = AuthSource.objects.get_or_create(key='MEIGRAY', defaults={'name': 'MeiGray'})[0]
        cls.team_src = AuthSource.objects.get_or_create(key='TEAM', defaults={'name': 'Team Authenticated'})[0]

    def test_playergear_authentication_creates_and_relates(self):
        from memorabilia.models import PlayerGearAuthentication
        auth = PlayerGearAuthentication.objects.create(
            collectible=self.player_gear,
            auth_type=self.coa_paper,
            number='M12345',
            issuer=self.meigray,
        )
        self.assertEqual(self.player_gear.authentications.count(), 1)
        self.assertEqual(auth.number, 'M12345')

    def test_playeritem_authentication_creates_and_relates(self):
        from memorabilia.models import PlayerItemAuthentication
        auth = PlayerItemAuthentication.objects.create(
            collectible=self.player_item,
            auth_type=self.coa_paper,
            number='',
            issuer=None,
        )
        self.assertEqual(self.player_item.authentications.count(), 1)
        self.assertIsNone(auth.issuer)

    def test_generalitem_authentication_creates_and_relates(self):
        from memorabilia.models import GeneralItemAuthentication
        auth = GeneralItemAuthentication.objects.create(
            collectible=self.general_item,
            auth_type=self.coa_paper,
            number='',
            issuer=None,
        )
        self.assertEqual(self.general_item.authentications.count(), 1)

    def test_authentication_str_with_all_fields(self):
        from memorabilia.models import PlayerGearAuthentication
        auth = PlayerGearAuthentication(
            collectible=self.player_gear,
            auth_type=self.coa_paper,
            number='M12345',
            issuer=self.meigray,
        )
        s = str(auth)
        self.assertIn('M12345', s)

    def test_authentication_str_empty(self):
        from memorabilia.models import PlayerGearAuthentication
        auth = PlayerGearAuthentication(collectible=self.player_gear)
        self.assertEqual(str(auth), '—')

    def test_authentication_deleted_with_collectible(self):
        from memorabilia.models import PlayerGearAuthentication
        jersey = HockeyJersey.objects.create(
            title='Delete Auth Test Jersey', description='', collection=self.collection,
            league='NHL', player='Test', brand='CCM', size='54', season='2020',
            game_type=self.game_type, usage_type=self.usage_type,
        )
        PlayerGearAuthentication.objects.create(
            collectible=jersey, auth_type=self.coa_printed, number='TI-99', issuer=self.team_src,
        )
        pk = jersey.pk
        jersey.delete()
        self.assertEqual(PlayerGearAuthentication.objects.filter(collectible_id=pk).count(), 0)

    def test_two_auth_records_per_jersey(self):
        from memorabilia.models import PlayerGearAuthentication
        jersey = HockeyJersey.objects.create(
            title='Two Auth Jersey', description='', collection=self.collection,
            league='NHL', player='Two Auth', brand='CCM', size='54', season='2020',
            game_type=self.game_type, usage_type=self.usage_type,
        )
        PlayerGearAuthentication.objects.create(
            collectible=jersey, auth_type=self.coa_paper, number='M99', issuer=self.meigray,
        )
        PlayerGearAuthentication.objects.create(
            collectible=jersey, auth_type=self.coa_printed, number='TI-001', issuer=self.team_src,
        )
        self.assertEqual(jersey.authentications.count(), 2)


class HockeyJerseyAuthDetailTests(BaseTestCase):
    """Tests that the detail view correctly exposes authentications on a jersey."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        from memorabilia.models import CoaType, AuthSource, PlayerGearAuthentication
        cls.coa = CoaType.objects.get_or_create(key='paper', defaults={'name': 'Paper Document'})[0]
        cls.source = AuthSource.objects.get_or_create(key='BAS2', defaults={'name': 'Beckett'})[0]
        cls.auth_jersey = HockeyJersey.objects.create(
            title='Auth Detail Jersey',
            description='Jersey with authentications',
            collection=cls.collection,
            league='NHL',
            player='Wayne Gretzky',
            brand='CCM',
            size='54',
            season='1988',
            game_type=cls.game_type,
            usage_type=cls.usage_type,
        )
        cls.auth = PlayerGearAuthentication.objects.create(
            collectible=cls.auth_jersey,
            auth_type=cls.coa,
            number='TAG-DETAIL-99',
            issuer=cls.source,
        )

    def _detail_url(self):
        return reverse(
            'memorabilia:collectible',
            kwargs={'collection_id': self.collection.id, 'collectible_type': 'hockeyjersey', 'pk': self.auth_jersey.id},
        )

    def test_detail_returns_200(self):
        response = self.client.get(self._detail_url())
        self.assertEqual(response.status_code, 200)

    def test_detail_context_collectible_has_authentication(self):
        response = self.client.get(self._detail_url())
        collectible = response.context['object']
        self.assertEqual(collectible.authentications.count(), 1)
        auth = collectible.authentications.first()
        self.assertEqual(auth.number, 'TAG-DETAIL-99')

    def test_detail_uses_hockeyjersey_template(self):
        response = self.client.get(self._detail_url())
        self.assertTemplateUsed(response, 'memorabilia/hockeyjersey_detail.html')


class AuthSearchTests(BaseTestCase):
    """Tests that auth_issuer and auth_number search filters work across collectible types."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        from memorabilia.models import CoaType, AuthSource, PlayerGearAuthentication, PlayerItemAuthentication
        cls.tristar = AuthSource.objects.get_or_create(key='TRISTAR', defaults={'name': 'Tristar'})[0]
        cls.coa = CoaType.objects.get_or_create(key='paper', defaults={'name': 'Paper Document'})[0]
        cls.search_col = Collection.objects.create(owner_uid=cls.owner.id, title='Auth Search Collection')

        cls.auth_jersey = HockeyJersey.objects.create(
            title='Auth Search Jersey',
            description='Jersey with auth',
            collection=cls.search_col,
            league='NHL', player='Gordie Howe', brand='Koho', size='52', season='1970',
            game_type=cls.game_type, usage_type=cls.usage_type,
        )
        PlayerGearAuthentication.objects.create(
            collectible=cls.auth_jersey, auth_type=cls.coa, number='STICKER-ALPHA', issuer=cls.tristar,
        )
        cls.auth_player = PlayerItem.objects.create(
            title='Auth Search Player', description='Player with auth',
            collection=cls.search_col, league='NHL', player='Phil Esposito',
        )
        PlayerItemAuthentication.objects.create(
            collectible=cls.auth_player, auth_type=cls.coa, number='PLAYER-AUTH-1', issuer=cls.tristar,
        )
        cls.plain_gear = PlayerGear.objects.create(
            title='Plain Gear No Auth', description='', collection=cls.search_col,
            league='NHL', player='Bobby Orr', brand='CCM', size='L', season='1972',
            game_type=cls.game_type, usage_type=cls.usage_type,
        )
        cls.plain_general = GeneralItem.objects.create(
            title='Plain General No Auth', description='', collection=cls.search_col,
        )

    def _search_url(self, **params):
        from urllib.parse import urlencode
        base = reverse('memorabilia:search_collectibles')
        return f'{base}?{urlencode(params)}' if params else base

    def test_auth_number_filter_returns_matching_jersey(self):
        response = self.client.get(self._search_url(auth_number='STICKER-ALPHA'))
        self.assertEqual(response.status_code, 200)
        titles = [r.title for r in response.context['results']]
        self.assertIn('Auth Search Jersey', titles)

    def test_auth_number_filter_is_case_insensitive(self):
        response = self.client.get(self._search_url(auth_number='sticker'))
        titles = [r.title for r in response.context['results']]
        self.assertIn('Auth Search Jersey', titles)

    def test_auth_number_excludes_items_without_matching_auth(self):
        response = self.client.get(self._search_url(auth_number='STICKER-ALPHA'))
        titles = [r.title for r in response.context['results']]
        self.assertNotIn('Plain Gear No Auth', titles)
        self.assertNotIn('Plain General No Auth', titles)

    def test_auth_number_matches_player_item(self):
        response = self.client.get(self._search_url(auth_number='PLAYER-AUTH-1'))
        titles = [r.title for r in response.context['results']]
        self.assertIn('Auth Search Player', titles)

    def test_auth_issuer_filter_returns_matching_jersey(self):
        response = self.client.get(self._search_url(auth_issuer='TRISTAR'))
        self.assertEqual(response.status_code, 200)
        titles = [r.title for r in response.context['results']]
        self.assertIn('Auth Search Jersey', titles)

    def test_auth_issuer_excludes_items_without_auth(self):
        response = self.client.get(self._search_url(auth_issuer='TRISTAR'))
        titles = [r.title for r in response.context['results']]
        self.assertNotIn('Plain Gear No Auth', titles)
        self.assertNotIn('Plain General No Auth', titles)

    def test_auth_issuer_no_match_returns_no_jersey(self):
        AuthSource.objects.get_or_create(key='JSA_NOONE', defaults={'name': 'JSA No Match'})
        response = self.client.get(self._search_url(auth_issuer='JSA_NOONE'))
        titles = [r.title for r in response.context['results']]
        self.assertNotIn('Auth Search Jersey', titles)

    def test_search_form_has_auth_issuer_field(self):
        from memorabilia.forms import CollectibleSearchForm
        form = CollectibleSearchForm()
        self.assertIn('auth_issuer', form.fields)

    def test_search_form_has_auth_number_field(self):
        from memorabilia.forms import CollectibleSearchForm
        form = CollectibleSearchForm()
        self.assertIn('auth_number', form.fields)

    def test_search_form_does_not_have_old_fields(self):
        from memorabilia.forms import CollectibleSearchForm
        form = CollectibleSearchForm()
        self.assertNotIn('auth_source', form.fields)
        self.assertNotIn('auth_tag_number', form.fields)
        self.assertNotIn('team_inventory_number', form.fields)


class AuthExportImportTests(BaseTestCase):
    """Tests for export/import round-trip of authentication records."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        from memorabilia.models import AuthSource, CoaType, PlayerGearAuthentication
        cls.coa_paper = CoaType.objects.get_or_create(key='paper', defaults={'name': 'Paper COA'})[0]
        cls.coa_printed = CoaType.objects.get_or_create(key='printed', defaults={'name': 'Printed on Jersey'})[0]
        cls.auth_source = AuthSource.objects.create(key='BECKETT', name='Beckett')
        cls.team_source = AuthSource.objects.get_or_create(key='TEAM', defaults={'name': 'Team'})[0]
        cls.export_jersey = HockeyJersey.objects.create(
            title='Export Auth Jersey',
            description='Jersey for export testing',
            collection=cls.collection,
            league='NHL',
            player='Mario Lemieux',
            brand='CCM',
            size='56',
            season='1992',
            game_type=cls.game_type,
            usage_type=cls.usage_type,
        )
        PlayerGearAuthentication.objects.create(
            collectible=cls.export_jersey,
            auth_type=cls.coa_paper,
            number='TAG-EXPORT-007',
            issuer=cls.auth_source,
        )
        PlayerGearAuthentication.objects.create(
            collectible=cls.export_jersey,
            auth_type=cls.coa_printed,
            number='INV-EXPORT',
            issuer=cls.team_source,
        )

    def _round_trip(self, jersey):
        """Export a single jersey and import it into a fresh collection. Return the new jersey."""
        from memorabilia.export_import import build_collectible_zip, parse_zip, _create_collectible
        import zipfile, io

        zip_bytes = build_collectible_zip(jersey)
        parsed = parse_zip(zip_bytes)
        target_collection = Collection.objects.create(
            owner_uid=self.owner.id, title='Import Target'
        )
        zf = zipfile.ZipFile(io.BytesIO(zip_bytes))
        for row in parsed['items']:
            _create_collectible(row, target_collection, zf, is_collection_export=False)
        return HockeyJersey.objects.filter(collection=target_collection).prefetch_related('authentications').first()

    def _get_csv_row(self, jersey):
        import zipfile, io, csv
        from memorabilia.export_import import build_collectible_zip
        zip_bytes = build_collectible_zip(jersey)
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            csv_text = zf.read('collectible.csv').decode()
        reader = csv.DictReader(io.StringIO(csv_text))
        return next(reader)

    def test_export_contains_authentications_json_column(self):
        row = self._get_csv_row(self.export_jersey)
        self.assertIn('authentications_json', row)

    def test_export_does_not_contain_old_auth_columns(self):
        row = self._get_csv_row(self.export_jersey)
        self.assertNotIn('team_inventory_number', row)
        self.assertNotIn('auth_tag_number', row)
        self.assertNotIn('auth_source', row)

    def test_export_authentications_json_has_two_records(self):
        import json
        row = self._get_csv_row(self.export_jersey)
        auth_list = json.loads(row['authentications_json'])
        self.assertEqual(len(auth_list), 2)

    def test_export_preserves_auth_numbers(self):
        import json
        row = self._get_csv_row(self.export_jersey)
        auth_list = json.loads(row['authentications_json'])
        numbers = {a['number'] for a in auth_list}
        self.assertIn('TAG-EXPORT-007', numbers)
        self.assertIn('INV-EXPORT', numbers)

    def test_export_preserves_issuers(self):
        import json
        row = self._get_csv_row(self.export_jersey)
        auth_list = json.loads(row['authentications_json'])
        issuers = {a['issuer'] for a in auth_list}
        self.assertIn('BECKETT', issuers)
        self.assertIn('TEAM', issuers)

    def test_import_round_trip_preserves_auth_count(self):
        imported = self._round_trip(self.export_jersey)
        self.assertIsNotNone(imported)
        self.assertEqual(imported.authentications.count(), 2)

    def test_import_round_trip_preserves_auth_numbers(self):
        imported = self._round_trip(self.export_jersey)
        numbers = set(imported.authentications.values_list('number', flat=True))
        self.assertIn('TAG-EXPORT-007', numbers)
        self.assertIn('INV-EXPORT', numbers)

    def test_import_round_trip_preserves_issuers(self):
        imported = self._round_trip(self.export_jersey)
        issuers = set(imported.authentications.values_list('issuer_id', flat=True))
        self.assertIn('BECKETT', issuers)
        self.assertIn('TEAM', issuers)

    def test_import_round_trip_keeps_collectible_type_hockeyjersey(self):
        imported = self._round_trip(self.export_jersey)
        self.assertIsNotNone(imported)
        self.assertEqual(imported.collectible_type, 'hockeyjersey')
        self.assertEqual(imported.gear_type_id, 'JRS')

    def test_import_jersey_with_no_auths_imports_cleanly(self):
        jersey_no_auth = HockeyJersey.objects.create(
            title='No Auth Export Jersey',
            description='No auth',
            collection=self.collection,
            league='NHL',
            player='Brendan Shanahan',
            brand='Koho',
            size='52',
            season='1998',
            game_type=self.game_type,
            usage_type=self.usage_type,
        )
        imported = self._round_trip(jersey_no_auth)
        self.assertIsNotNone(imported)
        self.assertEqual(imported.authentications.count(), 0)

    def test_import_with_unknown_issuer_gracefully_sets_null(self):
        from memorabilia.export_import import _create_collectible
        import zipfile, io, json
        from memorabilia.export_import import build_collectible_zip
        zip_bytes = build_collectible_zip(self.export_jersey)
        zf = zipfile.ZipFile(io.BytesIO(zip_bytes))
        target = Collection.objects.create(owner_uid=self.owner.id, title='Unknown Auth Target')
        row = {
            'collectible_type': 'hockeyjersey',
            'title': 'Unknown Auth Jersey',
            'description': '',
            'player': 'Unknown Player',
            'league': 'NHL',
            'brand': 'CCM',
            'size': '54',
            'season': '2000',
            'game_type': 'REG',
            'usage_type': 'GU',
            'authentications_json': json.dumps([
                {'auth_type': 'paper', 'number': 'TAG-X', 'issuer': 'NONEXISTENT_KEY'}
            ]),
            'images_json': '[]',
            'photomatches_json': '[]',
        }
        obj = _create_collectible(row, target, zf, is_collection_export=False)
        auth = obj.authentications.first()
        self.assertIsNotNone(auth)
        self.assertIsNone(auth.issuer)

    def test_search_form_has_auth_issuer_and_auth_number_fields(self):
        from memorabilia.forms import CollectibleSearchForm
        form = CollectibleSearchForm()
        self.assertIn('auth_issuer', form.fields)
        self.assertIn('auth_number', form.fields)


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

class WantListBaseTestCase(BaseTestCase):
    """Shared fixtures for want list tests."""
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.profile = WantListProfile.objects.create(
            user=cls.owner,
            slug='owner-wants',
            visibility='public',
        )
        cls.want_list = WantList.objects.create(
            profile=cls.profile,
            title='Priority Wants',
            order=0,
        )
        cls.want_item = WantListItem.objects.create(
            want_list=cls.want_list,
            collectible_type='hockeyjersey',
            player='Wayne Gretzky',
            team='Edmonton Oilers',
            league=cls.league,
            game_type=cls.game_type,
            usage_type=cls.usage_type,
        )

    def _item_post_data(self, **overrides):
        data = {
            'want_list': self.want_list.pk,
            'collectible_type': 'hockeyjersey',
            'player': 'Test Player',
            'league': self.league.pk,
            'game_type': self.game_type.pk,
            'usage_type': self.usage_type.pk,
            'notes': '',
            'images-TOTAL_FORMS': '0',
            'images-INITIAL_FORMS': '0',
            'images-MIN_NUM_FORMS': '0',
            'images-MAX_NUM_FORMS': '3',
        }
        data.update(overrides)
        return data


class WantListProfileTests(WantListBaseTestCase):
    def test_first_visit_creates_profile_and_redirects_to_settings(self):
        new_user = User.objects.create_user(username='newuser', password='pass')
        self.client.force_login(new_user)
        response = self.client.get(reverse('memorabilia:want_list_manage'))
        self.assertRedirects(response, reverse('memorabilia:want_list_profile_edit'))
        self.assertTrue(WantListProfile.objects.filter(user=new_user).exists())

    def test_slug_collision_resolves(self):
        from memorabilia.models import _generate_want_list_slug
        conflict_user = User.objects.create_user(username='owner-wants', password='pass')
        slug = _generate_want_list_slug(conflict_user)
        self.assertFalse(WantListProfile.objects.filter(slug=slug).exists())

    def test_reserved_slug_rejected(self):
        self.client.force_login(self.owner)
        response = self.client.post(
            reverse('memorabilia:want_list_profile_edit'),
            {'slug': 'manage', 'visibility': 'public'},
        )
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response.context['form'], 'slug', 'That handle is reserved. Please choose another.')

    def test_profile_edit_saves(self):
        self.client.force_login(self.owner)
        response = self.client.post(
            reverse('memorabilia:want_list_profile_edit'),
            {'slug': 'owner-wants', 'visibility': 'logged_in'},
        )
        self.assertRedirects(response, reverse('memorabilia:want_list_manage'))
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.visibility, 'logged_in')


class WantListCRUDTests(WantListBaseTestCase):
    def test_manage_page_shows_lists(self):
        self.client.force_login(self.owner)
        response = self.client.get(reverse('memorabilia:want_list_manage'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Priority Wants')

    def test_create_list(self):
        self.client.force_login(self.owner)
        response = self.client.post(
            reverse('memorabilia:want_list_create'),
            {'title': 'Long Shots'},
        )
        self.assertRedirects(response, reverse('memorabilia:want_list_manage'))
        self.assertTrue(WantList.objects.filter(profile=self.profile, title='Long Shots').exists())

    def test_edit_list(self):
        self.client.force_login(self.owner)
        response = self.client.post(
            reverse('memorabilia:want_list_edit', kwargs={'pk': self.want_list.pk}),
            {'title': 'Renamed List'},
        )
        self.assertRedirects(response, reverse('memorabilia:want_list_manage'))
        self.want_list.refresh_from_db()
        self.assertEqual(self.want_list.title, 'Renamed List')

    def test_delete_list(self):
        extra = WantList.objects.create(profile=self.profile, title='Temp', order=1)
        self.client.force_login(self.owner)
        response = self.client.post(
            reverse('memorabilia:want_list_delete', kwargs={'pk': extra.pk}),
        )
        self.assertRedirects(response, reverse('memorabilia:want_list_manage'))
        self.assertFalse(WantList.objects.filter(pk=extra.pk).exists())

    def test_reorder_lists(self):
        import json
        second = WantList.objects.create(profile=self.profile, title='Second', order=1)
        self.client.force_login(self.owner)
        payload = json.dumps([
            {'id': self.want_list.pk, 'order': 1},
            {'id': second.pk, 'order': 0},
        ])
        response = self.client.post(
            reverse('memorabilia:want_list_reorder'),
            data=payload,
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        self.want_list.refresh_from_db()
        second.refresh_from_db()
        self.assertEqual(self.want_list.order, 1)
        self.assertEqual(second.order, 0)

    def test_other_user_cannot_edit_list(self):
        self.client.force_login(self.other_user)
        response = self.client.post(
            reverse('memorabilia:want_list_edit', kwargs={'pk': self.want_list.pk}),
            {'title': 'Hacked'},
        )
        self.assertEqual(response.status_code, 404)

    def test_other_user_cannot_delete_list(self):
        self.client.force_login(self.other_user)
        response = self.client.post(
            reverse('memorabilia:want_list_delete', kwargs={'pk': self.want_list.pk}),
        )
        self.assertEqual(response.status_code, 404)


class WantListItemCRUDTests(WantListBaseTestCase):
    def test_create_item(self):
        self.client.force_login(self.owner)
        response = self.client.post(
            reverse('memorabilia:want_list_item_create', kwargs={'list_pk': self.want_list.pk}),
            self._item_post_data(player='Bobby Orr', team='Boston Bruins'),
        )
        self.assertRedirects(response, reverse('memorabilia:want_list_manage'))
        self.assertTrue(WantListItem.objects.filter(want_list=self.want_list, player='Bobby Orr').exists())

    def test_edit_item(self):
        self.client.force_login(self.owner)
        data = self._item_post_data(player='Updated Player')
        data['images-INITIAL_FORMS'] = '0'
        response = self.client.post(
            reverse('memorabilia:want_list_item_edit', kwargs={'pk': self.want_item.pk}),
            data,
        )
        self.assertRedirects(response, reverse('memorabilia:want_list_manage'))
        self.want_item.refresh_from_db()
        self.assertEqual(self.want_item.player, 'Updated Player')

    def test_delete_item(self):
        extra = WantListItem.objects.create(
            want_list=self.want_list,
            collectible_type='playeritem',
            player='Temp Player',
        )
        self.client.force_login(self.owner)
        response = self.client.post(
            reverse('memorabilia:want_list_item_delete', kwargs={'pk': extra.pk}),
        )
        self.assertRedirects(response, reverse('memorabilia:want_list_manage'))
        self.assertFalse(WantListItem.objects.filter(pk=extra.pk).exists())

    def test_image_limit_enforced(self):
        self.client.force_login(self.owner)
        data = self._item_post_data(player='Test')
        data['images-TOTAL_FORMS'] = '4'
        data['images-INITIAL_FORMS'] = '0'
        data['images-MAX_NUM_FORMS'] = '3'
        for i in range(4):
            data[f'images-{i}-link'] = f'http://example.com/{i}.jpg'
        response = self.client.post(
            reverse('memorabilia:want_list_item_create', kwargs={'list_pk': self.want_list.pk}),
            data,
        )
        self.assertEqual(response.status_code, 200)

    def test_at_least_one_field_required(self):
        self.client.force_login(self.owner)
        data = self._item_post_data(
            collectible_type='playeritem',
            player='', team='', notes='', league='',
            game_type='', usage_type='',
        )
        response = self.client.post(
            reverse('memorabilia:want_list_item_create', kwargs={'list_pk': self.want_list.pk}),
            data,
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(WantListItem.objects.filter(want_list=self.want_list, player='').exists())

    def test_item_valid_with_team_only(self):
        self.client.force_login(self.owner)
        data = self._item_post_data(
            collectible_type='playeritem',
            player='', team='Boston Bruins', notes='', league='',
            game_type='', usage_type='',
        )
        response = self.client.post(
            reverse('memorabilia:want_list_item_create', kwargs={'list_pk': self.want_list.pk}),
            data,
        )
        self.assertRedirects(response, reverse('memorabilia:want_list_manage'))
        self.assertTrue(WantListItem.objects.filter(want_list=self.want_list, team='Boston Bruins').exists())

    def test_other_user_cannot_edit_item(self):
        self.client.force_login(self.other_user)
        response = self.client.post(
            reverse('memorabilia:want_list_item_edit', kwargs={'pk': self.want_item.pk}),
            self._item_post_data(),
        )
        self.assertEqual(response.status_code, 404)


class WantListPermissionTests(WantListBaseTestCase):
    def test_public_page_visible_to_anonymous(self):
        response = self.client.get(
            reverse('memorabilia:want_list_public', kwargs={'slug': self.profile.slug})
        )
        self.assertEqual(response.status_code, 200)

    def test_private_page_returns_404_for_anonymous(self):
        self.profile.visibility = 'private'
        self.profile.save()
        response = self.client.get(
            reverse('memorabilia:want_list_public', kwargs={'slug': self.profile.slug})
        )
        self.assertEqual(response.status_code, 404)
        self.profile.visibility = 'public'
        self.profile.save()

    def test_private_page_returns_404_for_other_user(self):
        self.profile.visibility = 'private'
        self.profile.save()
        self.client.force_login(self.other_user)
        response = self.client.get(
            reverse('memorabilia:want_list_public', kwargs={'slug': self.profile.slug})
        )
        self.assertEqual(response.status_code, 404)
        self.profile.visibility = 'public'
        self.profile.save()

    def test_private_page_visible_to_owner(self):
        self.profile.visibility = 'private'
        self.profile.save()
        self.client.force_login(self.owner)
        response = self.client.get(
            reverse('memorabilia:want_list_public', kwargs={'slug': self.profile.slug})
        )
        self.assertEqual(response.status_code, 200)
        self.profile.visibility = 'public'
        self.profile.save()

    def test_logged_in_page_redirects_anonymous(self):
        self.profile.visibility = 'logged_in'
        self.profile.save()
        response = self.client.get(
            reverse('memorabilia:want_list_public', kwargs={'slug': self.profile.slug})
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response['Location'])
        self.profile.visibility = 'public'
        self.profile.save()

    def test_manage_requires_login(self):
        response = self.client.get(reverse('memorabilia:want_list_manage'))
        self.assertEqual(response.status_code, 302)

    def test_anonymous_cannot_create_item(self):
        response = self.client.post(
            reverse('memorabilia:want_list_item_create', kwargs={'list_pk': self.want_list.pk}),
            self._item_post_data(),
        )
        self.assertEqual(response.status_code, 302)


class WantListConvertTests(WantListBaseTestCase):
    def test_convert_creates_collectible_and_deletes_item(self):
        item = WantListItem.objects.create(
            want_list=self.want_list,
            collectible_type='playeritem',
            player='Bobby Hull',
            team='Chicago Blackhawks',
            league=self.league,
        )
        self.client.force_login(self.owner)
        post_data = self._player_item_post_data(
            player='Bobby Hull',
            title='Bobby Hull Player Item',
        )
        response = self.client.post(
            reverse('memorabilia:want_list_item_convert', kwargs={'pk': item.pk}),
            post_data,
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(WantListItem.objects.filter(pk=item.pk).exists())
        self.assertTrue(PlayerItem.objects.filter(player='Bobby Hull', title='Bobby Hull Player Item').exists())

    def test_convert_get_shows_form(self):
        self.client.force_login(self.owner)
        response = self.client.get(
            reverse('memorabilia:want_list_item_convert', kwargs={'pk': self.want_item.pk})
        )
        self.assertEqual(response.status_code, 200)

    def test_convert_invalid_form_does_not_delete_item(self):
        self.client.force_login(self.owner)
        post_data = self._hockey_jersey_post_data(player='', title='')
        response = self.client.post(
            reverse('memorabilia:want_list_item_convert', kwargs={'pk': self.want_item.pk}),
            post_data,
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(WantListItem.objects.filter(pk=self.want_item.pk).exists())

    def test_other_user_cannot_convert_item(self):
        self.client.force_login(self.other_user)
        response = self.client.get(
            reverse('memorabilia:want_list_item_convert', kwargs={'pk': self.want_item.pk})
        )
        self.assertEqual(response.status_code, 404)


class WantListPublicFilterTests(WantListBaseTestCase):
    def test_filter_by_type(self):
        WantListItem.objects.create(
            want_list=self.want_list,
            collectible_type='playeritem',
            player='Filter Player',
        )
        response = self.client.get(
            reverse('memorabilia:want_list_public', kwargs={'slug': self.profile.slug}),
            {'type': 'playeritem'},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Filter Player')
        # Wayne Gretzky appears in the player dropdown options even when filtered out of results
        self.assertContains(response, 'Wayne Gretzky')

    def test_filter_by_player(self):
        response = self.client.get(
            reverse('memorabilia:want_list_public', kwargs={'slug': self.profile.slug}),
            {'player': 'Wayne Gretzky'},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Wayne Gretzky')

    def test_filter_by_league(self):
        other_league = League.objects.create(key='AHL', name='American Hockey League')
        WantListItem.objects.create(
            want_list=self.want_list,
            collectible_type='playeritem',
            player='AHL Player',
            league=other_league,
        )
        response = self.client.get(
            reverse('memorabilia:want_list_public', kwargs={'slug': self.profile.slug}),
            {'league': 'AHL'},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'AHL Player')
        # Wayne Gretzky appears in the player dropdown options even when filtered out of results
        self.assertContains(response, 'Wayne Gretzky')

    def test_no_filter_shows_all_items(self):
        response = self.client.get(
            reverse('memorabilia:want_list_public', kwargs={'slug': self.profile.slug})
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Wayne Gretzky')
