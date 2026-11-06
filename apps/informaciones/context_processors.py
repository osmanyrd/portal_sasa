"""Context processor de la app de informaciones.

``informaciones_notificaciones`` inyecta en **todas** las plantillas del sitio
las variables que necesitan la campana del navbar y el cartel (toast):

  * ``info_conteo``        : número de contenidos recientes (novedades + informaciones).
  * ``info_recientes``     : lista de dicts (id, título, fecha, url, tipo, categoria).
  * ``info_mostrar_cartel``: booleano (hay algo que mostrar).
  * ``info_indice_url``    : URL de la página índice (para el botón 'Ver').

Se usa un cache corto (opcional, seteado con ``INFO_CACHE_RECIENTES``) para no
lanzar una consulta a la BD en cada petición → requisito de eficiencia/rendimiento.
Es un dict plano y JSON-serializable, por lo que también lo sirve la API.
"""

from django.core.cache import cache

from apps.informaciones import notificaciones

CACHE_KEY = "info_recientes"
CACHE_TTL = 5 * 60  # 5 minutos


def informaciones_notificaciones(request):
    """Datos de notificaciones para el navbar y el cartel de cualquier página."""
    from django.conf import settings

    usar_cache = getattr(settings, "INFO_CACHE_RECIENTES", False)

    if usar_cache:
        datos = cache.get(CACHE_KEY)
        if datos is None:
            datos = _calcular()
            cache.set(CACHE_KEY, datos, CACHE_TTL)
    else:
        datos = _calcular()

    return datos


def _calcular():
    """Ejecuta el cálculo real (sin cache) y lo serializa a dict plano."""
    dias = notificaciones.dias_recientes()
    items, conteo = notificaciones.recientes_todas(
        dias=dias, limit=notificaciones_combinadas_limite()
    )

    lista = []
    for item in items:
        try:
            categoria = item.categoria or "informacion"
        except AttributeError:
            categoria = "informacion"
        lista.append(
            {
                "id": item.pk,
                "titulo": item.nombre_corto,
                "fecha": item.fecha_publicacion,
                "url": item.enlace_externo or item.url,
                "tipo": item.tipo,
                "categoria": categoria,
            }
        )

    return {
        "info_conteo": conteo,
        "info_recientes": lista,
        "info_mostrar_cartel": conteo > 0,
        "info_indice_url": _indice_url(),
        "novedades_indice_url": _novedades_indice_url(),
    }


def _novedades_indice_url():
    """URL de la página índice de Novedades (para el botón 'Ver')."""
    try:
        from apps.informaciones.models import NovedadesIndexPage

        indice = NovedadesIndexPage.objects.live().first()
        if indice:
            return indice.url
    except Exception:
        pass
    return "/novedades/"


def notificaciones_combinadas_limite():
    """Máximo de ítems que se muestran en la campana / cartel combinadas."""
    try:
        from apps.informaciones.models import ContenidoPublicable
        return ContenidoPublicable.CAMPANA_LIMITE
    except Exception:
        return 8


def _indice_url():
    """URL de la página índice de Informaciones (para el botón 'Ver')."""
    try:
        from apps.informaciones.models import InformacionesIndexPage

        indice = InformacionesIndexPage.objects.live().first()
        if indice:
            return indice.url
    except Exception:
        pass
    return "/informaciones/"
