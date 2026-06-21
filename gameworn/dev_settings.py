from .base_settings import *

INSTALLED_APPS = [
    *INSTALLED_APPS,
    'django_browser_reload',
    'debug_toolbar',
]
MIDDLEWARE = [
    'debug_toolbar.middleware.DebugToolbarMiddleware',
    'django_browser_reload.middleware.BrowserReloadMiddleware',
    *MIDDLEWARE,
]

# In development, print emails to the console instead of sending over SMTP.
# EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
EMAIL_HOST = os.environ.get('EMAIL_HOST')
EMAIL_PORT = os.environ.get('EMAIL_PORT')
# EMAIL_USE_TLS = os.environ.get('EMAIL_USE_TLS')
# EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER')
# EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD')

# Database
# https://docs.djangoproject.com/en/5.0/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

INTERNAL_IPS = [
    '127.0.0.1',
]

# Accept requests from localhost and from a cloudflared quick tunnel
# (make relay-tunnel) so Mailgun inbound webhooks reach the local server.
ALLOWED_HOSTS = ['localhost', '127.0.0.1', '.trycloudflare.com']

TAILWIND_APP_NAME = 'theme'

STATIC_ROOT = BASE_DIR / 'static'

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'level': 'DEBUG',
            'class': 'logging.StreamHandler',
        },
    },
    'loggers': {
        'rules': {
            'handlers': ['console'],
            'level': 'DEBUG',
            'propagate': True,
        },
    },
}

# IPs (or CIDR ranges) allowed to access /admin/. Empty list = no restriction.
ADMIN_ALLOWED_IPS = []
