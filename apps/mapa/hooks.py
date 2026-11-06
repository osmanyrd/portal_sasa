from django.urls import reverse
from django.utils.functional import cached_property

from wagtail.admin.widgets.button import Button
from wagtail.snippets.views import snippets
from wagtail.snippets.views.snippets import SnippetViewSet

from apps.mapa.models import Dependencia, Provincia


class ProvinciaIndexView(snippets.IndexView):
    @cached_property
    def header_more_buttons(self):
        buttons = super().header_more_buttons.copy()
        buttons.append(
            Button(
                "Ver en mapa",
                url=reverse("wagtailadmin_home") + "?provincia=",
                icon_name="crosshairs",
                priority=50,
            )
        )
        return buttons


class ProvinciaViewSet(SnippetViewSet):
    model = Provincia
    icon = "globe"
    menu_label = "Provincias"
    list_display = ("nombre", "codigo", "orden", "activo", "total_dependencias")
    list_filter = ("activo",)
    search_fields = ("nombre", "codigo")
    index_view_class = ProvinciaIndexView


class DependenciaViewSet(SnippetViewSet):
    model = Dependencia
    icon = "thumbtack"
    menu_label = "Dependencias"
    list_display = ("nombre", "provincia", "tipo", "posicion_x", "posicion_y", "activo")
    list_filter = ("tipo", "activo", "provincia")
    search_fields = ("nombre", "provincia__nombre", "direccion")
    ordering = ["provincia", "nombre"]
