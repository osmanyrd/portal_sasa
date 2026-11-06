import logging

from django.conf import settings
from django.core.mail import BadHeaderError, send_mail
from django.db import models
from django.shortcuts import redirect, render
from wagtail.admin.panels import FieldPanel, MultiFieldPanel
from wagtail.fields import RichTextField, StreamField
from wagtail.models import Page
from wagtail.search import index
from wagtail.contrib.settings.models import BaseSiteSetting
from wagtail.contrib.settings.registry import register_setting

from apps.core.blocks import STREAMFIELD_BLOCKS
from apps.core.forms import ContactMessageForm

logger = logging.getLogger(__name__)


class SeoPageMixin(models.Model):
    og_image = models.ForeignKey(
        "wagtailimages.Image",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        verbose_name="Imagen para redes sociales (Open Graph)",
        help_text="Recomendado: 1200 x 630 píxeles.",
    )

    promote_panels = Page.promote_panels + [
        MultiFieldPanel(
            [FieldPanel("og_image")],
            heading="SEO avanzado",
        )
    ]

    class Meta:
        abstract = True


class BasePage(SeoPageMixin, Page):
    class Meta:
        abstract = True


class GenericPage(BasePage):
    subtitle = models.CharField(max_length=255, blank=True)
    header_image = models.ForeignKey(
        "wagtailimages.Image",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        verbose_name="Imagen de cabecera",
    )
    body = StreamField(STREAMFIELD_BLOCKS, blank=True)

    content_panels = Page.content_panels + [
        FieldPanel("subtitle"),
        FieldPanel("header_image"),
        FieldPanel("body"),
    ]

    search_fields = Page.search_fields + [
        index.SearchField("subtitle"),
        index.SearchField("body"),
    ]

    parent_page_types = ["home.HomePage", "core.GenericPage"]
    subpage_types = []

    template = "core/generic_page.html"

    class Meta:
        verbose_name = "Página interior genérica"
        verbose_name_plural = "Páginas interiores genéricas"


class ContactSubmission(models.Model):
    name = models.CharField(max_length=120, verbose_name="Nombre")
    email = models.EmailField(verbose_name="Correo electrónico")
    phone = models.CharField(max_length=25, blank=True, verbose_name="Teléfono")
    message = models.TextField(verbose_name="Mensaje")
    created_at = models.DateTimeField(auto_now_add=True)

    panels = [
        FieldPanel("name"),
        FieldPanel("email"),
        FieldPanel("phone"),
        FieldPanel("message"),
    ]

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Consulta recibida"
        verbose_name_plural = "Consultas recibidas (formulario de contacto)"

    def __str__(self):
        return f"{self.name} <{self.email}> ({self.created_at:%d/%m/%Y %H:%M})"


class ContactPage(BasePage):
    intro = RichTextField(blank=True)
    map_embed_url = models.URLField(
        blank=True,
        verbose_name="Mapa de ubicación",
        help_text=(
            "URL de inserción de Google Maps. En Google Maps: Compartir > "
            "Insertar un mapa > copiar el valor de 'src' del iframe."
        ),
    )
    success_text = models.TextField(
        default="¡Gracias por escribirnos! Te responderemos a la brevedad.",
        verbose_name="Mensaje de agradecimiento",
    )

    content_panels = Page.content_panels + [
        FieldPanel("intro"),
        FieldPanel("success_text"),
        FieldPanel("map_embed_url"),
    ]

    parent_page_types = ["home.HomePage"]
    subpage_types = []
    max_count = 1

    template = "core/contact_page.html"

    def serve(self, request):
        if request.method == "POST":
            form = ContactMessageForm(request.POST)
            is_htmx = request.headers.get("HX-Request") == "true"

            if not form.is_valid():
                if is_htmx:
                    return render(
                        request,
                        "core/includes/contact_form.html",
                        {"form": form},
                    )
            else:
                data = form.cleaned_data
                honeypot = bool(data.get("website"))
                if not honeypot:
                    submission = ContactSubmission.objects.create(
                        name=data["nombre"],
                        email=data["email"],
                        phone=data.get("telefono", ""),
                        message=data["mensaje"],
                    )
                    self._notify(submission)

                if is_htmx:
                    return render(request, "core/includes/contact_success.html", {})
                from django.contrib import messages

                messages.success(request, self.success_text)
                return redirect(f"{self.url}#contacto")
        else:
            form = ContactMessageForm()

        context = self.get_context(request)
        context["form"] = form
        return render(request, self.get_template(request), context)

    def _notify(self, submission):
        subject = f"[Web] Consulta de {submission.name}".replace("\n", " ").strip()
        body = (
            f"Nombre: {submission.name}\n"
            f"Email: {submission.email}\n"
            f"Teléfono: {submission.phone or '-'}\n\n"
            f"{submission.message}"
        )
        try:
            send_mail(
                subject=subject,
                message=body,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[settings.CONTACT_TO_EMAIL],
                reply_to=[submission.email],
            )
        except (BadHeaderError, ConnectionError, Exception) as exc:
            logger.warning(
                "Fallo el envío de email por la consulta de %s: %s",
                submission.email,
                exc,
            )


