"""Ingest a single inbound email reply and relay it into its inquiry thread.

This is the wiring seam for inbound mail: pipe a raw RFC822 message to stdin
from whatever delivery mechanism you choose later — an MTA alias/pipe, an IMAP
poller, or a provider webhook that hands off the raw message. Example:

    cat reply.eml | python manage.py relay_inbound_email

The command extracts the thread token from the subject ("[ref:<token>]"), the
sender address from the From header, and the plain-text body, then routes it
via memorabilia.relay.ingest_inbound (which verifies the sender is a thread
participant before relaying).
"""
import sys
from email import message_from_bytes
from email.utils import parseaddr

from django.core.management.base import BaseCommand

from memorabilia.relay import extract_token, ingest_inbound


def _plain_text_body(msg):
    """Return the best plain-text body from a parsed email.message.Message."""
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == 'text/plain' and 'attachment' not in str(part.get('Content-Disposition', '')):
                payload = part.get_payload(decode=True)
                if payload:
                    charset = part.get_content_charset() or 'utf-8'
                    return payload.decode(charset, errors='replace')
        return ''
    payload = msg.get_payload(decode=True)
    if payload is None:
        return ''
    charset = msg.get_content_charset() or 'utf-8'
    return payload.decode(charset, errors='replace')


class Command(BaseCommand):
    help = 'Relay one inbound email reply (raw RFC822 on stdin) into its inquiry thread.'

    def handle(self, *args, **options):
        raw = sys.stdin.buffer.read()
        if not raw:
            self.stderr.write('No email data on stdin.')
            return

        msg = message_from_bytes(raw)
        subject = msg.get('Subject', '')
        token = extract_token(subject)
        _, from_email = parseaddr(msg.get('From', ''))
        body = _plain_text_body(msg)

        if not token:
            self.stderr.write('No thread token found in subject; ignoring.')
            return

        message = ingest_inbound(token, from_email, body, subject=subject)
        if message is None:
            self.stderr.write('Reply not relayed (unknown token, sender, or empty body).')
            return

        status = 'relayed' if message.email_sent else 'saved (relay failed)'
        self.stdout.write(self.style.SUCCESS(
            f'Inbound {message.get_sender_role_display()} reply on inquiry '
            f'{message.inquiry_id} {status}.'
        ))
