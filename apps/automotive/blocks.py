"""
Bloques StreamField para la pagina de Servicios Automotores.
"""
from wagtail.blocks import (
    CharBlock,
    IntegerBlock,
    ListBlock,
    StructBlock,
    URLBlock,
)
from wagtail.blocks.field_block import RichTextBlock, TextBlock
from wagtail.images.blocks import ImageChooserBlock


class HeroBlock(StructBlock):
    """Seccion hero con titulo, subtitulo y CTAs."""

    title = CharBlock(
        default="Servicios Automotores S.A",
        label="Titulo principal",
    )
    subtitle = TextBlock(
        default="Especialistas en mantenimiento, reparacion y venta de vehiculos con mas de 20 anos de experiencia brindando soluciones automotrices integrales.",
        label="Subtitulo",
    )
    hero_image = ImageChooserBlock(required=False, label="Imagen de fondo")
    button_1_text = CharBlock(default="Ver servicios", label="Texto boton 1")
    button_1_url = CharBlock(default="#servicios", label="URL boton 1")
    button_2_text = CharBlock(default="Contactanos", label="Texto boton 2")
    button_2_url = CharBlock(default="#contacto", label="URL boton 2")

    class Meta:
        label = "Seccion Hero"
        icon = "image"


class MissionVisionValuesItem(StructBlock):
    """Item de mision, vision o valores."""

    icon = CharBlock(
        default="bi-bullseye",
        label="Icono Bootstrap Icons (ej: bi-bullseye)",
    )
    title = CharBlock(label="Titulo")
    text = TextBlock(label="Descripcion")


class StatsItem(StructBlock):
    """Item de estadistica."""

    number = IntegerBlock(label="Numero")
    suffix = CharBlock(default="+", label="Sufijo (ej: +)")
    label = CharBlock(label="Descripcion")


class AboutBlock(StructBlock):
    """Seccion Nosotros."""

    section_tag = CharBlock(default="Sobre nosotros", label="Etiqueta de seccion")
    title = CharBlock(
        default="Mas de dos decadas de excelencia automotriz",
        label="Titulo",
    )
    intro = TextBlock(
        default="Desde 2003, Servicios Automotores S.A ha sido sinonimo de confianza y calidad en el sector automotor.",
        label="Introduccion",
    )
    history_image = ImageChooserBlock(required=False, label="Imagen de historia")
    history_title = CharBlock(default="Nuestra historia", label="Titulo de historia")
    history_text = RichTextBlock(
        default="<p>Fundada con la vision de ofrecer un servicio automotriz de clase mundial, hemos crecido hasta convertirnos en un referente del sector. Contamos con instalaciones de mas de 3,000 m2 equipadas con tecnologia de ultima generacion.</p><p>Nuestro equipo de mas de 40 profesionales certificados trabaja con pasion y dedicacion para superar las expectativas de cada cliente.</p>",
        label="Texto de historia",
    )
    values = ListBlock(
        MissionVisionValuesItem,
        default=[
            {"icon": "bi-bullseye", "title": "Mision", "text": "Brindar soluciones automotrices integrales con calidad, eficiencia y compromiso."},
            {"icon": "bi-eye", "title": "Vision", "text": "Ser la empresa lider en servicios automotrices reconocida por nuestra excelencia."},
            {"icon": "bi-heart", "title": "Valores", "text": "Integridad, profesionalismo, innovacion y un compromiso inquebrantable con el cliente."},
        ],
        label="Mision, Vision y Valores",
    )
    stats = ListBlock(
        StatsItem,
        default=[
            {"number": 20, "suffix": "+", "label": "Anos de experiencia"},
            {"number": 15000, "suffix": "+", "label": "Clientes satisfechos"},
            {"number": 40, "suffix": "+", "label": "Tecnicos certificados"},
            {"number": 5000, "suffix": "+", "label": "Vehiculos atendidos al ano"},
        ],
        label="Estadisticas",
    )

    class Meta:
        label = "Seccion Nosotros"
        icon = "users"


class ServiceItem(StructBlock):
    """Item de servicio."""

    icon = CharBlock(
        default="bi-car-front",
        label="Icono Bootstrap Icons (ej: bi-car-front)",
    )
    title = CharBlock(label="Titulo del servicio")
    description = TextBlock(label="Descripcion")
    link_text = CharBlock(default="Mas informacion", label="Texto del enlace")
    link_url = CharBlock(default="#contacto", label="URL del enlace")


class ServicesBlock(StructBlock):
    """Seccion de servicios."""

    section_tag = CharBlock(default="Nuestros servicios", label="Etiqueta de seccion")
    title = CharBlock(
        default="Soluciones automotrices integrales",
        label="Titulo",
    )
    intro = TextBlock(
        default="Ofrecemos una gama completa de servicios disenados para mantener tu vehiculo en optimas condiciones.",
        label="Introduccion",
    )
    services = ListBlock(
        ServiceItem,
        label="Servicios",
    )

    class Meta:
        label = "Seccion Servicios"
        icon = "wrench"


