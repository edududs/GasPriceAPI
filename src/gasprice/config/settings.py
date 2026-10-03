"""Settings come from the environment; see `.env.example`. Debug defaults to off, so a deploy that
forgets a variable fails closed instead of serving debug pages."""

import os
from pathlib import Path

import dj_database_url
from django.core.exceptions import ImproperlyConfigured

PACKAGE_DIR = Path(__file__).resolve().parent.parent
BASE_DIR = PACKAGE_DIR.parent.parent


def env_bool(name: str, *, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def env_list(name: str, default: str = "") -> list[str]:
    return [item.strip() for item in os.environ.get(name, default).split(",") if item.strip()]


DEBUG = env_bool("DJANGO_DEBUG")
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY") or ("dev-only-insecure-key" if DEBUG else "")
if not SECRET_KEY:
    msg = "DJANGO_SECRET_KEY is required when DJANGO_DEBUG is off"
    raise ImproperlyConfigured(msg)

ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1" if DEBUG else "")
CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS")

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.staticfiles",
    "django_htmx",
    "django_tailwind_cli",
    "gasprice.prices.adapters.apps.PricesConfig",
    "gasprice.trips.adapters.apps.TripsConfig",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "django_htmx.middleware.HtmxMiddleware",
]

ROOT_URLCONF = "gasprice.config.urls"
WSGI_APPLICATION = "gasprice.config.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [PACKAGE_DIR / "web" / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
            ],
        },
    },
]


def database_url() -> str:
    """Local default: a SQLite file under ./data, created on first use. Any deploy sets DATABASE_URL."""
    if url := os.environ.get("DATABASE_URL"):
        return url
    (BASE_DIR / "data").mkdir(exist_ok=True)
    return f"sqlite:///{BASE_DIR / 'data' / 'gasprice.sqlite3'}"


DATABASES = {"default": dj_database_url.parse(database_url(), conn_max_age=60)}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LANGUAGE_CODE = "pt-br"
TIME_ZONE = "America/Sao_Paulo"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [PACKAGE_DIR / "web" / "static"]
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"
        if DEBUG
        else "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

# Tailwind v4 standalone binary: no Node in the project. `manage.py tailwind build` downloads it once.
TAILWIND_CLI_SRC_CSS = "src/gasprice/web/tailwind.css"
TAILWIND_CLI_DIST_CSS = "css/tailwind.css"
TAILWIND_CLI_VERSION = "4.1.14"

SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"
if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = env_bool("DJANGO_SECURE_SSL_REDIRECT", default=True)
    SECURE_REDIRECT_EXEMPT = [r"^api/v1/health$"]
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True

GASPRICE_ANP_PAGE_URL = os.environ.get(
    "GASPRICE_ANP_PAGE_URL",
    "https://www.gov.br/anp/pt-br/assuntos/precos-e-defesa-da-concorrencia/precos/"
    "levantamento-do-precos-de-combustiveis-ultimas-semanas-pesquisadas",
)
GASPRICE_HTTP_TIMEOUT = float(os.environ.get("GASPRICE_HTTP_TIMEOUT", "30"))

# Trips. `osrm` asks GASPRICE_OSRM_URL for road routes (the public demo server by default; point it at a
# self-hosted OSRM for real use). `straight` needs no network: great-circle distance times 1.25.
GASPRICE_ROUTER = os.environ.get("GASPRICE_ROUTER", "osrm")
GASPRICE_OSRM_URL = os.environ.get("GASPRICE_OSRM_URL", "https://router.project-osrm.org")
GASPRICE_NOMINATIM_URL = os.environ.get("GASPRICE_NOMINATIM_URL", "https://nominatim.openstreetmap.org")
GASPRICE_TILE_URL = os.environ.get("GASPRICE_TILE_URL", "https://tile.openstreetmap.org/{z}/{x}/{y}.png")
GASPRICE_TILE_ATTRIBUTION = os.environ.get(
    "GASPRICE_TILE_ATTRIBUTION",
    '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
)

CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
GASPRICE_MAX_AGE_DAYS = int(os.environ.get("GASPRICE_MAX_AGE_DAYS", "15"))

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"plain": {"format": "%(asctime)s %(levelname)s %(name)s %(message)s"}},
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "plain"}},
    "root": {"handlers": ["console"], "level": os.environ.get("LOG_LEVEL", "INFO")},
}
