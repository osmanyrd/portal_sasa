"""Registros de administración para la sección de Informaciones / Novedades.

Se enriquece el explorador de páginas de Wagtail para las ``Informacion`` y
``Novedad`` con columnas útiles: tipo, fecha de publicación, destacada y activo
(reaprovechando el mismo mecanismo que usa el módulo de foro).
"""

from django.templatetags.static import static
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from wagtail import hooks
from wagtail.admin.ui.tables import Column

from apps.informaciones.models import Informacion, Novedad


@hooks.register("insert_global_admin_js")
def admin_js_visualizacion_banner():
    """Asistente del editor: oculta el tamaño de miniatura cuando sobra."""
    return format_html(
        '<script src="{}"></script>',
        static("informaciones/admin/js/visualizacion_banner.js"),
    )


def _tipo_valor(page):
    page = page.specific
    nombre = page.nombre_tipo
    if getattr(page, "tipo", None) in ("oferta", "rebaja"):
        etiqueta = {"oferta": "Oferta", "rebaja": "Rebaja"}.get(page.tipo, nombre).upper()
        estilo = {
            "oferta": ("#b02a37", "#fde2e4"),
            "rebaja": ("#166534", "#e6f4ea"),
        }.get(
            page.tipo,
            ("inherit", "transparent"),
        )
        return mark_safe(
            f'<span style="display:inline-block;padding:2px 10px;border-radius:999px;'
            f'font-weight:700;font-size:.75rem;background:{estilo[1]};color:{estilo[0]};">{etiqueta}</span>'
        )
    return nombre


def _fecha_valor(page):
    page = page.specific
    if page.fecha_publicacion:
        return page.fecha_publicacion.strftime("%d/%m/%Y %H:%M")
    return "—"


def _destacada_valor(page):
    page = page.specific
    return "★" if page.destacado else ""


def _activo_valor(page):
    page = page.specific
    return "✓" if page.activo else "✗"


@hooks.register("register_page_listing_column")
def adicionar_columnas_informaciones():
    return [
        Column("tipo", label="Tipo", accessor=_tipo_valor, sort_key="tipo"),
        Column(
            "fecha_publicacion",
            label="Fecha",
            accessor=_fecha_valor,
            sort_key="fecha_publicacion",
        ),
        Column(
            "destacada",
            label="Dest.",
            accessor=_destacada_valor,
            sort_key="destacada",
        ),
        Column("activo", label="Activo", accessor=_activo_valor, sort_key="activo"),
    ]
