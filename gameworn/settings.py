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

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'error_file': {
            'level': 'ERROR',  # Set to ERROR to capture only error messages
            'class': 'logging.FileHandler',
            'filename': os.environ['LOG_FILE'],  # Specify your error log file path
        },
    },
    'loggers': {
        'django': {
            'handlers': ['error_file'],
            'level': 'ERROR',  # Set to ERROR to ensure only errors are logged
            'propagate': True,
        },
    },
}
