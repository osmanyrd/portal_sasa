"""Lógica modular de "informaciones recientes" (Servicios Automotores S.A).

Concentra TODO el cálculo de qué informaciones se consideran "recientes"
para poder ser usado por:

* el context processor global (navbar + cartel),
* la API JSON ``/api/informaciones/recientes/``,
* la propia página índice (listado).

Regla de "reciente":
  * ``activo=True``
  * ``fecha_publicacion`` dentro de los últimos ``N`` días (configurable).
  * si tiene ``fecha_expiracion`` debe ser futura (mayor que ahora).
  * el Page debe estar publicado (``live``).

La lógica se puede desactivar por completo: basta con no incluir el context
processor (o apagarlo) y/o retirar el botón de campana del template base;
ninguna otra parte del sitio depende de este módulo.
"""

from django.conf import settings


def dias_recientes():
    """Número de días hacia atrás que se considera "reciente".

    Configurable desde settings (``INFO_DIAS_RECIENTES``). Mínimo 1.
    """
    try:
        return max(1, int(settings.INFO_DIAS_RECIENTES))
    except (AttributeError, TypeError, ValueError):
        return 5


def informaciones_recientes(dias=None, limit=None, ahora=None):
    """Devuelve ``(qs, conteo)`` de informaciones recientes en orden
    descendente por fecha de publicación.

    * ``dias``  : ventana en días; ``None`` -> settings.
    * ``limit`` : opcional, recorta el QuerySet (útil para el dropdown).
    * ``ahora`` : inyectable para tests.
    """
    from apps.informaciones.models import Informacion

    if dias is None:
        dias = dias_recientes()

    qs = Informacion.recientes_qs(ahora=ahora, dias=dias)
    conteo = qs.count()
    if limit is not None:
        qs = qs[:limit]
    return qs, conteo


def novedades_recientes(dias=None, limit=None, ahora=None):
    """Análogo a :func:`informaciones_recientes` para :class:`Novedad`."""
    from apps.informaciones.models import Novedad

    if dias is None:
        dias = dias_recientes()

    qs = Novedad.recientes_qs(ahora=ahora, dias=dias)
    conteo = qs.count()
    if limit is not None:
        qs = qs[:limit]
    return qs, conteo


def recientes_todas(dias=None, limit=None, ahora=None):
    """Combina informaciones y novedades recientes en un solo QuerySet/lista.

    Devuelve ``(lista, conteo_total)`` donde cada elemento conserva el modelo
    real (con nombre_tipo, etiqueta_tipo, url, etc.) para poderlo renderizar de
    forma unificada en campana y cartel. Se mezclan por fecha descendente.
    """
    infos, _info_n = informaciones_recientes(dias=dias, ahora=ahora)
    novs, _nov_n = novedades_recientes(dias=dias, ahora=ahora)

    combinados = sorted(
        list(infos) + list(novs),
        key=lambda obj: obj.fecha_publicacion,
        reverse=True,
    )
    conteo = len(combinados)
    if limit is not None:
        combinados = combinados[:limit]
    return combinados, conteo
