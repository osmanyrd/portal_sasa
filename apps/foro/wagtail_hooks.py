"""Registros de administración para el módulo de foro.

- ``CategoriaForo``: snippet con SnippetViewSet (aparece en "Snippets").
- ``TemaForo``: como es una Page, se enriquece el explorador con:
    * columnas extra (categoría, estado, respuestas),
    * un botón "Moderar" que enlaza al panel central de moderación,
  y se añade un ítem de menú "Foro · Moderación" que abre la vista de
  moderación con filtros y acciones en lote.
"""

from django.urls import path

from wagtail import hooks
from wagtail.admin.menu import MenuItem
from wagtail.admin.ui.tables import Column
from wagtail.admin.widgets import PageListingButton
from wagtail.snippets.views.snippets import SnippetViewSet

from apps.foro import views
from apps.foro.models import CategoriaForo, TemaForo


# ---------------------------------------------------------------------------
# Snippet: Categoría de foro (grupo "Gestión de contenido" en core)
# ---------------------------------------------------------------------------
class CategoriaForoViewSet(SnippetViewSet):
    model = CategoriaForo
    icon = "folder-open-inverse"
    menu_label = "Categorías del foro"
    list_display = ("nombre", "slug", "total_temas", "orden", "activo")
    list_filter = ("activo",)
    search_fields = ("nombre", "slug", "descripcion")
    ordering = ["orden", "nombre"]


# ---------------------------------------------------------------------------
# URLs administrativas (vista de moderación)
# ---------------------------------------------------------------------------
@hooks.register("register_admin_urls")
def register_foro_admin_urls():
    return [
        path("foro/moderacion/", views.moderacion, name="foro_moderacion"),
        path(
            "foro/moderar/<int:tema_id>/<str:accion>/",
            views.moderar_tema,
            name="foro_moderar_tema",
        ),
    ]


# ---------------------------------------------------------------------------
# Columnas extra en el explorador de páginas para TemaForo
# ---------------------------------------------------------------------------
def _estado_valor(page):
    page = page.specific
    return page.get_estado_display()


def _categoria_valor(page):
    page = page.specific
    return page.categoria.nombre if page.categoria_id else "—"


def _respuestas_valor(page):
    page = page.specific
    return page.total_respuestas


@hooks.register("register_page_listing_column")
def adicionar_columnas_foro():
    return [
        Column(
            "categoria",
            label="Categoría",
            accessor=_categoria_valor,
            sort_key="categoria__nombre",
        ),
        Column(
            "estado",
            label="Estado",
            accessor=_estado_valor,
            sort_key="estado",
        ),
        Column(
            "respuestas",
            label="Resp.",
            accessor=_respuestas_valor,
            sort_key="respuesta_foro_count",
        ),
    ]


# ---------------------------------------------------------------------------
# Botón "Moderar" en el listado de páginas de cada tema
# ---------------------------------------------------------------------------
@hooks.register("register_page_listing_buttons")
def boton_moderar(page, next_url=None, user=None):
    if isinstance(page, TemaForo):
        return [
            PageListingButton(
                "Moderar",
                "/cms/foro/moderacion/",
                classname="button-secondary",
                icon_name="cog",
                attrs={"title": "Abrir el panel de moderación del foro"},
                priority=10,
            )
        ]
    return []


# ---------------------------------------------------------------------------
# ítem de menú "Foro · Moderación"
# ---------------------------------------------------------------------------
@hooks.register("register_admin_menu_item")
def menu_moderacion_foro():
    return MenuItem(
        "Foro · Moderación",
        "/cms/foro/moderacion/",
        icon_name="tasks",
        order=700,
    )
