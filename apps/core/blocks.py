from uuid import uuid4

from wagtail import blocks
from wagtail.documents.blocks import DocumentChooserBlock
from wagtail.embeds.blocks import EmbedBlock
from wagtail.images.blocks import ImageChooserBlock

BACKGROUND_CHOICES = [
    ("bg-white", "Blanco"),
    ("bg-body-tertiary", "Gris claro"),
    ("bg-brand", "Color primario de la marca"),
    ("bg-dark", "Oscuro"),
]

ALIGNMENT_CHOICES = [
    ("text-start", "Izquierda"),
    ("text-center", "Centrado"),
]

SPACING_CHOICES = [
    ("section-sm", "Compacto"),
    ("section-md", "Normal"),
    ("section-lg", "Amplio"),
]

BUTTON_STYLE_CHOICES = [
    ("btn-brand", "Botón primario (color de marca)"),
    ("btn-outline-brand", "Botón con contorno"),
]


class DesignOptionsMixin(blocks.StructBlock):
    background = blocks.ChoiceBlock(
        choices=BACKGROUND_CHOICES,
        default="bg-white",
        required=False,
        label="Color de fondo",
    )
    alignment = blocks.ChoiceBlock(
        choices=ALIGNMENT_CHOICES,
        default="text-start",
        required=False,
        label="Alineación del texto",
    )
    spacing = blocks.ChoiceBlock(
        choices=SPACING_CHOICES,
        default="section-md",
        required=False,
        label="Espaciado vertical",
    )

    class Meta:
        form_classname = "struct-block"

    def get_context(self, value, parent_context=None):
        context = super().get_context(value, parent_context)
        context["design_classes"] = " ".join(
            part for part in (
                value.get("background"),
                value.get("alignment"),
                value.get("spacing"),
            ) if part
        )
        return context


class ButtonMixin(blocks.StructBlock):
    cta_label = blocks.CharBlock(required=False, label="Texto del botón")
    cta_page = blocks.PageChooserBlock(required=False, label="Enlace interno")
    cta_url = blocks.URLBlock(required=False, label="Enlace externo (URL)")
    cta_style = blocks.ChoiceBlock(
        choices=BUTTON_STYLE_CHOICES,
        default="btn-brand",
        required=False,
        label="Estilo del botón",
    )

    def get_context(self, value, parent_context=None):
        context = super().get_context(value, parent_context)
        target = value.get("cta_page")
        url = value.get("cta_url")
        if target:
            context["cta_href"] = target.url
        elif url:
            context["cta_href"] = url
        else:
            context["cta_href"] = ""
        return context


class HeroBlock(ButtonMixin, DesignOptionsMixin, blocks.StructBlock):
    title = blocks.CharBlock(label="Título principal")
    subtitle = blocks.TextBlock(required=False, rows=3, label="Bajada")
    background_image = ImageChooserBlock(
        required=False,
        label="Imagen de fondo",
        help_text="Opcional. Si no se carga, se usa un fondo degradado.",
    )

    class Meta:
        template = "blocks/hero_block.html"
        icon = "image"
        label = "Portada (Hero)"


class FeatureItemStructBlock(blocks.StructBlock):
    icon = blocks.CharBlock(
        required=True,
        label="Ícono",
        help_text=(
            "Nombre del ícono de Bootstrap Icons sin el prefijo 'bi-'. "
            "Catálogo: https://icons.getbootstrap.com"
        ),
    )
    title = blocks.CharBlock(label="Título de la tarjeta")
    description = blocks.TextBlock(rows=3, label="Descripción")


class FeaturesBlock(DesignOptionsMixin, blocks.StructBlock):
    heading = blocks.CharBlock(required=False, label="Título de la sección")
    intro = blocks.TextBlock(required=False, rows=2, label="Introducción opcional")
    items = blocks.ListBlock(FeatureItemStructBlock(), label="Tarjetas")
    columns = blocks.ChoiceBlock(
        choices=[("2", "2 columnas"), ("3", "3 columnas"), ("4", "4 columnas")],
        default="3",
        label="Cantidad de columnas",
    )

    class Meta:
        template = "blocks/features_block.html"
        icon = "grip"
        label = "Características"


    def get_context(self, value, parent_context=None):
        context = super().get_context(value, parent_context)
        col_class = {"2": "col-lg-6", "3": "col-lg-4", "4": "col-lg-3"}.get(
            value.get("columns"), "col-lg-4"
        )
        context["col_class"] = col_class
        return context


