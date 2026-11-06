"""Vista del endpoint público de búsqueda `/api/catalogo/buscar/`."""

import logging

from django.http import JsonResponse
from django.views.decorators.http import require_http_methods

from apps.catalogo_erp.models import CategoriaProductoERP
from apps.catalogo_erp.services import CatalogoError, buscar_productos

logger = logging.getLogger(__name__)


@require_http_methods(["GET", "POST"])
def catalogo_buscar(request):
    """Busca productos en el ERP según categoría y provincia; devuelve JSON.

    Parámetros:
      - ``categoria_id`` (obligatorio): pk de una categoría activa.
      - ``provincia`` (obligatorio): código (PR, LH…) o pk de la provincia.
        Limita la disponibilidad a las agencias de esa provincia.
      - ``q`` (obligatorio): término único que se busca a la vez en el código
        y en la descripción del producto.

    Por compatibilidad se aceptan ``q1``/``q2``/``q3``; si viene ``q`` vacío se
    usa el primero informado.
    """
    datos = request.GET if request.method == "GET" else request.POST
    categoria_id = (datos.get("categoria_id") or "").strip()

    if not categoria_id or not categoria_id.isdigit():
        return JsonResponse({"ok": False, "error": "Parámetro 'categoria_id' inválido."})

    try:
        categoria = CategoriaProductoERP.objects.get(pk=int(categoria_id), activo=True)
    except CategoriaProductoERP.DoesNotExist:
        return JsonResponse(
            {"ok": False, "error": "La categoría solicitada no existe o está inactiva."}
        )

    provincia = (datos.get("provincia") or "").strip()
    termino = (datos.get("q") or "").strip()
    if not termino:
        termino = next(
            ((datos.get(f"q{i}") or "").strip() for i in (1, 2, 3) if (datos.get(f"q{i}") or "").strip()),
            "",
        )
    terminos = {"q": termino}

    try:
        productos = buscar_productos(categoria, terminos, provincia)
    except CatalogoError as exc:
        return JsonResponse({"ok": False, "error": str(exc)})
    except Exception as exc:  # noqa: BLE001 - el endpoint nunca debe explotar
        logger.exception("Error inesperado en búsqueda ERP (categoría %s)", categoria.pk)
        return JsonResponse(
            {"ok": False, "error": "Error interno al consultar el ERP. Intentá de nuevo."}
        )

    return JsonResponse(
        {
            "ok": True,
            "productos": productos,
            "provincia": provincia,
        }
    )