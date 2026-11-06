"""Registro en el admin de Wagtail: gestión de usuarios y sistemas externos.

Los ``SnippetViewSet`` se agrupan en las secciones "Gestión de contenido" /
"Configuración" definidas en ``apps.core.wagtail_hooks``.
"""

from django.contrib import messages
from django.contrib.auth.models import User
from django.urls import path
from django.utils import timezone
from wagtail import hooks
from wagtail.snippets.views.snippets import SnippetViewSet

from apps.usuarios import admin_views
from apps.usuarios.models import ConfiguracionSistemaExterno, PerfilUsuario


class ConfiguracionSistemaExternoViewSet(SnippetViewSet):
    """Configuración del sistema externo (Configuración → Sistema externo)."""

    model = ConfiguracionSistemaExterno
    icon = "link"
    menu_label = "Sistema externo"
    list_display = ("nombre", "url", "activo")
    list_filter = ("activo",)
    search_fields = ("nombre", "url")


class PerfilUsuarioViewSet(SnippetViewSet):
    """Perfiles de usuarios registrados (Gestión de contenido → Perfiles de usuario)."""

    model = PerfilUsuario
    icon = "user"
    menu_label = "Perfiles de usuario"
    list_display = (
        "display_name",
        "user",
        "tipo_usuario",
        "activo",
        "fecha_registro",
    )
    list_filter = ("tipo_usuario", "activo")
    search_fields = ("user__username", "user__email", "nombre_empresa", "cif_nit")

    def display_name(self, obj):
        return obj.display_name

    display_name.short_description = "Nombre"


@hooks.register("register_admin_urls")
def registrar_urls_admin():
    return [
        path(
            "usuarios/sincronizar/",
            admin_views.sincronizar_view,
            name="usuarios_sincronizar",
        ),
    ]
