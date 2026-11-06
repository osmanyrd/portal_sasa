"""Widget de Wagtail/Django para capturar latitud/longitud desde el admin.

Renderiza un campo de texto junto a un botón "Obtener coordenadas" que abre
un mapa Leaflet (local, sin APIs de pago) donde se hace clic para elegir el
punto. El valor se escribe automáticamente en el campo con 8 decimales.

Los assets (Leaflet + picker) se inyectan automáticamente en las páginas de
edición de Wagtail gracias a la clase ``Media`` del widget (Wagtail 5+ / 6).
"""
import secrets

from django import forms
from django.template.loader import render_to_string
from django.utils.safestring import mark_safe


class MapPointWidget(forms.TextInput):
    """Entrada de coordenadas con selector de mapa interactivo.

    Es un ``TextInput`` (mantiene la compatibilidad con ``DecimalField``)
    pero renderiza, además del input, el botón y el panel Leaflet.
    """

    template_name = "mapa/widgets/map_point_widget.html"

    # Incluido solo donde se usa el widget: las páginas de edición de
    # Provincia (snippet) en el panel de Dependencias.
    class Media:
        css = {
            "all": (
                "/static/vendor/css/leaflet.css",
                "/static/mapa/css/map_point_admin.css",
            )
        }
        js = (
            "/static/vendor/js/leaflet.js",
            "/static/mapa/js/map_point_admin.js",
        )

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        context["widget"]["type"] = "text"
        context["widget"]["attrs"]["inputmode"] = "decimal"
        context["widget"]["attrs"]["autocomplete"] = "off"
        context["widget"]["attrs"]["placeholder"] = "Ej: 23.137, -82.354"
        return context

    def render(self, name, value, attrs=None, renderer=None):
        # OJO: NO usar super().render() aquí, porque renderizaría con
        # self.template_name (la plantilla del selector) y luego la
        # envolveríamos de nuevo → input y botón duplicados.
        # El input se renderiza con la plantilla estándar de Django.
        widget_context = self.get_context(name, value, attrs)
        input_html = self._render(
            "django/forms/widgets/input.html", widget_context, renderer
        )
        # ID estable del input: lo usa el JS para vincular el mapa con el campo.
        input_id = (attrs or {}).get("id") or "id_%s_%s" % (name, secrets.token_hex(3))
        context = {
            "input": mark_safe(input_html),
            "input_id": input_id,
            "suffix": secrets.token_hex(3),
        }
        return mark_safe(render_to_string(self.template_name, context))