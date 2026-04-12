from .base_settings import *

# IPs (or CIDR ranges) allowed to access /admin/. Empty list = no restriction.
ADMIN_ALLOWED_IPS = []

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

# Use a fixed secret key for tests
SECRET_KEY = SECRET_KEY or 'test-secret-key-not-for-production'
