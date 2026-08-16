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
