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
