from django.test import TestCase
from django.contrib.auth.models import User
from django.urls import reverse

from .models import Collection, PlayerItem, OtherItem, League, GameType, UsageType


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
            brand='Adidas',
            size='L',
            player='Wayne Gretzky',
            season='1985',
            game_type='REG',
            usage_type='GU',
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
            'brand': 'Adidas',
            'size': 'L',
            'player': 'Test Player',
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
            league='NHL', brand='Adidas', size='L', player='P',
            season='2024', game_type='REG', usage_type='GU',
        )
        response = self.client.post(reverse(
            'memorabilia:delete_collectible',
            args=[self.collection.id, 'playeritem', temp.id],
        ))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(PlayerItem.objects.filter(pk=temp.id).exists())


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

    def test_edit_otheritem_other_user_forbidden(self):
        self.client.force_login(self.other_user)
        response = self.client.get(reverse(
            'memorabilia:edit_collectible',
            args=[self.collection.id, 'otheritem', self.other_item.id],
        ))
        self.assertEqual(response.status_code, 403)
