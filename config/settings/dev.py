from .base import *  # noqa: F403

DEBUG = True

ALLOWED_HOSTS = sorted(set(ALLOWED_HOSTS) | {"localhost", "127.0.0.1", "web", "192.168.19.9", "informatico-cm.sasa.co.cu"})

CSRF_TRUSTED_ORIGINS = sorted(set(env.list("CSRF_TRUSTED_ORIGINS", default=[])) | {
    "http://informatico-cm.sasa.co.cu:8000",
    "https://informatico-cm.sasa.co.cu",
})

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
