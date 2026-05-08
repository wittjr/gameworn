from .base_settings import *
from csp.constants import NONCE

if not SECRET_KEY:
    raise ValueError("DJANGO_SECRET_KEY environment variable is not set")

CLOUDFLARE_ORIGIN_SECRET = os.environ.get('CLOUDFLARE_ORIGIN_SECRET', '')
CLOUDFLARE_ORIGIN_PULL = True

SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SECURE_SSL_REDIRECT = False  # Cloudflare handles HTTP→HTTPS redirect

SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

_storage_account_name = os.environ.get('AZURE_STORAGE_ACCOUNT_NAME', '')
CONTENT_SECURITY_POLICY = {
    "DIRECTIVES": {
        "default-src": ["'self'"],
        "script-src": [
            "'self'",
            "https://cdn.jsdelivr.net",
            "https://www.googletagmanager.com",
            "https://static.cloudflareinsights.com",
            "https://kit.fontawesome.com",
            NONCE,
        ],
        "img-src": list(filter(None, [
            "'self'",
            "data:",
            "https:",
            f"https://{_storage_account_name}.blob.core.windows.net" if _storage_account_name else None,
        ])),
        "style-src": ["'self'", "'unsafe-inline'"],
        "font-src": ["'self'", "https://ka-f.fontawesome.com"],
        "connect-src": [
            "'self'",
            "https://*.google-analytics.com",
            "https://*.googletagmanager.com",
            "https://ka-f.fontawesome.com",
        ],
        "object-src": ["'none'"],
        "base-uri": ["'self'"],
        "form-action": ["'self'"],
        "frame-src": ["https://embed.gettyimages.com"],
        "frame-ancestors": ["'none'"],
    }
}

MIDDLEWARE.insert(
    MIDDLEWARE.index('django.middleware.security.SecurityMiddleware') + 1,
    'whitenoise.middleware.WhiteNoiseMiddleware',
)
MIDDLEWARE.insert(
    MIDDLEWARE.index('django.middleware.security.SecurityMiddleware') + 1,
    'csp.middleware.CSPMiddleware',
)

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

_storage_account = os.environ.get('AZURE_STORAGE_ACCOUNT_NAME', '')

if _storage_account:
    from azure.identity import DefaultAzureCredential
    STORAGES = {
        "default": {
            "BACKEND": "storages.backends.azure_storage.AzureStorage",
            "OPTIONS": {
                "account_name": _storage_account,
                "azure_container": "media",
                "token_credential": DefaultAzureCredential(),
                "overwrite_files": False,
            },
        },
        "staticfiles": {
            "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
        },
    }
    MEDIA_URL = f"https://{_storage_account}.blob.core.windows.net/media/"
else:
    STORAGES = {
        "default": {
            "BACKEND": "django.core.files.storage.FileSystemStorage",
        },
        "staticfiles": {
            "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
        },
    }

# Azure sets WEBSITE_HOSTNAME automatically (e.g. heavyuse.azurewebsites.net).
website_hostname = os.environ.get('WEBSITE_HOSTNAME', '')
if website_hostname:
    ALLOWED_HOSTS.append(website_hostname)

# Database
# https://docs.djangoproject.com/en/5.0/ref/settings/#databases


_developer_ip = os.environ.get('DEVELOPER_IP', '')
ADMIN_ALLOWED_IPS = [_developer_ip] if _developer_ip else []

DATABASES = {
    "default": {
        "ENGINE": "mssql",
        "NAME": os.environ.get("AZURE_SQL_DATABASE"),
        "HOST": os.environ.get("AZURE_SQL_SERVER"),
        "PORT": "1433",
        "CONN_MAX_AGE": 60,
        "OPTIONS": {
            "driver": "ODBC Driver 18 for SQL Server",
            "extra_params": "Authentication=ActiveDirectoryMsi",
        },
    }
}