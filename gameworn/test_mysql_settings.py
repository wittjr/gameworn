import os

from .base_settings import *

# MySQL connection for CI/local parity testing (see .github/workflows/test-mysql.yml
# and artifacts/plan_testing_strategy.md, Recommendation 2). Defaults match that
# workflow's service-container config, and also match what a local
# `docker run -e MYSQL_ROOT_PASSWORD=root -e MYSQL_DATABASE=gameworn_test
# -p 3306:3306 mysql:8` produces, so this module needs no extra env vars in
# either environment -- only override via env vars for a different local setup.
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.mysql",
        "HOST": os.environ.get("MYSQL_HOST", "127.0.0.1"),
        "PORT": os.environ.get("MYSQL_PORT", "3306"),
        "NAME": os.environ.get("MYSQL_DATABASE", "gameworn_test"),
        "USER": os.environ.get("MYSQL_USER", "root"),
        "PASSWORD": os.environ.get("MYSQL_PASSWORD", "root"),
    }
}

# Use a fixed secret key for tests
SECRET_KEY = SECRET_KEY or 'test-secret-key-not-for-production'
