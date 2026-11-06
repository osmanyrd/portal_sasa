"""
Templatetag de la cinta de informaciones (ticker).

Uso en el template base (justo debajo del navbar):

    {% load cinta_tags %}
    {% mostrar_cinta_informaciones %}

Renderiza la cinta únicamente cuando:
  * la configuración global ``ConfiguracionCinta.activada`` es True, y
  * existe al menos una :class:`InformacionCinta` visible en este momento.

Si no se cumplen ambas, el tag renderiza una cadena vacía (la cinta se oculta).
Los datos se cachean brevemente (5 min) para no consultar la BD en cada petición.
"""
from django import template
from django.core.cache import cache
from django.utils import timezone

from apps.informaciones.models import ConfiguracionCinta, InformacionCinta

register = template.Library()

CACHE_KEY = "cinta_informaciones"
CACHE_TTL = 5 * 60  # 5 minutos


def _calcular():
    """Cálculo real (sin cache) de la cinta."""
    config = ConfiguracionCinta.obtener()
    if not config.activada:
        return {"activada": False, "config": config, "informaciones": []}

    informaciones = list(InformacionCinta.activas())
    return {
        "activada": True,
        "config": config,
        "informaciones": informaciones,
    }


@register.inclusion_tag(
    "informaciones/includes/cinta.html",
    takes_context=False,
)
def mostrar_cinta_informaciones():
    """Prepara el contexto de la cinta de informaciones."""
    try:
        from django.conf import settings

        if getattr(settings, "INFO_CACHE_CINTA", False):
            datos = cache.get(CACHE_KEY)
            if datos is None:
                datos = _calcular()
                cache.set(CACHE_KEY, datos, CACHE_TTL)
            return datos
        return _calcular()
    except Exception:
        return {"activada": False, "config": None, "informaciones": []}
