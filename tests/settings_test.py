# pyright: reportConstantRedefinition=false
# Overrides on top of the real settings; redefining them is the point of this file.
import os

os.environ.setdefault("DJANGO_SECRET_KEY", "test-only")
os.environ.setdefault("DATABASE_URL", "sqlite://:memory:")

from gasprice.config.settings import *  # noqa: F403

DEBUG = False
ALLOWED_HOSTS = ["testserver"]
SECURE_SSL_REDIRECT = False
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.InMemoryStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}
# No collectstatic in tests: whitenoise would only warn about the missing STATIC_ROOT.
MIDDLEWARE = [item for item in MIDDLEWARE if not item.startswith("whitenoise")]  # noqa: F405