def messages_success(request, page):
    from django.contrib import messages

    text = page.success_text
    import re

    plain = re.sub(r"<[^>]+>", "", str(text)).strip()
    messages.success(request, plain or "Tu mensaje fue enviado. ¡Gracias!")


@register_setting
class SiteSettings(BaseSiteSetting):
    logo = models.ForeignKey(
        "wagtailimages.Image",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        verbose_name="Logotipo",
        help_text="Idealmente en formato PNG o SVG con fondo transparente.",
    )
    logo_rotacion = models.BooleanField(
        default=False,
        verbose_name="Animar rotación del logo",
        help_text="Si está marcado, el logotipo del navbar girará continuamente (ideal si es redondo y sin fondo).",
    )
    favicon = models.ForeignKey(
        "wagtailimages.Image",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        verbose_name="Favicon",
        help_text="Ícono cuadrado de al menos 32x32 píxeles.",
    )
    primary_color = models.CharField(
        max_length=9,
        default="#0d6efd",
        verbose_name="Color primario",
        help_text="Formato hexadecimal, por ejemplo #0d6efd.",
    )
    secondary_color = models.CharField(
        max_length=9,
        default="#212529",
        verbose_name="Color secundario",
    )
    facebook_url = models.URLField(blank=True, verbose_name="Facebook")
    instagram_url = models.URLField(blank=True, verbose_name="Instagram")
    linkedin_url = models.URLField(blank=True, verbose_name="LinkedIn")
    x_url = models.URLField(blank=True, verbose_name="X (Twitter)")
    youtube_url = models.URLField(blank=True, verbose_name="YouTube")
    footer_text = RichTextField(
        blank=True,
        verbose_name="Texto institucional del footer",
        help_text="Breve descripción de la empresa que aparece en el pie.",
    )
    address = models.CharField(max_length=255, blank=True, verbose_name="Dirección")
    phone = models.CharField(max_length=40, blank=True, verbose_name="Teléfono")
    contact_email = models.EmailField(blank=True, verbose_name="Email de contacto")

    panels = [
        MultiFieldPanel(
            [
                FieldPanel("logo"),
                FieldPanel("logo_rotacion"),
                FieldPanel("favicon"),
                FieldPanel("primary_color"),
                FieldPanel("secondary_color"),
            ],
            heading="Identidad visual",
        ),
        MultiFieldPanel(
            [
                FieldPanel("facebook_url"),
                FieldPanel("instagram_url"),
                FieldPanel("linkedin_url"),
                FieldPanel("x_url"),
                FieldPanel("youtube_url"),
            ],
            heading="Redes sociales",
        ),
        MultiFieldPanel(
            [FieldPanel("footer_text")],
            heading="Footer",
        ),
        MultiFieldPanel(
            [
                FieldPanel("address"),
                FieldPanel("phone"),
                FieldPanel("contact_email"),
            ],
            heading="Datos de contacto",
        ),
    ]

    class Meta:
        verbose_name = "Ajustes del sitio"
        verbose_name_plural = "Ajustes del sitio"


# ─────────────────────────────────────────────────────────
# SISTEMA DE TEMATICA POR FECHAS
# ─────────────────────────────────────────────────────────


