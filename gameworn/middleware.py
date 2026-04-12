import ipaddress

from django.conf import settings
from django.http import HttpResponseForbidden


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
