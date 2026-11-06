"""Vista del admin: botón "Probar conexión" del snippet de configuración."""

import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.catalogo_erp.models import ConfiguracionERP
from apps.catalogo_erp.services import probar_conexion

logger = logging.getLogger(__name__)


def _volver(request):
    """URL de retorno preferible tras probar la conexión."""
    return request.META.get("HTTP_REFERER") or reverse("wagtailadmin_home")


@login_required
@require_POST
def probar_conexion_view(request):
    """Prueba la conexión con el ERP y avisa por mensajes del admin."""
    config = None
    config_id = (request.POST.get("id") or "").strip()
    if config_id.isdigit():
        config = ConfiguracionERP.objects.filter(pk=int(config_id)).first()
    if config is None:
        config = ConfiguracionERP.obtener()
    if config is None:
        messages.warning(
            request,
            "Aún no hay una configuración ERP. Guardala primero y volvé a probar.",
        )
        return redirect(_volver(request))

    ok, mensaje = probar_conexion(config)
    config.ultimo_test = timezone.now()
    config.save(update_fields=["ultimo_test"])

    if ok:
        messages.success(request, mensaje)
    else:
        logger.error("Prueba de conexión ERP fallida: %s", mensaje)
        messages.error(request, mensaje)
    return redirect(_volver(request))