class Tema(models.Model):
    """
    Tema visual automatico que se aplica segun la fecha actual.

    Permite cambiar logo, banner y color de acento del sitio
    automaticamente en fechas senaladas (Navidad, Ano Nuevo, etc.).
    Si hay mas de un tema vigente, se selecciona el mas reciente
    por fecha de inicio.
    """

    nombre = models.CharField(max_length=150, verbose_name="Nombre del tema")
    fecha_inicio = models.DateField(verbose_name="Fecha de inicio", db_index=True)
    fecha_fin = models.DateField(verbose_name="Fecha de fin", db_index=True)
    logo = models.ForeignKey(
        "wagtailimages.Image",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        verbose_name="Logo del tema",
        help_text="Reemplaza el logo del sitio durante este tema.",
    )
    banner = models.ForeignKey(
        "wagtailimages.Image",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        verbose_name="Banner del tema",
        help_text="Imagen de banner que se muestra durante este tema.",
    )
    color_acento = models.CharField(
        max_length=9,
        default="#E63946",
        verbose_name="Color de acento (hex)",
        help_text="Color hexadecimal que reemplaza el color primario durante este tema.",
    )
    activo = models.BooleanField(default=True, verbose_name="Activo", db_index=True)

    panels = [
        MultiFieldPanel(
            [
                FieldPanel("nombre"),
                FieldPanel("activo"),
            ],
            heading="Tema",
        ),
        MultiFieldPanel(
            [
                FieldPanel("fecha_inicio"),
                FieldPanel("fecha_fin"),
            ],
            heading="Vigencia",
        ),
        MultiFieldPanel(
            [
                FieldPanel("logo"),
                FieldPanel("banner"),
                FieldPanel("color_acento"),
            ],
            heading="Elementos visuales",
        ),
    ]

    class Meta:
        ordering = ["-fecha_inicio"]
        verbose_name = "Tema"
        verbose_name_plural = "Temas"

    def __str__(self):
        return f"{self.nombre} ({self.fecha_inicio} — {self.fecha_fin})"

    def esta_vigente(self):
        """Verifica si el tema esta vigente segun fechas y flag activo."""
        from datetime import date

        if not self.activo:
            return False
        hoy = date.today()
        return self.fecha_inicio <= hoy <= self.fecha_fin


@register_setting
class ConfiguracionTema(BaseSiteSetting):
    """
    Configuracion por defecto de logos y banner.
    Se usa cuando no hay ningun Tema vigente.
    """

    logo_default = models.ForeignKey(
        "wagtailimages.Image",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        verbose_name="Logo por defecto",
    )
    banner_default = models.ForeignKey(
        "wagtailimages.Image",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        verbose_name="Banner por defecto",
    )
    color_acento_default = models.CharField(
        max_length=9,
        default="#0d6efd",
        verbose_name="Color de acento por defecto (hex)",
    )

    panels = [
        MultiFieldPanel(
            [
                FieldPanel("logo_default"),
                FieldPanel("banner_default"),
                FieldPanel("color_acento_default"),
            ],
            heading="Configuracion por defecto del tema",
        ),
    ]

    class Meta:
        verbose_name = "Configuracion de tema"
        verbose_name_plural = "Configuracion de temas"


# ---------------------------------------------------------------------------
# Banner del carrusel de inicio (snippet)
# ---------------------------------------------------------------------------
# Banner del carrusel de inicio (snippet)
# ---------------------------------------------------------------------------
class BannerCarrusel(models.Model):
    """
    Banner principal que aparece como primera diapositiva del carrusel de inicio.

    Se gestiona como snippet desde el panel de Wagtail (Snippets → Banner del carrusel).
    """

    titulo = models.CharField(max_length=200, verbose_name="Título")
    subtitulo = models.CharField(max_length=300, blank=True, verbose_name="Subtítulo")
    imagen = models.ForeignKey(
        "wagtailimages.Image",
        on_delete=models.CASCADE,
        related_name="+",
        verbose_name="Imagen",
    )
    boton_texto = models.CharField(
        max_length=50, blank=True, verbose_name="Texto del botón 1"
    )
    boton_enlace = models.URLField(
        blank=True, verbose_name="Enlace del botón 1",
        help_text="URL completa (ej.: /servicios/).",
    )
    boton2_texto = models.CharField(
        max_length=50, blank=True, verbose_name="Texto del botón 2"
    )
    boton2_enlace = models.URLField(
        blank=True, verbose_name="Enlace del botón 2",
        help_text="URL completa (ej.: /contacto/).",
    )
    activo = models.BooleanField(default=True, verbose_name="Activo", db_index=True)
    orden = models.IntegerField(default=0, verbose_name="Orden")

    panels = [
        MultiFieldPanel(
            [
                FieldPanel("titulo"),
                FieldPanel("subtitulo"),
            ],
            heading="Contenido",
        ),
        FieldPanel("imagen"),
        MultiFieldPanel(
            [
                FieldPanel("boton_texto"),
                FieldPanel("boton_enlace"),
                FieldPanel("boton2_texto"),
                FieldPanel("boton2_enlace"),
            ],
            heading="Botones de acción",
        ),
        MultiFieldPanel(
            [
                FieldPanel("activo"),
                FieldPanel("orden"),
            ],
            heading="Configuración",
        ),
    ]

    class Meta:
        ordering = ["orden", "-id"]
        verbose_name = "Banner del carrusel"
        verbose_name_plural = "Banners del carrusel"

    def __str__(self):
        return self.titulo
