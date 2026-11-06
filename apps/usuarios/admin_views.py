"""Vistas admin: sincronización manual de personas jurídicas."""

import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from apps.usuarios.models import PerfilUsuario


@login_required
def sincronizar_view(request):
    """Muestra el formulario de sincronización y ejecuta la sincronización."""
    if not request.user.is_staff:
        messages.error(request, "No tenés permisos para esta acción.")
        return redirect("wagtailadmin_home")

    if request.method == "POST":
        datos_json = request.POST.get("datos_json", "").strip()
        if not datos_json:
            messages.error(request, " Pegá los datos JSON para sincronizar.")
            return redirect("usuarios_sincronizar")

        try:
            datos = json.loads(datos_json)
        except json.JSONDecodeError as e:
            messages.error(request, f" JSON inválido: {e}")
            return redirect("usuarios_sincronizar")

        from django.core.management import call_command
        from io import StringIO

        out = StringIO()
        call_command(
            "sincronizar_personas_juridicas",
            datos=json.dumps(datos),
            stdout=out,
        )
        resultado = out.getvalue()
        messages.success(request, f"Sincronización completada.\n{resultado}")
        return redirect("usuarios_sincronizar")

    # GET: mostrar formulario
    perfiles_juridicos = PerfilUsuario.objects.filter(
        tipo_usuario="juridica"
    ).select_related("user")[:20]

    return render(request, "usuarios/admin/sincronizar.html", {
        "perfiles_juridicos": perfiles_juridicos,
    })
