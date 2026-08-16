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

class ContactOwnerTests(BaseTestCase):
    """Interested parties can message an item owner; the message is relayed by
    email (owner address never exposed) and saved as an OwnerInquiry."""

    def setUp(self):
        # The base owner has no email by default; give them one so they're contactable.
        self.owner.email = 'owner@example.com'
        self.owner.save()
        self.player_item.for_sale = True
        self.player_item.asking_price = 100
        self.player_item.save()

    def _login_buyer(self):
        # Contacting requires login; the interested party is a different user.
        self.client.force_login(self.other_user)

    def _detail_url(self, obj):
        return reverse('memorabilia:collectible', kwargs={
            'collection_id': self.collection.id,
            'collectible_type': obj.collectible_type,
            'pk': obj.id,
        })

    def _contact_url(self, obj):
        return reverse('memorabilia:contact_owner', kwargs={
            'collection_id': self.collection.id,
            'collectible_type': obj.collectible_type,
            'collectible_id': obj.id,
        })

    def _post_data(self, **overrides):
        data = {
            'sender_name': 'Jane Buyer',
            'sender_email': 'jane@example.com',
            'message': 'Is this still available?',
            'website': '',
        }
        data.update(overrides)
        return data

    def test_anonymous_redirected_to_login(self):
        response = self.client.get(self._contact_url(self.player_item))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response.url)

    def test_get_form_when_logged_in(self):
        self._login_buyer()
        response = self.client.get(self._contact_url(self.player_item))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.player_item.title)

    def test_post_relays_to_owner_without_exposing_requester(self):
        self._login_buyer()
        response = self.client.post(self._contact_url(self.player_item), self._post_data())
        self.assertEqual(response.status_code, 302)

        inquiry = OwnerInquiry.objects.get(sender_email='jane@example.com')
        self.assertEqual(inquiry.recipient, self.owner)
        self.assertEqual(inquiry.sender_user, self.other_user)
        self.assertEqual(inquiry.collectible_id, self.player_item.id)
        self.assertEqual(inquiry.item_title, self.player_item.title)
        self.assertTrue(inquiry.token)

        # The first message is stored on the thread and relayed.
        self.assertEqual(inquiry.messages.count(), 1)
        first = inquiry.messages.get()
        self.assertEqual(first.sender_role, InquiryMessage.REQUESTER)
        self.assertEqual(first.body, 'Is this still available?')
        self.assertFalse(first.inbound)
        self.assertTrue(first.email_sent)

        self.assertEqual(len(mail.outbox), 1)
        sent = mail.outbox[0]
        self.assertEqual(sent.to, ['owner@example.com'])
        # Reply-To is the relay mailbox, never the requester's address.
        self.assertNotIn('jane@example.com', sent.reply_to)
        self.assertNotIn('jane@example.com', sent.body)
        self.assertIn('Is this still available?', sent.body)
        self.assertIn(f'[ref:{inquiry.token}]', sent.subject)

    def test_sale_interest_recorded_with_price(self):
        self._login_buyer()
        self.client.post(self._contact_url(self.player_item), self._post_data(interest='sale'))
        inquiry = OwnerInquiry.objects.get(sender_email='jane@example.com')
        self.assertEqual(inquiry.interest, 'sale')
        self.assertEqual(inquiry.item_price, 100)
        self.assertEqual(inquiry.item_currency, 'USD')
        self.assertIn('For sale', mail.outbox[0].body)
        self.assertIn('$100.00 USD', mail.outbox[0].body)

    def test_sale_interest_snapshots_item_currency(self):
        self.player_item.currency = 'CAD'
        self.player_item.save()
        self._login_buyer()
        self.client.post(self._contact_url(self.player_item), self._post_data(interest='sale'))
        inquiry = OwnerInquiry.objects.get(sender_email='jane@example.com')
        self.assertEqual(inquiry.item_currency, 'CAD')
        self.assertIn('$100.00 CAD', mail.outbox[0].body)

    def test_trade_interest_recorded_without_price(self):
        self.player_item.for_sale = False
        self.player_item.for_trade = True
        self.player_item.save()
        self._login_buyer()
        self.client.post(self._contact_url(self.player_item), self._post_data(interest='trade'))
        inquiry = OwnerInquiry.objects.get(sender_email='jane@example.com')
        self.assertEqual(inquiry.interest, 'trade')
        self.assertIsNone(inquiry.item_price)
        self.assertIn('For trade', mail.outbox[0].body)
        self.assertNotIn('$', mail.outbox[0].body)

    def test_interest_defaults_to_sole_listing(self):
        # Item is only for sale; no interest param supplied -> inferred as sale.
        self._login_buyer()
        self.client.post(self._contact_url(self.player_item), self._post_data())
        inquiry = OwnerInquiry.objects.get(sender_email='jane@example.com')
        self.assertEqual(inquiry.interest, 'sale')

    def _make_inquiry(self):
        self._login_buyer()
        self.client.post(self._contact_url(self.player_item), self._post_data())
        inquiry = OwnerInquiry.objects.get(sender_email='jane@example.com')
        mail.outbox.clear()
        return inquiry

    def test_owner_reply_relayed_to_requester(self):
        inquiry = self._make_inquiry()
        msg = ingest_inbound(inquiry.token, 'owner@example.com',
                             'Yes, still available.\n\n> On ... jane wrote:\n> hi')
        self.assertIsNotNone(msg)
        self.assertEqual(msg.sender_role, InquiryMessage.OWNER)
        self.assertTrue(msg.inbound)
        # Quoted history is trimmed.
        self.assertEqual(msg.body, 'Yes, still available.')

        self.assertEqual(len(mail.outbox), 1)
        sent = mail.outbox[0]
        self.assertEqual(sent.to, ['jane@example.com'])
        self.assertNotIn('owner@example.com', sent.body)
        self.assertNotIn('owner@example.com', sent.reply_to)
        self.assertIn('Yes, still available.', sent.body)

    def test_requester_reply_relayed_to_owner(self):
        inquiry = self._make_inquiry()
        msg = ingest_inbound(inquiry.token, 'jane@example.com', "Great, I'll take it!")
        self.assertIsNotNone(msg)
        self.assertEqual(msg.sender_role, InquiryMessage.REQUESTER)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['owner@example.com'])

    def test_reply_subject_is_preserved(self):
        inquiry = self._make_inquiry()
        reply_subject = f'Re: Interest in "X" [ref:{inquiry.token}]'
        ingest_inbound(inquiry.token, 'owner@example.com', 'Still available.',
                       subject=reply_subject)
        self.assertEqual(mail.outbox[0].subject, reply_subject)

    def test_reply_without_subject_uses_canonical(self):
        inquiry = self._make_inquiry()
        ingest_inbound(inquiry.token, 'owner@example.com', 'Still available.')
        sent_subject = mail.outbox[0].subject
        self.assertTrue(sent_subject.startswith('Interest in'))
        self.assertIn(f'[ref:{inquiry.token}]', sent_subject)

    def test_relayed_reply_includes_anonymized_thread_history(self):
        inquiry = self._make_inquiry()
        # Owner replies, then requester replies -> the requester's relayed reply
        # should carry the earlier messages as quoted context.
        ingest_inbound(inquiry.token, 'owner@example.com', 'Yes, still available.')
        mail.outbox.clear()
        ingest_inbound(inquiry.token, 'jane@example.com', "Great, I'll take it.")

        sent = mail.outbox[0]
        self.assertEqual(sent.to, ['owner@example.com'])
        self.assertIn("Great, I'll take it.", sent.body)
        # earlier messages are quoted from our records...
        self.assertIn('Earlier in this conversation', sent.body)
        self.assertIn('Yes, still available.', sent.body)
        # ...with no real email address leaked into the history.
        self.assertNotIn('jane@example.com', sent.body)
        self.assertNotIn('owner@example.com', sent.body)

    def test_unknown_sender_is_ignored(self):
        inquiry = self._make_inquiry()
        msg = ingest_inbound(inquiry.token, 'stranger@example.com', 'let me in')
        self.assertIsNone(msg)
        self.assertEqual(inquiry.messages.count(), 1)  # only the original
        self.assertEqual(len(mail.outbox), 0)

    def test_unknown_token_is_ignored(self):
        self._make_inquiry()
        self.assertIsNone(ingest_inbound('deadbeef', 'owner@example.com', 'hi'))
        self.assertEqual(len(mail.outbox), 0)

    def test_token_and_quote_helpers(self):
        self.assertEqual(extract_token('Re: interest in "X" [ref:abc123]'), 'abc123')
        self.assertIsNone(extract_token('no token here'))
        self.assertEqual(strip_quoted_reply('Hello\n> quoted\n> more'), 'Hello')

    def test_honeypot_drops_message_silently(self):
        self._login_buyer()
        response = self.client.post(
            self._contact_url(self.player_item),
            self._post_data(website='http://spam.example'),
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(OwnerInquiry.objects.exists())
        self.assertEqual(len(mail.outbox), 0)

    def test_404_when_item_not_listed(self):
        self._login_buyer()
        self.player_item.for_sale = False
        self.player_item.for_trade = False
        self.player_item.save()
        response = self.client.get(self._contact_url(self.player_item))
        self.assertEqual(response.status_code, 404)

    def test_404_when_owner_has_no_email(self):
        self._login_buyer()
        self.owner.email = ''
        self.owner.save()
        response = self.client.get(self._contact_url(self.player_item))
        self.assertEqual(response.status_code, 404)

    def test_invalid_email_redisplays_form(self):
        self._login_buyer()
        response = self.client.post(
            self._contact_url(self.player_item),
            self._post_data(sender_email='not-an-email'),
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(OwnerInquiry.objects.exists())
        self.assertEqual(len(mail.outbox), 0)

    def test_detail_shows_contact_link_when_logged_in(self):
        self._login_buyer()
        response = self.client.get(self._detail_url(self.player_item))
        self.assertTrue(response.context['owner_can_contact'])
        self.assertContains(response, 'Contact owner')

    def test_detail_shows_login_link_when_anonymous(self):
        response = self.client.get(self._detail_url(self.player_item))
        self.assertContains(response, 'Login to contact owner')

class RelayModuleTests(BaseTestCase):
    """Direct unit tests for memorabilia.relay's own functions, called without
    going through the contact_owner view or the ingest_inbound webhook path.
    ContactOwnerTests and MailgunInboundWebhookTests already cover this
    behavior at the integration level; these isolate the module logic itself,
    including branches (like relay_message's no-destination-address path)
    that the view layer guards against and so never reaches in practice."""

    def setUp(self):
        self.owner.email = 'owner@example.com'
        self.owner.save()
        self.inquiry = OwnerInquiry.objects.create(
            recipient=self.owner,
            sender_user=self.other_user,
            collection_id=self.collection.id,
            collectible_type=self.player_item.collectible_type,
            collectible_id=self.player_item.id,
            item_title=self.player_item.title,
            item_url='https://example.com/item',
            sender_name='Jane Buyer',
            sender_email='jane@example.com',
        )

    def test_extract_token_malformed_or_truncated(self):
        # Truncated: no closing bracket.
        self.assertIsNone(extract_token('Re: interest in "X" [ref:abc123'))
        # Invalid character breaks the alnum-only token match.
        self.assertIsNone(extract_token('Re: interest in "X" [ref:abc-123]'))
        # Empty token.
        self.assertIsNone(extract_token('Re: interest in "X" [ref:]'))

    def test_relay_message_requester_to_owner(self):
        message = InquiryMessage.objects.create(
            inquiry=self.inquiry,
            sender_role=InquiryMessage.REQUESTER,
            body='Is this still available?',
        )
        sent = relay_message(message)
        self.assertTrue(sent)
        self.assertTrue(message.email_sent)
        self.assertEqual(len(mail.outbox), 1)
        email = mail.outbox[0]
        self.assertEqual(email.to, ['owner@example.com'])
        self.assertEqual(email.reply_to, [relay_address()])
        self.assertIn('Jane Buyer', email.from_email)
        self.assertNotIn('jane@example.com', email.from_email)

    def test_relay_message_owner_to_requester(self):
        message = InquiryMessage.objects.create(
            inquiry=self.inquiry,
            sender_role=InquiryMessage.OWNER,
            body='Yes, still available.',
        )
        sent = relay_message(message)
        self.assertTrue(sent)
        self.assertEqual(len(mail.outbox), 1)
        email = mail.outbox[0]
        self.assertEqual(email.to, ['jane@example.com'])
        self.assertEqual(email.reply_to, [relay_address()])
        self.assertNotIn('owner@example.com', email.from_email)

    def test_relay_message_no_destination_address_fails_closed(self):
        # Requester -> owner has nowhere to go when the owner has no email on
        # file. The contact_owner view guards against this case (404s before
        # a message can be created), so this branch is only reachable by
        # calling relay_message directly.
        self.owner.email = ''
        self.owner.save()
        message = InquiryMessage.objects.create(
            inquiry=self.inquiry,
            sender_role=InquiryMessage.REQUESTER,
            body='Is this still available?',
        )
        sent = relay_message(message)
        self.assertFalse(sent)
        message.refresh_from_db()
        self.assertFalse(message.email_sent)
        self.assertEqual(len(mail.outbox), 0)


@override_settings(ANYMAIL={'MAILGUN_WEBHOOK_SIGNING_KEY': 'test-signing-key'})

class MailgunInboundWebhookTests(BaseTestCase):
    """The Mailgun inbound Route webhook verifies the signature, then relays."""

    def setUp(self):
        self.owner.email = 'owner@example.com'
        self.owner.save()
        self.player_item.for_sale = True
        self.player_item.save()
        self.inquiry = OwnerInquiry.objects.create(
            recipient=self.owner,
            sender_user=self.other_user,
            collection_id=self.collection.id,
            collectible_type=self.player_item.collectible_type,
            collectible_id=self.player_item.id,
            item_title=self.player_item.title,
            item_url='https://example.com/item',
            sender_name='Jane Buyer',
            sender_email='jane@example.com',
        )
        self.url = reverse('memorabilia:mailgun_inbound')

    def _signed(self, **fields):
        timestamp, token = '1700000000', 'nonce123'
        signature = hmac.new(
            b'test-signing-key',
            f'{timestamp}{token}'.encode(),
            hashlib.sha256,
        ).hexdigest()
        data = {'timestamp': timestamp, 'token': token, 'signature': signature}
        data.update(fields)
        return data

    def test_valid_owner_reply_is_relayed(self):
        resp = self.client.post(self.url, self._signed(
            sender='owner@example.com',
            subject=f'Re: interest in "X" [ref:{self.inquiry.token}]',
            **{'stripped-text': 'Yes, still available.'},
        ))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(self.inquiry.messages.count(), 1)
        msg = self.inquiry.messages.get()
        self.assertEqual(msg.sender_role, InquiryMessage.OWNER)
        self.assertTrue(msg.inbound)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['jane@example.com'])

    def test_bad_signature_rejected(self):
        data = self._signed(
            sender='owner@example.com',
            subject=f'Re: [ref:{self.inquiry.token}]',
            **{'stripped-text': 'hi'},
        )
        data['signature'] = 'deadbeef'
        resp = self.client.post(self.url, data)
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(self.inquiry.messages.count(), 0)
        self.assertEqual(len(mail.outbox), 0)

    def test_unknown_token_accepted_but_dropped(self):
        resp = self.client.post(self.url, self._signed(
            sender='owner@example.com',
            subject='Re: something [ref:nosuchtoken]',
            **{'stripped-text': 'hi'},
        ))
        # 200 so Mailgun stops retrying; nothing relayed.
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(mail.outbox), 0)

    def test_get_not_allowed(self):
        self.assertEqual(self.client.get(self.url).status_code, 405)
