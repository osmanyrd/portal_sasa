"""Logica de disponibilidad de encuestas (Servicios Automotores S.A).

Centraliza el calculo de "encuestas pendientes" para un usuario, de modo que
todas las piezas del frontend (modal, boton flotante, campanita del navbar y
context processor) sean coherentes entre si.

Convenciones de "pendiente":
  * ``activa=True``.
  * Vigente segun ``fecha_inicio`` / ``fecha_fin``.
  * El usuario no ha completado la encuesta (no existe ``Participacion`` con
    ``completada=True`` para su ``session_key``).

Se apoya en el cache de Django para no pegarle a la BD en cada peticion (clave
por sesion), tal y como pide el requisito de eficiencia.
"""
from django.core.cache import cache

from apps.surveys.models import Encuesta

CACHE_TTL = 60 * 5  # 5 minutos


def _get_session_key(request):
    """Obtiene (y si es necesario crea) la clave de sesion del usuario."""
    if not hasattr(request, "session") or not hasattr(request.session, "session_key"):
        return ""
    if not request.session.session_key:
        request.session.create()
    return request.session.session_key or ""


def _calcular_pendientes(session_key):
    """Calcula la lista de encuestas pendientes (sin cache)."""
    ahora = None
    pendientes = []
    for encuesta in Encuesta.objects.filter(activa=True).order_by("-fecha_inicio"):
        if encuesta.esta_vigente() and encuesta.es_pendiente_para(session_key):
            pendientes.append(encuesta)
    return pendientes


def encuestas_pendientes(request, usar_cache=True):
    """Devuelve la lista de encuestas pendientes para el request actual.

    Si ``usar_cache`` es True se cachea por sesion (5 min) para no lanzar
    consultas en cada peticion. La clave incluye la sesion, por lo que cada
    usuario obtiene su propio resultado y el cache se invalida al responder.
    """
    session_key = _get_session_key(request)

    if usar_cache and session_key:
        cache_key = f"surveys_pendientes_{session_key}"
        pendientes = cache.get(cache_key)
        if pendientes is None:
            pendientes = _calcular_pendientes(session_key)
            cache.set(cache_key, pendientes, CACHE_TTL)
        return pendientes

    return _calcular_pendientes(session_key)


def encuesta_pendiente(request, usar_cache=True):
    """Devuelve la encuesta pendiente mas reciente, o ``None``.

    Conveniencia: normalmente basta con la encuesta pendiente mas nueva.
    """
    pendientes = encuestas_pendientes(request, usar_cache=usar_cache)
    return pendientes[0] if pendientes else None


def invalidar_cache_encuestas(session_key):
    """Invalida el cache de encuestas pendientes de una sesion (al responder)."""
    if session_key:
        cache.delete(f"surveys_pendientes_{session_key}")


def contexto_encuestas(request):
    """Dict plano para el context processor.

    Inyecta:
      * ``encuestas_pendientes``          : lista de Encuesta pendientes.
      * ``encuesta_pendiente``            : la mas reciente (o None).
      * ``contador_encuestas_pendientes`` : int (numero de pendientes).
    """
    pendientes = encuestas_pendientes(request, usar_cache=True)
    return {
        "encuestas_pendientes": pendientes,
        "encuesta_pendiente": pendientes[0] if pendientes else None,
        "contador_encuestas_pendientes": len(pendientes),
    }
