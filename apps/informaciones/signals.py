from django.core.cache import cache

from wagtail.signals import page_published

_CACHE_KEYS = ["info_recientes", "cinta_informaciones"]


def limpiar_cache_informaciones(sender, **kwargs):
    """Invalida el cache de notificaciones/cinta al publicar contenido."""
    for key in _CACHE_KEYS:
        cache.delete(key)


def connect():
    page_published.connect(limpiar_cache_informaciones, dispatch_uid="info_invalidar_cache")