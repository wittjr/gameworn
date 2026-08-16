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

class MemorabiliaExtrasTagTests(BaseTestCase):
    """Direct unit tests for memorabilia.templatetags.memorabilia_extras.

    These tags render on nearly every page (cards, collages, avatars) but
    previously had no dedicated coverage -- only whatever incidental exercise
    they got from view tests that happened to render a template using them.
    """

    PNG_1PX = (
        b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01'
        b'\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00'
        b'\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82'
    )

    def _upload(self, name='test.png'):
        return SimpleUploadedFile(name, self.PNG_1PX, content_type='image/png')

    # ── collage_rows ─────────────────────────────────────────────────

    def test_collage_rows_zero_images(self):
        self.assertEqual(collage_rows([]), [])

    def test_collage_rows_one_image(self):
        self.assertEqual(collage_rows([0]), [[0]])

    def test_collage_rows_two_images(self):
        self.assertEqual(collage_rows([0, 1]), [[0, 1]])

    def test_collage_rows_three_images(self):
        self.assertEqual(collage_rows([0, 1, 2]), [[0, 1, 2]])

    def test_collage_rows_four_images(self):
        self.assertEqual(collage_rows([0, 1, 2, 3]), [[0, 1], [2, 3]])

    def test_collage_rows_seven_images(self):
        self.assertEqual(
            collage_rows([0, 1, 2, 3, 4, 5, 6]),
            [[0, 1], [2, 3], [4, 5, 6]],
        )

    # ── getmediaurl ──────────────────────────────────────────────────

    def test_getmediaurl_none_falls_back_to_placeholder(self):
        self.assertEqual(getmediaurl(None, None), static('memorabilia/placeholder.svg'))

    def test_getmediaurl_string_passthrough(self):
        self.assertEqual(
            getmediaurl(None, 'https://example.com/x.jpg'),
            'https://example.com/x.jpg',
        )

    def test_getmediaurl_collectible_image_prefers_link(self):
        record = PlayerItemImage(collectible=self.player_item, link='https://live.staticflickr.com/x.jpg')
        self.assertEqual(getmediaurl(None, record), 'https://live.staticflickr.com/x.jpg')

    @override_settings(MEDIA_ROOT=tempfile.mkdtemp())
    def test_getmediaurl_collectible_image_falls_back_to_uploaded_file(self):
        record = PlayerItemImage.objects.create(collectible=self.player_item, image=self._upload())
        self.assertEqual(getmediaurl(None, record), record.image.url)

    @override_settings(MEDIA_ROOT=tempfile.mkdtemp())
    def test_getmediaurl_raw_imagefieldfile(self):
        # The FileInput -> ImageFieldFile branch (image.image passed directly,
        # not the wrapping model instance).
        record = PlayerItemImage.objects.create(collectible=self.player_item, image=self._upload())
        self.assertEqual(getmediaurl(None, record.image), record.image.url)

    def test_getmediaurl_photomatch_prefers_link(self):
        import datetime
        record = PhotoMatch(
            collectible=self.player_gear,
            link='https://live.staticflickr.com/y.jpg',
            game_date=datetime.date(2024, 1, 1),
        )
        self.assertEqual(getmediaurl(None, record), 'https://live.staticflickr.com/y.jpg')

    def test_getmediaurl_photomatch_falls_back_to_getty_thumbnail(self):
        import datetime
        record = PhotoMatch(
            collectible=self.player_gear,
            getty_thumbnail_url='https://embed.gettyimages.com/thumb.jpg',
            game_date=datetime.date(2024, 1, 1),
        )
        self.assertEqual(getmediaurl(None, record), 'https://embed.gettyimages.com/thumb.jpg')

    def test_getmediaurl_photomatch_with_nothing_falls_back_to_placeholder(self):
        import datetime
        record = PhotoMatch(collectible=self.player_gear, game_date=datetime.date(2024, 1, 1))
        self.assertEqual(getmediaurl(None, record), static('memorabilia/placeholder.svg'))

    # ── get_user_avatar_url ──────────────────────────────────────────

    def test_get_user_avatar_url_for_known_user(self):
        self.owner.email = 'owner@example.com'
        self.owner.save()
        url = get_user_avatar_url('owner@example.com')
        self.assertTrue(url.startswith('https://secure.gravatar.com/avatar/'))

    def test_get_user_avatar_url_for_a_different_user(self):
        self.owner.email = 'owner@example.com'
        self.owner.save()
        self.other_user.email = 'other@example.com'
        self.other_user.save()
        owner_url = get_user_avatar_url('owner@example.com')
        other_url = get_user_avatar_url('other@example.com')
        self.assertTrue(other_url.startswith('https://secure.gravatar.com/avatar/'))
        # Different emails hash to different gravatar URLs.
        self.assertNotEqual(owner_url, other_url)
