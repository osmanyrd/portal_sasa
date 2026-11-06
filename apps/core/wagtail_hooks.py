"""
Registros de administración para el módulo core.

Organiza todos los snippets del sitio en dos secciones del menú del admin:

- **Gestión de contenido**: banners, temas visuales, cinta, encuestas,
  categorías del foro, conocimiento/conversaciones del chatbot, provincias,
  dependencias, categorías del catálogo, consultas recibidas y perfiles.
- **Configuración**: conexión al ERP y sistema externo.

Los ``SnippetViewSet`` viven en cada app (``wagtail_hooks.py`` / ``hooks.py``)
y se agrupan aquí con ``SnippetViewSetGroup``, de modo que la barra lateral
queda ordenada y desaparece el menú "Fragmentos" plano.
"""

from wagtail.snippets.models import register_snippet
from wagtail.snippets.views.snippets import SnippetViewSet, SnippetViewSetGroup

from apps.catalogo_erp.wagtail_hooks import (
    CategoriaProductoERPViewSet,
    ConfiguracionERPViewSet,
)
from apps.chatbot.wagtail_hooks import (
    DocumentoConocimientoViewSet,
    RegistroConversacionViewSet,
)
from apps.foro.wagtail_hooks import CategoriaForoViewSet
from apps.informaciones.hooks import ConfiguracionCintaViewSet, InformacionCintaViewSet
from apps.mapa.hooks import DependenciaViewSet, ProvinciaViewSet
from apps.surveys.hooks import EncuestaViewSet
from apps.usuarios.wagtail_hooks import (
    ConfiguracionSistemaExternoViewSet,
    PerfilUsuarioViewSet,
)

from apps.core.models import BannerCarrusel, ContactSubmission, Tema


class ContactSubmissionViewSet(SnippetViewSet):
    model = ContactSubmission
    icon = "mail"
    menu_label = "Consultas recibidas"
    list_display = ("name", "email", "phone", "created_at")
    list_filter = ("created_at",)
    search_fields = ("name", "email", "phone", "message")
    ordering = ["-created_at"]
    search_background_color = "grey"


class TemaViewSet(SnippetViewSet):
    model = Tema
    icon = "view"
    menu_label = "Temas visuales"
    list_display = ("nombre", "fecha_inicio", "fecha_fin", "activo")
    list_filter = ("activo",)
    search_fields = ("nombre",)
    ordering = ["-fecha_inicio"]


class BannerCarruselViewSet(SnippetViewSet):
    model = BannerCarrusel
    icon = "image"
    menu_label = "Banners"
    list_display = ("titulo", "orden", "activo")
    list_filter = ("activo",)
    search_fields = ("titulo", "subtitulo")
    ordering = ["orden", "-id"]


class ContenidoViewSetGroup(SnippetViewSetGroup):
    """Sección "Gestión de contenido" del menú del admin."""

    items = [
        BannerCarruselViewSet,
        TemaViewSet,
        InformacionCintaViewSet,
        ConfiguracionCintaViewSet,
        EncuestaViewSet,
        CategoriaForoViewSet,
        DocumentoConocimientoViewSet,
        RegistroConversacionViewSet,
        ProvinciaViewSet,
        DependenciaViewSet,
        CategoriaProductoERPViewSet,
        ContactSubmissionViewSet,
        PerfilUsuarioViewSet,
    ]
    menu_label = "Gestión de contenido"
    menu_icon = "form"
    menu_order = 600


class ConfiguracionViewSetGroup(SnippetViewSetGroup):
    """Sección "Configuración" del menú del admin."""

    items = [ConfiguracionERPViewSet, ConfiguracionSistemaExternoViewSet]
    menu_label = "Configuración"
    menu_icon = "cog"
    menu_order = 650


register_snippet(ContenidoViewSetGroup)
register_snippet(ConfiguracionViewSetGroup)