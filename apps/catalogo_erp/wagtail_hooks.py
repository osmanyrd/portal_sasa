"""Registro en el admin: snippets ERP y la URL del botón "Probar conexión".

Los ``SnippetViewSet`` se agrupan en las secciones "Gestión de contenido" /
"Configuración" definidas en ``apps.core.wagtail_hooks``.
"""

from django.urls import path
from wagtail import hooks
from wagtail.snippets.views.snippets import SnippetViewSet

from apps.catalogo_erp import admin_views
from apps.catalogo_erp.models import CategoriaProductoERP, ConfiguracionERP


class ConfiguracionERPViewSet(SnippetViewSet):
    """Configuración única de conexión al ERP (Configuración → Configuración ERP)."""

    model = ConfiguracionERP
    icon = "desktop"
    menu_label = "Configuración ERP"
    list_display = ("host", "usuario", "nombre_bd", "activo", "ultimo_test")
    list_filter = ("activo",)
    search_fields = ("host", "usuario", "nombre_bd")


class CategoriaProductoERPViewSet(SnippetViewSet):
    """Categorías de productos del ERP (Gestión de contenido → Categorías del catálogo)."""

    model = CategoriaProductoERP
    icon = "tag"
    menu_label = "Categorías del catálogo"
    list_display = ("nombre", "tabla_origen", "etiqueta_busqueda", "orden", "activo")
    list_filter = ("activo", "metodo_busqueda")
    search_fields = ("nombre", "slug", "tabla_origen")
    ordering = ["orden", "nombre"]


@hooks.register("register_admin_urls")
def registrar_urls_admin():
    return [
        path(
            "catalogo-erp/probar-conexion/",
            admin_views.probar_conexion_view,
            name="catalogo_erp_probar_conexion",
        )
    ]