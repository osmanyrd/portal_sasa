"""
Configuración base compartida por desarrollo y producción.
Toda variable sensible se lee desde el entorno (o un archivo .env en la raíz).
"""
import environ
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env(
    DJANGO_DEBUG=(bool, False),
    DB_ENGINE=(str, "postgresql"),
)

if (BASE_DIR / ".env").exists():
    environ.Env.read_env(BASE_DIR / ".env")

SECRET_KEY = env(
    "DJANGO_SECRET_KEY", default="django-insecure-clave-solo-para-desarrollo-local"
)
DEBUG = env("DJANGO_DEBUG")
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=[])

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.sitemaps",
    "django.contrib.staticfiles",
    "django.contrib.postgres",
    # OAuth2 provider (Portal del Cliente)
    "oauth2_provider",
    # CORS para el frontend del portal
    "corsheaders",
    "wagtail.contrib.forms",
    "wagtail.contrib.redirects",
    "wagtail.contrib.sitemaps",
    "wagtail.contrib.settings",
    "wagtail.embeds",
    "wagtail.sites",
    "wagtail.users",
    "wagtail.snippets",
    "wagtail.documents",
    "wagtail.images",
    "wagtail.search",
    "wagtail.admin",
    "wagtail",
    "modelcluster",
    "taggit",
    "apps.core",
    "apps.home",
    "apps.surveys",
    "apps.automotive",
    "apps.chatbot",
    "apps.mapa",
    "apps.catalogo_erp",
    "apps.foro",
    "apps.informaciones",
    "apps.usuarios",
    "apps.pwa",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.gzip.GZipMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "wagtail.contrib.redirects.middleware.RedirectMiddleware",
    "apps.usuarios.middleware.SessionTimeoutMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "wagtail.contrib.settings.context_processors.settings",
                "apps.core.context_processors.site",
                "apps.core.context_processors.tema_activo",
                "apps.informaciones.context_processors.informaciones_notificaciones",
                "apps.surveys.context_processors.encuestas_contexto",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

if env("DB_ENGINE") == "sqlite":
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": env("POSTGRES_DB", default="institucional"),
            "USER": env("POSTGRES_USER", default="postgres"),
            "PASSWORD": env("POSTGRES_PASSWORD", default="postgres"),
            "HOST": env("DB_HOST", default="localhost"),
            "PORT": env("DB_PORT", default="5432"),
            "CONN_MAX_AGE": 60,
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "UserAttributeSimilarityValidator"
        ),
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 10},
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

LANGUAGE_CODE = "es"
TIME_ZONE = "America/Havana"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

EMAIL_BACKEND = env(
    "EMAIL_BACKEND",
    default=(
        "django.core.mail.backends.console.EmailBackend"
        if DEBUG
        else "django.core.mail.backends.smtp.EmailBackend"
    ),
)
EMAIL_HOST = env("EMAIL_HOST", default="localhost")
EMAIL_PORT = env.int("EMAIL_PORT", default=587)
EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")
EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=True)
EMAIL_USE_SSL = env.bool("EMAIL_USE_SSL", default=False)
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="webmaster@localhost")
CONTACT_TO_EMAIL = env("CONTACT_TO_EMAIL", default=DEFAULT_FROM_EMAIL)

WAGTAIL_SITE_NAME = env("WAGTAIL_SITE_NAME", default="Mi Empresa")
LOGIN_URL = "/cuenta/login/"
LOGIN_REDIRECT_URL = "/cuenta/perfil/"
LOGOUT_REDIRECT_URL = "/cuenta/login/"
WAGTAILADMIN_BASE_URL = env("WAGTAILADMIN_BASE_URL", default="http://localhost:8000")

WAGTAILSEARCH_BACKENDS = {
    "default": {
        "BACKEND": "wagtail.search.backends.database",
    },
}

WAGTAILEMBEDS_FINDERS = [
    {"class": "wagtail.embeds.finders.oembed"},
]

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {"class": "logging.StreamHandler"},
    },
    "root": {
        "handlers": ["console"],
        "level": env("DJANGO_LOG_LEVEL", default="INFO"),
    },
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "unique-snowflake",
    },
}

# --- Sección "Informaciones" ---
# Ventana (en días) para considerar una información como "reciente".
INFO_DIAS_RECIENTES = env.int("INFO_DIAS_RECIENTES", default=5)
# Activa el cache corto del context processor de notificaciones.
INFO_CACHE_RECIENTES = env.bool("INFO_CACHE_RECIENTES", default=True)

# ======================================================================
# OAuth2 (proveedor de identidad para el Portal del Cliente)
# ======================================================================
OAUTH2_PROVIDER = {
    "OAUTH2_APPLICATION_MODEL": "oauth2_provider.Application",
    "ACCESS_TOKEN_EXPIRE_SECONDS": 300,      # 5 minutos
    "REFRESH_TOKEN_EXPIRE_SECONDS": 86400,   # 1 día
    "AUTHORIZATION_CODE_EXPIRE_SECONDS": 600,
    "SCOPES": {
        "read": "Leer datos del perfil",
        "write": "Registrar información",
    },
}

# Orígenes permitidos para el Portal del Cliente (Next.js local).
CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]
CORS_ALLOW_CREDENTIALS = True
