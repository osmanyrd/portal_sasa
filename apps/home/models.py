from django.db import models
from wagtail.admin.panels import FieldPanel
from wagtail.fields import StreamField
from wagtail.models import Page
from wagtail.search import index

from apps.core.blocks import STREAMFIELD_BLOCKS


class HomePage(Page):
    subtitle = models.CharField(max_length=255, blank=True)
    hero_image = models.ForeignKey(
        "wagtailimages.Image",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        verbose_name="Imagen principal",
        help_text="Se puede definir un punto focal desde la biblioteca de imágenes.",
    )
    body = StreamField(STREAMFIELD_BLOCKS, blank=True)

    content_panels = Page.content_panels + [
        FieldPanel("subtitle"),
        FieldPanel("hero_image"),
        FieldPanel("body"),
    ]

    search_fields = Page.search_fields + [
        index.SearchField("subtitle"),
        index.SearchField("body"),
    ]

    parent_page_types = ["wagtailcore.Page"]
    subpage_types = [
        "core.GenericPage",
        "core.ContactPage",
    ]

    template = "home/home_page.html"

    class Meta:
        verbose_name = "Página de inicio"
        verbose_name_plural = "Páginas de inicio"

    max_count = 1

    def get_context(self, request, *args, **kwargs):
        context = super().get_context(request, *args, **kwargs)

        # --- Carrusel de inicio ---
        from apps.core.models import BannerCarrusel
        from apps.informaciones.models import Novedad

        slides = []

        # 1. Banner activo (primera diapositiva)
        banner = BannerCarrusel.objects.filter(activo=True).order_by("orden", "-id").first()
        if banner:
            slides.append({
                "tipo": "banner",
                "titulo": banner.titulo,
                "subtitulo": banner.subtitulo,
                "imagen": banner.imagen,
                "boton_texto": banner.boton_texto,
                "boton_enlace": banner.boton_enlace,
            })

        # 2. Novedades destacadas para carrusel
        novedades_carrusel = (
            Novedad.objects.filter(
                aparecer_en_carrusel=True,
                activo=True,
                live=True,
            )
            .order_by("orden_carrusel", "-fecha_publicacion")[:6]
        )
        for nov in novedades_carrusel:
            slides.append({
                "tipo": "novedad",
                "titulo": nov.titulo_efectivo,
                "subtitulo": nov.resumen,
                "imagen": nov.imagen,
                "boton_texto": "Ver más",
                "boton_enlace": nov.url,
                "etiqueta": nov.nombre_tipo,
            })

        context["carousel_slides"] = slides
        context["carousel_total"] = len(slides)

        return context