class GalleryImageItem(StructBlock):
    """Item de galeria."""

    image = ImageChooserBlock(label="Imagen")
    alt = CharBlock(label="Texto alternativo")


class GalleryBlock(StructBlock):
    """Seccion de galeria."""

    section_tag = CharBlock(default="Nuestras instalaciones", label="Etiqueta de seccion")
    title = CharBlock(
        default="Conoce nuestras instalaciones",
        label="Titulo",
    )
    images = ListBlock(
        GalleryImageItem,
        label="Imagenes",
    )

    class Meta:
        label = "Seccion Galeria"
        icon = "image"


class LocationInfoItem(StructBlock):
    """Item de informacion de ubicacion."""

    icon = CharBlock(
        default="bi-geo-alt-fill",
        label="Icono Bootstrap Icons (ej: bi-geo-alt-fill)",
    )
    title = CharBlock(label="Titulo")
    text = TextBlock(label="Descripcion")


class LocationBlock(StructBlock):
    """Seccion de ubicacion y vias de acceso."""

    section_tag = CharBlock(default="Encuentranos", label="Etiqueta de seccion")
    title = CharBlock(default="Vias de acceso", label="Titulo")
    intro = TextBlock(
        default="Estamos ubicados en una zona estrategica de facil acceso para tu comodidad.",
        label="Introduccion",
    )
    info_items = ListBlock(
        LocationInfoItem,
        label="Informacion de contacto",
    )
    map_latitude = CharBlock(default="19.4326", label="Latitud del mapa")
    map_longitude = CharBlock(default="-99.1332", label="Longitud del mapa")
    transport_title = CharBlock(default="Transporte publico", label="Titulo transporte")
    transport_text = TextBlock(
        default="Estacion de metro Industrial a 400m. Lineas 1 y 9. Autobuses urbanos rutas 15, 22 y 45 con parada frente a nuestras instalaciones.",
        label="Info de transporte",
    )

    class Meta:
        label = "Seccion Ubicacion"
        icon = "site"


class SocialChannelItem(StructBlock):
    """Item de red social."""

    platform = CharBlock(label="Plataforma (ej: WhatsApp)")
    icon = CharBlock(label="Icono Bootstrap (ej: bi-whatsapp)")
    url = URLBlock(label="URL del perfil")
    handle = CharBlock(label="Manejo (ej: @usuario)")
    color_class = CharBlock(
        default="whatsapp-icon",
        label="Clase CSS del color (ej: whatsapp-icon)",
    )


class ContactBlock(StructBlock):
    """Seccion de contacto."""

    section_tag = CharBlock(default="Contactanos", label="Etiqueta de seccion")
    title = CharBlock(default="Solicita tu cotizacion", label="Titulo")
    intro = TextBlock(
        default="Completa el formulario y nuestro equipo te respondera en menos de 24 horas con una propuesta personalizada.",
        label="Introduccion",
    )
    social_channels = ListBlock(
        SocialChannelItem,
        label="Canales sociales",
    )

    class Meta:
        label = "Seccion Contacto"
        icon = "mail"


class FooterLinkItem(StructBlock):
    """Item de enlace del footer."""

    text = CharBlock(label="Texto del enlace")
    url = CharBlock(default="#", label="URL")


class FooterColumn(StructBlock):
    """Columna del footer."""

    title = CharBlock(label="Titulo de columna")
    links = ListBlock(FooterLinkItem, label="Enlaces")


class FooterBlock(StructBlock):
    """Footer del sitio."""

    description = TextBlock(
        default="Mas de 20 anos brindando soluciones automotrices integrales con la mas alta calidad y compromiso con nuestros clientes.",
        label="Descripcion",
    )
    social_links = ListBlock(
        SocialChannelItem,
        label="Enlaces sociales",
    )
    columns = ListBlock(
        FooterColumn,
        label="Columnas de enlaces",
    )
    country_brand_logo = ImageChooserBlock(
        required=False,
        label="Logo Marca País",
        help_text="Logo de la marca país (ej: Hecho en México).",
    )
    registration_number = CharBlock(
        default="",
        required=False,
        label="Número de registro",
        help_text="Número de registro comercial o legal.",
    )
    copyright_text = CharBlock(
        default="2026 Servicios Automotores S.A. Todos los derechos reservados.",
        label="Texto de copyright",
    )
    privacy_url = URLBlock(required=False, label="URL Politica de privacidad")
    terms_url = URLBlock(required=False, label="URL Terminos y condiciones")

    class Meta:
        label = "Footer"
        icon = "site"
