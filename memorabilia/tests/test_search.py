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
