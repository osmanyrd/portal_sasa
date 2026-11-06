import json

from django.core.cache import cache
from django.http import JsonResponse
from django.views.decorators.http import require_GET

from apps.mapa.models import ConfiguracionMapa, _provincias_data

CACHE_KEY = "mapa_datos_json"
CACHE_TTL = 60 * 10  # 10 minutos


@require_GET
def mapa_datos(request):
    """GET /api/mapa/datos/ — JSON con provincias activas, hotspots y dependencias."""
    datos = cache.get(CACHE_KEY)
    if datos is None:
        datos = _mapa_datos()
        cache.set(CACHE_KEY, datos, CACHE_TTL)
    return JsonResponse(datos, json_dumps_params={"ensure_ascii": False})


def _mapa_datos():
    """Serializa el payload completo del API del mapa (sin cache)."""
    from wagtail.models import Site

    site = Site.objects.first()
    mapa_conf = None
    try:
        if site is not None:
            mapa_conf = ConfiguracionMapa.for_site(site)
    except Exception:
        pass

    mapa_url = ""
    if mapa_conf and mapa_conf.imagen_mapa:
        mapa_url = mapa_conf.imagen_mapa.get_rendition("original").url

    return {
        "mapa_url": mapa_url,
        "provincias": _provincias_data(),
    }
