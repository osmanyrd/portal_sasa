"""Carga datos de ejemplo para la sección de Informaciones.

Crea la página índice (InformacionesIndexPage) y 4 informaciones de ejemplo
de distintos tipos, todas dentro de la ventana de "recientes".

Uso:
    python manage.py load_informaciones_sample
    python manage.py load_informaciones_sample --forzar
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from wagtail.images.models import Image
from wagtail.models import Site

from apps.informaciones.models import Informacion, InformacionesIndexPage


DATOS_INFORMACIONES = [
    {
        "title": "Corte de suministro eléctrico programado",
        "titulo_corto": "Corte eléctrico: 1 y 2 de septiembre",
        "resumen": "Trabajos en la red eléctrica: servicios con generadores de emergencia.",
        "tipo": "alerta",
        "destacada": True,
        "imagen": "Galeria - Recepcion de clientes",
        "contenido": (
            "<p>Se informa a los clientes que el 1 y 2 de septiembre "
            "se realizarán trabajos en la red eléctrica. Los servicios "
            "de ventas y atención al cliente operarán con generadores "
            "de emergencia con capacidad reducida.</p>"
            "<p>Recomendamos coordinar sus visitas fuera de esos horarios "
            "o contactarnos previamente al <strong>+53 55 123 4567</strong>.</p>"
        ),
    },
    {
        "title": "Mantenimiento preventivo de temporada",
        "titulo_corto": "Mantenimiento preventivo disponible",
        "resumen": "Inspección completa de frenos, fluidos, filtros y refrigeración.",
        "tipo": "aviso",
        "destacada": True,
        "imagen": "Historia - Taller de reparacion",
        "contenido": (
            "<p>Comienza el periodo ideal para el mantenimiento preventivo "
            "de su vehículo antes del cambio de estación. Nuestro equipo "
            "realiza inspección completa de frenos, fluidos, filtros y "
            "sistema de enfriamiento.</p>"
            "<p>Agende su cita sin compromiso en nuestro centro de servicio.</p>"
        ),
    },
    {
        "title": "Nuevos horarios de atención a partir de septiembre",
        "titulo_corto": "Cambios en horarios de lunes a sábado",
        "resumen": "Nuevos horarios de atención al público desde el 1 de septiembre.",
        "tipo": "comunicado",
        "destacada": True,
        "imagen": "Recepcion de clientes",
        "contenido": (
            "<p>Les comunicamos que a partir del 1 de septiembre los "
            "nuevos horarios de atención al público serán:</p>"
            "<ul>"
            "<li>Lunes a viernes: 8:00 a.m. – 5:00 p.m.</li>"
            "<li>Sábados: 8:00 a.m. – 1:00 p.m.</li>"
            "<li>Domingos y feriados: cerrado</li>"
            "</ul>"
        ),
    },
    {
        "title": "Llegan nuevos repuestos originales al catálogo",
        "titulo_corto": "Nuevos repuestos disponibles",
        "resumen": "Filtros, pastillas y bujías originales de primeras marcas ya en stock.",
        "tipo": "noticia",
        "destacada": True,
        "imagen": "Showroom de vehiculos",
        "contenido": (
            "<p>Nuevos repuestos originales de primeras marcas ya están "
            "disponibles en nuestro catálogo. Encuentre filtros de aceite, "
            "pastillas de freno y bujías de encendido de última generación.</p>"
            "<p>Visite la sección <a href='/catalogo/'>Catálogo</a> para "
            "ver el inventario completo con precios y fichas técnicas.</p>"
        ),
    },
]


class Command(BaseCommand):
    help = "Crea la página índice de informaciones y 4 informaciones de ejemplo."

    def add_arguments(self, parser):
        parser.add_argument(
            "--forzar",
            action="store_true",
            help="Elimina las informaciones existentes antes de recrearlas.",
        )

    def handle(self, *args, **options):
        forzar = options["forzar"]

        if forzar:
            Informacion.objects.all().delete()
            self.stdout.write(self.style.WARNING("Informaciones anteriores eliminadas."))

        home = Site.objects.get(is_default_site=True).root_page

        indice = self._crear_indice(home)
        self._crear_informaciones(indice)

        total = Informacion.objects.child_of(indice).count()
        self.stdout.write(self.style.SUCCESS(
            f"\nListo: índice en /{indice.slug}/ — {total} informaciones creadas."
        ))

    def _crear_indice(self, home):
        existente = InformacionesIndexPage.objects.first()
        if existente:
            return existente

        indice = InformacionesIndexPage(
            title="Informaciones",
            slug="informaciones",
            introduccion=(
                "Manténgase al tanto de las novedades, avisos importantes, "
                "comunicados oficiales y eventos de Servicios Automotores S.A."
            ),
            dias_recientes=5,
        )
        home.add_child(instance=indice)
        indice.save_revision().publish()
        self.stdout.write(self.style.SUCCESS(f"  Índice creado: /{indice.slug}/"))
        return indice

    def _crear_informaciones(self, indice):
        ahora = timezone.now()
        total = len(DATOS_INFORMACIONES)

        for i, datos in enumerate(DATOS_INFORMACIONES):
            slug_base = datos["title"].lower()
            for ch in (" ", ":", ".", ",", "¡", "!", "¿", "(", ")", "/", "—"):
                slug_base = slug_base.replace(ch, "-")
            slug_base = slug_base.replace("--", "-").strip("-")

            slug = slug_base
            counter = 1
            while indice.get_children().filter(slug=slug).exists():
                slug = f"{slug_base}-{counter}"
                counter += 1

            fecha_pub = ahora - timezone.timedelta(days=i)

            info = Informacion(
                title=datos["title"],
                slug=slug,
                titulo_corto=datos["titulo_corto"],
                resumen=datos.get("resumen", ""),
                tipo=datos["tipo"],
                contenido=datos["contenido"],
                fecha_publicacion=fecha_pub,
                fecha_expiracion=None,
                destacado=datos["destacada"],
                activo=True,
            )

            titulo_imagen = datos.get("imagen")
            if titulo_imagen:
                imagen = Image.objects.filter(title__icontains=titulo_imagen).first()
                if imagen:
                    info.imagen = imagen
                else:
                    self.stdout.write(self.style.WARNING(
                        f"      aviso: imagen '{titulo_imagen}' no existe en la biblioteca"
                    ))

            existente = Informacion.objects.filter(slug=slug).first()
            if existente:
                self.stdout.write(f"      omiso: {slug} ya existe")
                continue

            indice.add_child(instance=info)
            self.stdout.write(self.style.SUCCESS(
                f"  - {info.nombre_tipo.upper():<14s} /{slug}/  ({datos['title']})"
            ))