class GalleryImageStructBlock(blocks.StructBlock):
    image = ImageChooserBlock(label="Imagen")
    caption = blocks.CharBlock(required=False, label="Epígrafe")


class GalleryBlock(DesignOptionsMixin, blocks.StructBlock):
    heading = blocks.CharBlock(required=False, label="Título de la galería")
    images = blocks.ListBlock(GalleryImageStructBlock(), min_num=1)
    columns = blocks.ChoiceBlock(
        choices=[("2", "2 columnas"), ("3", "3 columnas"), ("4", "4 columnas")],
        default="3",
        label="Cantidad de columnas",
    )

    class Meta:
        template = "blocks/gallery_block.html"
        icon = "doc-full"
        label = "Galería de imágenes"


    def get_context(self, value, parent_context=None):
        context = super().get_context(value, parent_context)
        col_class = {"2": "col-lg-6", "3": "col-lg-4", "4": "col-lg-3"}.get(
            value.get("columns"), "col-lg-4"
        )
        context["col_class"] = col_class
        return context


class TestimonialStructBlock(blocks.StructBlock):
    quote = blocks.TextBlock(rows=3, label="Testimonio")
    author = blocks.CharBlock(label="Autor/a")
    role = blocks.CharBlock(required=False, label="Cargo o empresa")
    photo = ImageChooserBlock(required=False, label="Foto (opcional)")


class TestimonialsBlock(DesignOptionsMixin, blocks.StructBlock):
    heading = blocks.CharBlock(required=False, label="Título de la sección")
    items = blocks.ListBlock(TestimonialStructBlock(), min_num=1)
    display = blocks.ChoiceBlock(
        choices=[("carousel", "Carrusel"), ("grid", "Lista en tarjetas")],
        default="carousel",
        label="Formato",
    )

    class Meta:
        template = "blocks/testimonials_block.html"
        icon = "comment"
        label = "Testimonios"


    def get_context(self, value, parent_context=None):
        context = super().get_context(value, parent_context)
        context["uid"] = uuid4().hex[:8]
        return context


class CTABlock(ButtonMixin, DesignOptionsMixin, blocks.StructBlock):
    heading = blocks.CharBlock(label="Título")
    text = blocks.TextBlock(required=False, rows=2)

    class Meta:
        template = "blocks/cta_block.html"
        icon = "megaphone"
        label = "Llamado a la acción"

    def get_context(self, value, parent_context=None):
        context = super().get_context(value, parent_context)
        context["on_dark"] = value.get("background") in ("bg-brand", "bg-dark")
        return context


class RichTextSectionBlock(DesignOptionsMixin, blocks.StructBlock):
    content = blocks.RichTextBlock(label="Contenido")

    class Meta:
        template = "blocks/richtext_section_block.html"
        icon = "doc-full-inverse"
        label = "Texto enriquecido"


class VideoBlock(DesignOptionsMixin, blocks.StructBlock):
    heading = blocks.CharBlock(required=False, label="Título")
    embed_url = EmbedBlock(
        required=False,
        label="Video incrustado (YouTube / Vimeo)",
        help_text="Pegá la URL del video.",
    )
    video_file = DocumentChooserBlock(
        required=False,
        label="Archivo de video (.mp4)",
        help_text="Alternativa: un archivo alojado en Documentos.",
    )

    class Meta:
        template = "blocks/video_block.html"
        icon = "media"
        label = "Video"


class ContactFormBlock(DesignOptionsMixin, blocks.StructBlock):
    heading = blocks.CharBlock(default="Escribinos", label="Título")
    text = blocks.TextBlock(required=False, rows=2, label="Texto introductorio")

    class Meta:
        template = "blocks/contact_form_block.html"
        icon = "mail"
        label = "Formulario de contacto"

    def get_context(self, value, parent_context=None):
        from apps.core.forms import ContactMessageForm

        context = super().get_context(value, parent_context)
        context["contact_form"] = ContactMessageForm()
        return context


STREAMFIELD_BLOCKS = [
    ("hero", HeroBlock()),
    ("features", FeaturesBlock()),
    ("gallery", GalleryBlock()),
    ("testimonios", TestimonialsBlock()),
    ("cta", CTABlock()),
    ("texto_rico", RichTextSectionBlock()),
    ("video", VideoBlock()),
    ("formulario_contacto", ContactFormBlock()),
]
