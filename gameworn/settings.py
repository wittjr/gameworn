from .base_settings import *

# Database
# https://docs.djangoproject.com/en/5.0/ref/settings/#databases


# IPs (or CIDR ranges) allowed to access /admin/. Empty list = no restriction.
ADMIN_ALLOWED_IPS = []

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.mysql",
        "OPTIONS": {
            "read_default_file": os.environ.get('DB_CONNECTION_INFO'),
        },
    }
}