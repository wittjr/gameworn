"""Browser-driven regression coverage for the focus-trap behavior added in
issue #123 (gallery lightbox + delete-confirmation modal). Uses Playwright
against a real Django LiveServer since none of this behavior is exercised by
the app's JavaScript-free Django TestCase suite.

Requires `pip install -r requirements-e2e.txt && python -m playwright install
chromium`. Excluded from the default `make test` run (tagged 'e2e'); run via
`make test-e2e`. If playwright isn't installed, the whole class is skipped
with a clear reason rather than raising an ImportError at test-discovery time.
"""
import unittest

try:
    from playwright.sync_api import sync_playwright, expect
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

from django.contrib.auth import BACKEND_SESSION_KEY, HASH_SESSION_KEY, SESSION_KEY
from django.contrib.auth.models import User
from django.contrib.sessions.backends.db import SessionStore
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import tag
from django.urls import reverse

from ..models import Collection, GameType, GearType, HockeyJersey, PlayerGearImage, UsageType


@tag('e2e')
class FocusManagementE2ETests(StaticLiveServerTestCase):
    @classmethod
    def setUpClass(cls):
        if not PLAYWRIGHT_AVAILABLE:
            raise unittest.SkipTest(
                'playwright not installed - pip install -r requirements-e2e.txt '
                '&& python -m playwright install chromium'
            )
        super().setUpClass()
        cls.playwright = sync_playwright().start()
        cls.browser = cls.playwright.chromium.launch()

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()
        super().tearDownClass()

    def setUp(self):
        super().setUp()
        self.owner = User.objects.create_user(username='owner', password='testpass')
        self.collection = Collection.objects.create(owner_uid=self.owner.id, title='E2E Collection')
        game_type = GameType.objects.create(key='REG', name='Regular Season')
        usage_type = UsageType.objects.create(key='GU', name='Game Used')
        GearType.objects.get_or_create(key='JRS', defaults={'name': 'Jersey'})
        self.jersey = HockeyJersey.objects.create(
            title='E2E Jersey',
            collection=self.collection,
            league='NHL',
            player='Test Player',
            brand='CCM',
            size='54',
            season='2024',
            game_type=game_type,
            usage_type=usage_type,
        )
        # Two images so the lightbox renders prev/next buttons too, exercising
        # the full Tab-trap boundary (three focusable elements, not just one).
        PlayerGearImage.objects.create(collectible=self.jersey, primary=True, link='https://example.com/one.jpg')
        PlayerGearImage.objects.create(collectible=self.jersey, primary=False, link='https://example.com/two.jpg')

        self.detail_url = self.live_server_url + reverse(
            'memorabilia:collectible',
            kwargs={'collection_id': self.collection.pk, 'collectible_type': 'hockeyjersey', 'pk': self.jersey.pk},
        )

        self.context = self.browser.new_context()
        self.page = self.context.new_page()

    def tearDown(self):
        self.context.close()
        super().tearDown()

    def _login_as_owner(self):
        """Authenticate the browser context as self.owner without a login UI.

        The app is SOCIALACCOUNT_ONLY (Discord/Facebook OAuth only, no
        password login), so there's no form to drive here. Build a real
        Django session server-side and hand its cookie to the browser instead
        - the same mechanism Django's own session middleware uses to
        recognize a logged-in request.
        """
        session = SessionStore()
        session[SESSION_KEY] = str(self.owner.pk)
        session[BACKEND_SESSION_KEY] = 'django.contrib.auth.backends.ModelBackend'
        session[HASH_SESSION_KEY] = self.owner.get_session_auth_hash()
        session.save()
        self.context.add_cookies([{
            'name': 'sessionid',
            'value': session.session_key,
            'url': self.live_server_url,
        }])

    def test_lightbox_focus_trap_and_restore(self):
        self.page.goto(self.detail_url)

        thumb = self.page.locator('.gallery-thumb').first
        close_btn = self.page.locator('#gallery-close')
        prev_btn = self.page.locator('#gallery-prev')
        next_btn = self.page.locator('#gallery-next')

        # Enter on a focused thumbnail opens the lightbox (button semantics:
        # Enter fires the same click handler as a mouse click).
        thumb.focus()
        thumb.press('Enter')
        expect(self.page.locator('#gallery-lightbox')).to_be_visible()
        expect(close_btn).to_be_focused()

        # Tab from the last focusable element wraps to the first.
        next_btn.focus()
        self.page.keyboard.press('Tab')
        expect(close_btn).to_be_focused()

        # Shift+Tab from the first focusable element wraps to the last.
        self.page.keyboard.press('Shift+Tab')
        expect(next_btn).to_be_focused()

        # A full Tab traversal starting from the close button never leaves
        # the dialog for page content behind the overlay.
        close_btn.focus()
        self.page.keyboard.press('Tab')
        expect(prev_btn).to_be_focused()
        self.page.keyboard.press('Tab')
        expect(next_btn).to_be_focused()
        self.page.keyboard.press('Tab')
        expect(close_btn).to_be_focused()

        # Escape closes the lightbox and returns focus to the thumbnail that
        # opened it.
        self.page.keyboard.press('Escape')
        expect(self.page.locator('#gallery-lightbox')).to_be_hidden()
        expect(thumb).to_be_focused()

    def test_delete_modal_focus_trap_and_restore(self):
        self._login_as_owner()
        self.page.goto(self.detail_url)

        # Scoped by accessible name, not just href*="/delete" - the modal's
        # own "Yes, delete" confirm link shares that same href once opened.
        delete_link = self.page.get_by_role('link', name='Delete Collectible')
        close_btn = self.page.locator('#delete-modal-close')
        confirm_link = self.page.locator('#delete-modal-confirm')
        cancel_btn = self.page.locator('#delete-modal-cancel')

        delete_link.focus()
        delete_link.press('Enter')
        expect(self.page.locator('#delete-confirm-modal')).to_be_visible()
        expect(close_btn).to_be_focused()

        # Tab from the last focusable element wraps to the first.
        cancel_btn.focus()
        self.page.keyboard.press('Tab')
        expect(close_btn).to_be_focused()

        # A full Tab traversal never leaves the dialog for page content
        # behind the overlay.
        self.page.keyboard.press('Tab')
        expect(confirm_link).to_be_focused()
        self.page.keyboard.press('Tab')
        expect(cancel_btn).to_be_focused()

        # Cancel closes the modal and returns focus to the link that opened it.
        cancel_btn.click()
        expect(self.page.locator('#delete-confirm-modal')).to_be_hidden()
        expect(delete_link).to_be_focused()
