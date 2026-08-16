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

class SecuritySettingsTests(TestCase):
    """Smoke tests that verify security-critical settings are wired correctly."""

    def test_axes_backend_is_first_in_authentication_backends(self):
        from django.conf import settings
        backends = settings.AUTHENTICATION_BACKENDS
        self.assertTrue(
            len(backends) > 0,
            "AUTHENTICATION_BACKENDS must not be empty"
        )
        self.assertEqual(
            backends[0],
            'axes.backends.AxesStandaloneBackend',
            f"AxesStandaloneBackend must be first in AUTHENTICATION_BACKENDS, got: {backends[0]}"
        )

    def test_axes_failure_limit_configured(self):
        from django.conf import settings
        self.assertTrue(
            hasattr(settings, 'AXES_FAILURE_LIMIT'),
            "AXES_FAILURE_LIMIT must be set"
        )
        self.assertGreater(settings.AXES_FAILURE_LIMIT, 0)

    def test_axes_cooloff_time_configured(self):
        from datetime import timedelta
        from django.conf import settings
        self.assertTrue(
            hasattr(settings, 'AXES_COOLOFF_TIME'),
            "AXES_COOLOFF_TIME must be set"
        )
        self.assertIsInstance(settings.AXES_COOLOFF_TIME, timedelta)
        # Must be a positive cooloff
        self.assertGreater(settings.AXES_COOLOFF_TIME, timedelta(0))

    def test_axes_reset_on_success_is_true(self):
        from django.conf import settings
        self.assertTrue(
            getattr(settings, 'AXES_RESET_ON_SUCCESS', False),
            "AXES_RESET_ON_SUCCESS must be True so successful logins clear lockout counters"
        )

    def test_axes_middleware_present(self):
        from django.conf import settings
        self.assertIn(
            'axes.middleware.AxesMiddleware',
            settings.MIDDLEWARE,
            "axes.middleware.AxesMiddleware must be in MIDDLEWARE"
        )

    def test_axes_in_installed_apps(self):
        from django.conf import settings
        self.assertIn(
            'axes',
            settings.INSTALLED_APPS,
            "'axes' must be in INSTALLED_APPS"
        )
