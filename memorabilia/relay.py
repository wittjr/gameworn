"""Anonymized email relay for OwnerInquiry threads.

Neither party ever learns the other's email address. Outbound messages are sent
from the site's relay mailbox with the thread token embedded in the subject as
``[ref:<token>]``. When a party replies to that email, an inbound handler (an
IMAP poller, a provider webhook, or an MTA pipe) extracts the token + sender and
calls :func:`ingest_inbound`, which relays the reply on to the other party.
"""
import hashlib
import hmac
import logging
import re

from django.conf import settings
from django.core.mail import EmailMessage
from django.utils.html import strip_tags
from email.utils import formataddr

from .models import OwnerInquiry, InquiryMessage

logger = logging.getLogger(__name__)

_TOKEN_RE = re.compile(r'\[ref:([0-9a-zA-Z]+)\]')


def verify_mailgun_signature(timestamp, token, signature):
    """Verify a Mailgun webhook signature (HMAC-SHA256 of ``timestamp+token``
    with the configured signing key). Fails closed if anything is missing."""
    signing_key = (getattr(settings, 'ANYMAIL', {}) or {}).get('MAILGUN_WEBHOOK_SIGNING_KEY', '')
    if not (signing_key and timestamp and token and signature):
        return False
    expected = hmac.new(
        signing_key.encode('utf-8'),
        f'{timestamp}{token}'.encode('utf-8'),
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


def relay_address():
    """Mailbox that relayed mail is sent from / replied to."""
    return getattr(settings, 'INQUIRY_RELAY_EMAIL', None) or settings.DEFAULT_FROM_EMAIL


def extract_token(subject):
    """Pull the thread token out of an email subject, or None."""
    if not subject:
        return None
    match = _TOKEN_RE.search(subject)
    return match.group(1) if match else None


# Lines that typically mark the start of quoted text in a reply.
_QUOTE_MARKERS = (
    re.compile(r'^On .+ wrote:\s*$'),
    re.compile(r'^-{2,}\s*Original Message\s*-{2,}', re.IGNORECASE),
    re.compile(r'^_{5,}\s*$'),
    re.compile(r'^From:\s', re.IGNORECASE),
)


def strip_quoted_reply(text):
    """Best-effort trim of quoted history from a plain-text email reply."""
    if not text:
        return ''
    lines = text.replace('\r\n', '\n').split('\n')
    kept = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith('>'):
            break
        if any(marker.match(stripped) for marker in _QUOTE_MARKERS):
            break
        kept.append(line)
    return '\n'.join(kept).strip()


def _counterparty_label(inquiry, sender_role):
    """Display name (never an email) for the message author."""
    if sender_role == InquiryMessage.REQUESTER:
        return inquiry.sender_name or 'Interested buyer'
    owner = inquiry.recipient
    if owner:
        return owner.get_full_name() or owner.username
    return 'Item owner'


def _thread_history(inquiry, current_message):
    """Render the earlier messages in the thread as quoted context.

    Sourced from our own stored messages (never the sender's quoted email), so
    only anonymized author labels and already-stripped bodies appear — no real
    email address can leak. Most recent first.
    """
    prior = [m for m in inquiry.messages.all() if m.id != current_message.id]
    if not prior:
        return ''
    blocks = []
    # Deepen the quote level for each older message (most recent = one '>',
    # the one it replied to = '>>', and so on) so it reads like a nested thread.
    for depth, m in enumerate(reversed(prior), start=1):
        prefix = '> ' * depth
        label = _counterparty_label(inquiry, m.sender_role)
        lines = [f'{label} wrote:'] + strip_tags(m.body).split('\n')
        blocks.append('\n'.join(prefix + line for line in lines))
    return '\n'.join(blocks)


def relay_message(message, reply_subject=None):
    """Send a thread message on to whichever party did NOT write it.

    ``reply_subject`` is the subject line from an inbound email reply; when
    given it's forwarded as-is (preserving the sender's "Re:" and the [ref:]
    token, which inbound matching already guaranteed is present). The web-form
    first message has no inbound subject, so it falls back to a canonical one.

    Returns True on success. Sets and saves ``message.email_sent``.
    """
    inquiry = message.inquiry
    site = getattr(settings, 'SITE_NAME', 'the site')

    if message.sender_role == InquiryMessage.REQUESTER:
        # From the requester → goes to the owner.
        owner = inquiry.recipient
        to_email = owner.email if owner else None
    else:
        # From the owner → goes back to the requester.
        to_email = inquiry.sender_email

    if not to_email:
        logger.warning('No destination address for inquiry %s message %s', inquiry.id, message.id)
        message.email_sent = False
        message.save(update_fields=['email_sent'])
        return False

    author = _counterparty_label(inquiry, message.sender_role)
    subject = reply_subject or f'Interest in "{inquiry.item_title}" [ref:{inquiry.token}]'
    body_lines = [
        f'{author} sent a message about "{inquiry.item_title}".',
    ]
    if inquiry.item_url:
        body_lines.append(f'Item: {inquiry.item_url}')
    body_lines += [
        '',
        strip_tags(message.body),
    ]
    history = _thread_history(inquiry, message)
    if history:
        body_lines += ['', '—— Earlier in this conversation ——', '', history]
    body_lines += [
        '',
        '—',
        f'Reply to this email to respond. Your contact details stay private — '
        f'{site} relays messages between you and the other party.',
    ]
    body = '\n'.join(body_lines)

    from_email = formataddr((f'{author} via {site}', settings.DEFAULT_FROM_EMAIL))

    try:
        EmailMessage(
            subject=subject,
            body=body,
            from_email=from_email,
            to=[to_email],
            reply_to=[relay_address()],
        ).send(fail_silently=False)
        message.email_sent = True
    except Exception:
        logger.exception('Failed to relay inquiry %s message %s', inquiry.id, message.id)
        message.email_sent = False
    message.save(update_fields=['email_sent'])
    return message.email_sent


def ingest_inbound(token, from_email, body, subject=None):
    """Route an inbound email reply into its thread and relay it onward.

    ``subject`` is the inbound email's subject; it's forwarded as-is so the
    relayed message keeps the sender's "Re:" and threads as a reply.

    Returns the created :class:`InquiryMessage`, or None if the token is
    unknown or the sender isn't a participant (which is silently ignored so the
    relay can't be used to probe addresses).
    """
    if not token or not from_email:
        return None
    inquiry = OwnerInquiry.objects.filter(token=token).first()
    if inquiry is None:
        return None

    from_email = from_email.strip().lower()
    owner = inquiry.recipient
    owner_email = (owner.email or '').strip().lower() if owner else ''

    if owner_email and from_email == owner_email:
        role = InquiryMessage.OWNER
    elif from_email == inquiry.sender_email.strip().lower():
        role = InquiryMessage.REQUESTER
    else:
        logger.warning('Inbound reply for inquiry %s from unknown sender; ignored', inquiry.id)
        return None

    cleaned = strip_quoted_reply(body)
    if not cleaned:
        return None

    message = InquiryMessage.objects.create(
        inquiry=inquiry,
        sender_role=role,
        body=cleaned[:2000],
        inbound=True,
    )
    relay_message(message, reply_subject=subject)
    return message
