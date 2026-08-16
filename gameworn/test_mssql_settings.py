import os

from .base_settings import *

# MSSQL connection for CI/local parity testing (see .github/workflows/test-mssql.yml
# and artifacts/plan_testing_strategy.md, Recommendation 2). Defaults match that
# workflow's service-container config, and also match what a local
# `docker run -e ACCEPT_EULA=Y -e MSSQL_SA_PASSWORD=GamewornTestCI!1 -p 1433:1433
# mcr.microsoft.com/mssql/server:2022-latest` produces, so this module needs no
# extra env vars in either environment -- only override via env vars for a
# different local setup.
#
# Uses SQL auth (not settings.py's Authentication=ActiveDirectoryMsi -- that
# extra_param only authenticates against real Azure AD, which a CI/local
# container has no access to). TrustServerCertificate=yes is required because
# the container's self-signed cert isn't in a chain ODBC Driver 18 trusts by
# default.
DATABASES = {
    "default": {
        "ENGINE": "mssql",
        "HOST": os.environ.get("MSSQL_HOST", "127.0.0.1"),
        "PORT": os.environ.get("MSSQL_PORT", "1433"),
        "NAME": os.environ.get("MSSQL_DATABASE", "gameworn_test"),
        "USER": os.environ.get("MSSQL_USER", "sa"),
        "PASSWORD": os.environ.get("MSSQL_SA_PASSWORD", "GamewornTestCI!1"),
        "OPTIONS": {
            "driver": "ODBC Driver 18 for SQL Server",
            "extra_params": "TrustServerCertificate=yes",
        },
    }
}

# Use a fixed secret key for tests
SECRET_KEY = SECRET_KEY or 'test-secret-key-not-for-production'
