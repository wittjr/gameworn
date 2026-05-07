import base64
import ipaddress
import os

from cryptography import x509
from cryptography.hazmat.primitives.asymmetric import padding
from django.conf import settings
from django.http import HttpResponseForbidden


class CloudflareSecretHeaderMiddleware:
    """Rejects requests missing the shared secret Cloudflare injects on every request.

    Set up a Cloudflare Transform Rule to add:
        X-Origin-Secret: <value of CLOUDFLARE_ORIGIN_SECRET>
    to all requests for your zone. Only your zone knows the secret, so this
    proves traffic came through your Cloudflare zone specifically — not just
    Cloudflare's network.

    No-op when CLOUDFLARE_ORIGIN_SECRET is unset, so dev/test are unaffected.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        secret = getattr(settings, 'CLOUDFLARE_ORIGIN_SECRET', '')
        if secret and request.path != '/robots933456.txt' and request.headers.get('X-Origin-Secret') != secret:
            return HttpResponseForbidden()
        return self.get_response(request)


class CloudflareOriginPullMiddleware:
    """Verifies that every request carries a valid Cloudflare Authenticated Origin Pull cert.

    App Service forwards the client cert in X-ARR-ClientCert (base64 DER). We verify
    it was signed by Cloudflare's origin pull CA, proving the request actually came
    from Cloudflare rather than someone who knows a Cloudflare IP range.

    No-op unless CLOUDFLARE_ORIGIN_PULL = True in settings, so dev/test are unaffected.
    Requires: Authenticated Origin Pulls enabled in Cloudflare SSL/TLS → Origin Server,
    clientCertEnabled + clientCertMode='Optional' on the App Service (set in Bicep), and
    cloudflare_origin_pull_ca.pem next to this file.
    """

    _CA_PATH = os.path.join(os.path.dirname(__file__), '..', 'infra', 'cloudflare_origin_pull_ca.pem')
    _cf_ca = None

    def __init__(self, get_response):
        self.get_response = get_response

    def _load_ca(self):
        if CloudflareOriginPullMiddleware._cf_ca is None:
            with open(self._CA_PATH, 'rb') as f:
                CloudflareOriginPullMiddleware._cf_ca = x509.load_pem_x509_certificate(f.read())
        return CloudflareOriginPullMiddleware._cf_ca

    def _verify(self, cert_b64):
        try:
            ca = self._load_ca()
            cert = x509.load_der_x509_certificate(base64.b64decode(cert_b64))
            ca.public_key().verify(
                cert.signature,
                cert.tbs_certificate_bytes,
                padding.PKCS1v15(),
                cert.signature_hash_algorithm,
            )
            return True
        except Exception:
            return False

    def __call__(self, request):
        if not getattr(settings, 'CLOUDFLARE_ORIGIN_PULL', False):
            return self.get_response(request)
        cert_b64 = request.META.get('HTTP_X_ARR_CLIENTCERT')
        if not cert_b64 or not self._verify(cert_b64):
            return HttpResponseForbidden()
        return self.get_response(request)


class AdminIPWhitelistMiddleware:
    """Block access to /admin/ for IPs not in ADMIN_ALLOWED_IPS.

    If ADMIN_ALLOWED_IPS is empty or not set, the middleware is a no-op
    so development environments are unaffected by default.

    Supports exact IPs and CIDR ranges, e.g.:
        ADMIN_ALLOWED_IPS = ['203.0.113.10', '10.0.0.0/24']
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path.startswith('/admin/'):
            allowed = getattr(settings, 'ADMIN_ALLOWED_IPS', [])
            if allowed:
                ip = self._get_client_ip(request)
                if not self._is_allowed(ip, allowed):
                    return HttpResponseForbidden('Access denied.')
        return self.get_response(request)

    def _get_client_ip(self, request):
        forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
        if forwarded:
            return forwarded.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR', '')

    def _is_allowed(self, ip, allowed):
        try:
            addr = ipaddress.ip_address(ip)
        except ValueError:
            return False
        for entry in allowed:
            try:
                if '/' in entry:
                    if addr in ipaddress.ip_network(entry, strict=False):
                        return True
                elif addr == ipaddress.ip_address(entry):
                    return True
            except ValueError:
                continue
        return False
