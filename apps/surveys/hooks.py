from django.templatetags.static import static
from django.urls import reverse
from django.utils.functional import cached_property
from django.utils.html import format_html

from wagtail import hooks
from wagtail.admin.widgets.button import Button
from wagtail.snippets.views import snippets
from wagtail.snippets.views.snippets import SnippetViewSet

from apps.surveys.models import Encuesta


# ── Admin JS para paneles condicionales ─────────────────────────
@hooks.register("insert_global_admin_js")
def admin_js_encuestas():
    """Carga los JS de edicion condicional para Encuesta y Pregunta."""
    return format_html(
        '<script src="{}"></script>\n<script src="{}"></script>',
        static("encuestas/edit_encuesta.js"),
        static("encuestas/edit_pregunta.js"),
    )


class EncuestaIndexView(snippets.IndexView):
    @cached_property
    def header_more_buttons(self):
        buttons = super().header_more_buttons.copy()
        buttons.append(
            Button(
                "Ver estadísticas",
                url=reverse("surveys:list"),
                icon_name="tasks",
                priority=50,
            )
        )
        return buttons


class EncuestaEditView(snippets.EditView):
    @cached_property
    def header_more_buttons(self):
        buttons = super().header_more_buttons.copy()
        buttons.append(
            Button(
                "Ver estadísticas",
                url=reverse("surveys:estadisticas", args=[self.object.pk]),
                icon_name="tasks",
                priority=50,
            )
        )
        buttons.append(
            Button(
                "Exportar CSV",
                url=reverse("surveys:exportar_csv", args=[self.object.pk]),
                icon_name="download",
                priority=60,
            )
        )
        return buttons


class EncuestaViewSet(SnippetViewSet):
    model = Encuesta
    icon = "clipboard-list"
    menu_label = "Encuestas"
    list_display = (
        "nombre",
        "titulo_publico",
        "tipo_encuesta",
        "tipo_display",
        "activa",
        "fecha_inicio",
        "fecha_fin",
        "exportar_csv_link",
    )
    list_filter = ("activa", "tipo_encuesta")
    search_fields = ("nombre", "titulo_publico")
    index_view_class = EncuestaIndexView
    edit_view_class = EncuestaEditView