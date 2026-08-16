import logging

from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from ..relay import extract_token, ingest_inbound, verify_mailgun_signature

logger = logging.getLogger(__name__)

@csrf_exempt
@require_POST
def mailgun_inbound(request):
    """Webhook target for Mailgun inbound Routes. Mailgun POSTs a parsed reply
    here; we verify its signature, pull the thread token from the subject and
    the sender + body, and relay the message on to the other party."""
    # Mailgun's signature triplet (note: its "token" is a signing nonce, NOT our
    # inquiry token).
    if not verify_mailgun_signature(
        request.POST.get('timestamp', ''),
        request.POST.get('token', ''),
        request.POST.get('signature', ''),
    ):
        logger.warning('Rejected Mailgun inbound webhook: bad signature')
        return HttpResponse('Invalid signature', status=403)

    sender = request.POST.get('sender', '')
    subject = request.POST.get('subject', '')
    # Mailgun pre-strips quoted history into "stripped-text"; fall back to full body.
    body = request.POST.get('stripped-text') or request.POST.get('body-plain', '')

    thread_token = extract_token(subject)
    ingest_inbound(thread_token, sender, body, subject=subject)
    # Always 200 so Mailgun doesn't retry; unroutable mail is simply dropped.
    return HttpResponse(status=200)

