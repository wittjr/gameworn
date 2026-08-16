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

class MarketplaceViewTests(BaseTestCase):
    def test_marketplace_lists_for_sale_and_trade_items(self):
        self.player_item.for_sale = True
        self.player_item.save()
        self.general_item.for_trade = True
        self.general_item.save()

        response = self.client.get(reverse('memorabilia:marketplace'))
        self.assertEqual(response.status_code, 200)
        titles = [c.title for c in response.context['results']]
        self.assertIn(self.player_item.title, titles)
        self.assertIn(self.general_item.title, titles)

    def test_marketplace_excludes_items_not_for_sale_or_trade(self):
        response = self.client.get(reverse('memorabilia:marketplace'))
        self.assertEqual(response.status_code, 200)
        # No fixture item is flagged, so nothing should be listed.
        self.assertEqual(list(response.context['results']), [])

    def test_marketplace_show_sale_filter(self):
        self.player_item.for_sale = True
        self.player_item.save()
        self.general_item.for_trade = True
        self.general_item.save()

        response = self.client.get(reverse('memorabilia:marketplace'), {'show': 'sale'})
        self.assertEqual(response.status_code, 200)
        titles = [c.title for c in response.context['results']]
        self.assertIn(self.player_item.title, titles)
        self.assertNotIn(self.general_item.title, titles)

    def test_marketplace_show_trade_filter(self):
        self.player_item.for_sale = True
        self.player_item.save()
        self.general_item.for_trade = True
        self.general_item.save()

        response = self.client.get(reverse('memorabilia:marketplace'), {'show': 'trade'})
        self.assertEqual(response.status_code, 200)
        titles = [c.title for c in response.context['results']]
        self.assertIn(self.general_item.title, titles)
        self.assertNotIn(self.player_item.title, titles)

    def test_marketplace_public_no_login_required(self):
        self.player_item.for_sale = True
        self.player_item.save()
        response = self.client.get(reverse('memorabilia:marketplace'))
        self.assertEqual(response.status_code, 200)

    def test_marketplace_text_filter(self):
        self.player_item.for_sale = True
        self.player_item.save()
        self.general_item.for_sale = True
        self.general_item.save()
        response = self.client.get(reverse('memorabilia:marketplace'), {'query': 'Puck'})
        titles = [c.title for c in response.context['results']]
        self.assertIn(self.general_item.title, titles)
        self.assertNotIn(self.player_item.title, titles)

    def test_marketplace_item_type_filter(self):
        self.player_item.for_sale = True
        self.player_item.save()
        self.player_gear.for_sale = True
        self.player_gear.save()
        response = self.client.get(reverse('memorabilia:marketplace'), {'item_type': 'playeritem'})
        titles = [c.title for c in response.context['results']]
        self.assertIn(self.player_item.title, titles)
        self.assertNotIn(self.player_gear.title, titles)

    def test_marketplace_game_type_filter_excludes_non_gear(self):
        self.player_gear.for_sale = True
        self.player_gear.save()
        self.general_item.for_sale = True
        self.general_item.save()
        response = self.client.get(reverse('memorabilia:marketplace'), {'game_type': self.game_type.key})
        titles = [c.title for c in response.context['results']]
        self.assertIn(self.player_gear.title, titles)
        self.assertNotIn(self.general_item.title, titles)

    def test_marketplace_league_filter_excludes_general_items(self):
        self.player_item.for_sale = True
        self.player_item.save()
        self.general_item.for_sale = True
        self.general_item.save()
        response = self.client.get(reverse('memorabilia:marketplace'), {'league': 'NHL'})
        titles = [c.title for c in response.context['results']]
        self.assertIn(self.player_item.title, titles)
        self.assertNotIn(self.general_item.title, titles)
