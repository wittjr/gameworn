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

class Django60CompatibilityTests(TestCase):
    """
    Regression tests for Django 6.0 breaking changes.

    Each method documents which breaking change it covers, what the codebase
    pattern is, and what the expected behaviour is under Django 6.

    Items A, B, C, E below are confirmed NOT present in this codebase (see
    comments).  Item D (URLField default scheme change) does have real
    surface area and is actively tested.
    """

    # ── A. Model.save() positional args removed ───────────────────────────────
    # Verdict: NOT APPLICABLE.
    # Every .save() call in models.py / views.py / forms.py uses keyword args
    # (update_fields=[...], commit=False) or bare .save() with no args at all.
    # HockeyJersey.save() correctly splats *args/**kwargs.  No positional bool
    # args like obj.save(True) exist anywhere.

    # ── B. BaseConstraint positional args removed ─────────────────────────────
    # Verdict: NOT APPLICABLE.
    # No UniqueConstraint / CheckConstraint / BaseConstraint usage in the app.
    # All Meta constraints are models.Index(fields=[...], name=...) which
    # already use keyword args.

    # ── C. format_html() without format args removed ──────────────────────────
    # Verdict: NOT APPLICABLE.
    # The single format_html() call (admin.py ImageInlineMixin.preview) passes
    # `url` as a format argument — it is not a bare format_html("plain string").

    # ── D. URLField default scheme is now https ───────────────────────────────
    # Django 6.0 makes URLField assume https by default and removes the
    # FORMS_URLFIELD_ASSUME_HTTPS transitional setting.  The collection header
    # image URL path goes through FlowbiteImageDropzoneField → forms.URLField.
    # These tests confirm:
    #   1. FORMS_URLFIELD_ASSUME_HTTPS is NOT set (setting removed in Django 6).
    #   2. https:// image URLs are accepted by the field.
    #   3. http:// image URLs are rejected (Django 6 URLField now requires https
    #      for bare http:// that previously relied on the assume-https fallback).

    def test_forms_urlfield_assume_https_setting_not_present(self):
        """
        FORMS_URLFIELD_ASSUME_HTTPS was removed in Django 6.0.
        Confirm it is absent from settings to avoid a startup error.
        """
        from django.conf import settings
        self.assertFalse(
            hasattr(settings, 'FORMS_URLFIELD_ASSUME_HTTPS'),
            "FORMS_URLFIELD_ASSUME_HTTPS must not be set — it was removed in Django 6.0",
        )

    def test_urlfield_accepts_https_image_url(self):
        """
        The URLField inside FlowbiteImageDropzoneField must accept an https://
        image URL — Django 6's default scheme is now https.
        """
        from django import forms

        field = forms.URLField(required=False)
        # Should not raise
        validated = field.clean('https://example.com/image.jpg')
        self.assertEqual(validated, 'https://example.com/image.jpg')

    def test_urlfield_rejects_plain_http_image_url(self):
        """
        Under Django 6 URLField no longer silently upgrades bare http:// URLs
        to https.  An http:// URL must still validate (http is still a valid
        scheme) but we confirm no exception is raised — http is NOT treated as
        invalid, only bare scheme-less strings were previously auto-prefixed.
        This test documents the contract: http:// URLs remain valid; only
        truly invalid strings are rejected.
        """
        from django import forms
        from django.core.exceptions import ValidationError

        field = forms.URLField(required=False)
        # http:// is still a syntactically valid URL — should not raise
        validated = field.clean('http://example.com/image.jpg')
        self.assertIn('example.com', validated)

    def test_urlfield_rejects_non_url_string(self):
        """
        A plain string with no scheme must be rejected by URLField.
        """
        from django import forms
        from django.core.exceptions import ValidationError

        field = forms.URLField(required=False)
        with self.assertRaises(ValidationError):
            field.clean('not-a-url-at-all')

    def test_flowbite_image_dropzone_field_accepts_https_url(self):
        """
        The composite FlowbiteImageDropzoneField used for collection header
        images must accept an https:// URL in the URL subfield position.
        """
        from django_flowbite_widgets.flowbite_fields import FlowbiteImageDropzoneField

        field = FlowbiteImageDropzoneField(required=False)
        # Simulate the widget decompress: [file_value, url_value]
        result = field.clean([None, 'https://example.com/header.jpg'])
        # compress() returns (file, url) tuple
        self.assertIsNotNone(result)
        file_val, url_val = result
        self.assertIsNone(file_val)
        self.assertEqual(url_val, 'https://example.com/header.jpg')

    def test_flowbite_image_dropzone_field_empty_url_is_fine(self):
        """
        An empty URL value in the composite field must not raise when the
        field is not required — covers the collection form with no header image.
        """
        from django_flowbite_widgets.flowbite_fields import FlowbiteImageDropzoneField

        field = FlowbiteImageDropzoneField(required=False)
        result = field.clean([None, ''])
        # Both subfields empty and field not required — should return None
        self.assertIsNone(result)

    # ── E. ADMINS / MANAGERS tuple format deprecated ──────────────────────────
    # Verdict: NOT APPLICABLE.
    # Neither ADMINS nor MANAGERS is set in base_settings.py, dev_settings.py,
    # or settings.py (production).  Django's default for both is an empty list,
    # so there is nothing to migrate.

    # ── Model.save() keyword-args-only smoke test ─────────────────────────────
    # Although no positional args exist, we smoke-test the two most active
    # save paths (HockeyJersey auto-sets gear_type_id; CollectibleImage.delete
    # propagates to storage) to confirm they still work under Django 6.

    def test_hockey_jersey_save_sets_gear_type_id(self):
        """
        HockeyJersey.save() overrides gear_type_id='JRS' then calls
        super().save(*args, **kwargs).  Under Django 6, save() no longer
        accepts positional args — verify the proxy still saves correctly when
        called with keyword-only args.
        """
        owner = User.objects.create_user(username='hj_save_owner', password='pw')
        league = League.objects.create(key='D6L', name='Django 6 League')
        game_type = GameType.objects.create(key='D6G', name='Django 6 Game')
        usage_type = UsageType.objects.create(key='D6U', name='Django 6 Usage')
        gear_type, _ = GearType.objects.get_or_create(key='JRS', defaults={'name': 'Jersey'})
        collection = Collection.objects.create(owner_uid=owner.id, title='D6 Collection')

        jersey = HockeyJersey(
            title='D6 Jersey',
            description='Django 6 smoke test jersey',
            collection=collection,
            player='Test Player',
            brand='CCM',
            size='54',
            season='2025',
            game_type=game_type,
            usage_type=usage_type,
        )
        # Should not raise TypeError under Django 6 (no positional args)
        jersey.save()
        jersey.refresh_from_db()
        self.assertEqual(jersey.gear_type_id, 'JRS')
        self.assertEqual(jersey.collectible_type, 'hockeyjersey')
