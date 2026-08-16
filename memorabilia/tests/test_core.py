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

class PublicViewTests(BaseTestCase):
    def test_home_page(self):
        response = self.client.get(reverse('memorabilia:home'))
        self.assertEqual(response.status_code, 200)

    def test_home_recent_fragment(self):
        # The recent-items grid is lazy-loaded from its own endpoint so the
        # home page shell can render without touching the DB.
        response = self.client.get(reverse('memorabilia:home_recent'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'memorabilia/_recent_items.html')

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
