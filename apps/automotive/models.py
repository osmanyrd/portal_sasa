"""
Modelo de pagina para Servicios Automotores.
"""
import hashlib

from django.db import models
from wagtail.admin.panels import FieldPanel, MultiFieldPanel
from wagtail.fields import StreamField
from wagtail.models import Page
from wagtail.images.blocks import ImageChooserBlock

from apps.automotive.blocks import (
    AboutBlock,
    ContactBlock,
    FooterBlock,
    GalleryBlock,
    HeroBlock,
    LocationBlock,
    ServicesBlock,
)


class AutomotivePage(Page):
    """
    Pagina de aterrizaje para Servicios Automotores S.A.

    Permite editar todas las secciones del sitio desde el admin de Wagtail
    usando bloques StreamField.
    """

    template = "automotive/automotive_page.html"

    logo = StreamField(
        [("logo", ImageChooserBlock(label="Logo del sitio"))],
        blank=True,
        use_json_field=True,
        verbose_name="Logo",
        help_text="Logo que aparece en la barra de navegación. Si está vacío, se muestra el texto 'SA'.",
    )

    hero = StreamField(
        [("hero", HeroBlock())],
        blank=True,
        use_json_field=True,
        verbose_name="Seccion Hero",
    )
    about = StreamField(
        [("about", AboutBlock())],
        blank=True,
        use_json_field=True,
        verbose_name="Seccion Nosotros",
    )
    services = StreamField(
        [("services", ServicesBlock())],
        blank=True,
        use_json_field=True,
        verbose_name="Seccion Servicios",
    )
    gallery = StreamField(
        [("gallery", GalleryBlock())],
        blank=True,
        use_json_field=True,
        verbose_name="Seccion Galeria",
    )
    location = StreamField(
        [("location", LocationBlock())],
        blank=True,
        use_json_field=True,
        verbose_name="Seccion Ubicacion",
    )
    contact = StreamField(
        [("contact", ContactBlock())],
        blank=True,
        use_json_field=True,
        verbose_name="Seccion Contacto",
    )
    footer = StreamField(
        [("footer", FooterBlock())],
        blank=True,
        use_json_field=True,
        verbose_name="Footer",
    )

    # --- Modo de visualización de las tarjetas de la portada ---
    MODO_VERTICAL = "vertical"
    MODO_HORIZONTAL = "horizontal"

    MODO_TARJETAS_CHOICES = [
        (MODO_VERTICAL, "Vertical (imagen arriba)"),
        (MODO_HORIZONTAL, "Horizontal (imagen al costado)"),
    ]

    modo_tarjetas_novedades = models.CharField(
        max_length=20,
        choices=MODO_TARJETAS_CHOICES,
        default=MODO_VERTICAL,
        verbose_name="Tarjetas de Novedades",
        help_text="Cómo se muestran las tarjetas de la columna de novedades.",
    )
    modo_tarjetas_informaciones = models.CharField(
        max_length=20,
        choices=MODO_TARJETAS_CHOICES,
        default=MODO_VERTICAL,
        verbose_name="Tarjetas de Informaciones",
        help_text="Cómo se muestran las tarjetas de la columna de informaciones.",
    )

    content_panels = Page.content_panels + [
        FieldPanel("logo"),
        "hero",
        "about",
        "services",
        "gallery",
        "location",
        "contact",
        "footer",
        MultiFieldPanel(
            [
                FieldPanel("modo_tarjetas_novedades"),
                FieldPanel("modo_tarjetas_informaciones"),
            ],
            heading="Portada: tarjetas de Novedades e Informaciones",
            help_text=(
                "Elegí si las tarjetas destacadas de cada columna se muestran "
                "verticales (imagen arriba, 2 por fila) u horizontales "
                "(imagen al costado, una debajo de otra)."
            ),
        ),
    ]

    class Meta:
        verbose_name = "Pagina Automotriz"
        verbose_name_plural = "Paginas Automotrices"

    # --- Contenidos destacados de la portada (Novedades / Informaciones) ---
    MAX_DESTACADOS_POR_COLUMNA = 4

    @property
    def novedades_visibles(self):
        """Novedades activas marcadas como destacadas (columna izquierda)."""
        from apps.informaciones.models import Novedad

        return Novedad.destacados(limite=self.MAX_DESTACADOS_POR_COLUMNA)

    @property
    def informaciones_visibles(self):
        """Informaciones activas marcadas como destacadas (columna derecha)."""
        from apps.informaciones.models import Informacion

        return Informacion.destacados(limite=self.MAX_DESTACADOS_POR_COLUMNA)

    @property
    def tiene_novedades(self):
        return bool(self.novedades_visibles)

    @property
    def tiene_informaciones(self):
        return bool(self.informaciones_visibles)

    def get_context(self, request, *args, **kwargs):
        context = super().get_context(request, *args, **kwargs)

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
                "boton2_texto": banner.boton2_texto,
                "boton2_enlace": banner.boton2_enlace,
            })

        # 2. Novedades destacadas para carrusel
        novedades_carrusel = (
            Novedad.objects.filter(
                aparecer_en_carrusel=True,
                activo=True,
                live=True,
            )
            .select_related("imagen")
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
                # Presentación de la imagen (reutiliza los campos de Novedad):
                # la presentación principal (tipo 'banner') siempre llena la
                # pantalla; las novedades usan su modo/tamaño/fondo/posición.
                "modo_efectivo": nov.modo_efectivo,
                "tamano_miniatura": nov.tamano_miniatura,
                "estilo_fondo": nov.estilo_fondo,
                "posicion_vertical": nov.posicion_vertical,
                "posicion_horizontal": nov.posicion_horizontal,
            })

        context["carousel_slides"] = slides
        context["carousel_total"] = len(slides)

        # Clave de caché por contenido: el fragmento del carrusel se re-renderiza
        # cuando cambia cualquiera de las opciones que definen su aspecto.
        firma = "|".join(
            "{tipo}:{img}:{modo}:{tam}:{fondo}:{posv}:{posh}".format(
                tipo=s.get("tipo", ""),
                img=s.get("imagen").pk if s.get("imagen") else "-",
                modo=s.get("modo_efectivo", ""),
                tam=s.get("tamano_miniatura", ""),
                fondo=s.get("estilo_fondo", ""),
                posv=s.get("posicion_vertical", ""),
                posh=s.get("posicion_horizontal", ""),
            )
            for s in slides
        )
        context["carousel_cache_key"] = hashlib.md5(firma.encode()).hexdigest()[:12]

        return context
