from .base_settings import *

INSTALLED_APPS = [
    *INSTALLED_APPS,
    'tailwind',
    'django_browser_reload',
    'debug_toolbar',
]
MIDDLEWARE = [
    'debug_toolbar.middleware.DebugToolbarMiddleware',
    *MIDDLEWARE,
]

# EMAIL_BACKEND = os.environ.get('EMAIL_BACKEND')
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

TAILWIND_APP_NAME = 'theme'
