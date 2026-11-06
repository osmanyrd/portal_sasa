"""
Registros de administración de la cinta de informaciones (ticker).

Define los ``SnippetViewSet`` de :class:`InformacionCinta` y
:class:`ConfiguracionCinta` para que aparezcan de forma clara y usable
en el menú Snippets de Wagtail, con listado, filtros y búsqueda.

Los modelos ya se registran en ``models.py`` apuntando aquí (lazy, sin
imports circulares), igual que hace el módulo de encuestas.
"""
from wagtail.snippets.views.snippets import SnippetViewSet

from apps.informaciones.models import ConfiguracionCinta, InformacionCinta


class InformacionCintaViewSet(SnippetViewSet):
    model = InformacionCinta
    icon = "info-circle"
    menu_label = "Cinta informativa"
    list_display = ("texto", "tipo", "orden", "activo", "fecha_inicio", "fecha_fin")
    list_filter = ("activo", "tipo")
    search_fields = ("texto",)
    ordering = ["orden", "-fecha_creacion"]


class ConfiguracionCintaViewSet(SnippetViewSet):
    model = ConfiguracionCinta
    icon = "sliders"
    menu_label = "Configuración de la cinta"
    list_display = ("id", "activada", "estilo", "mostrar_iconos")
    ordering = ["pk"]
