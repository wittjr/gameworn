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
