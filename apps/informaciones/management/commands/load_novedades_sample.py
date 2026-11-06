"""Carga datos de ejemplo para la sección de Novedades.

Crea la página índice (NovedadesIndexPage) y novedades de ejemplo
(promociones / ofertas / rebajas / lanzamientos / noticias), algunas marcadas
como destacadas para la portada.

Uso:
    python manage.py load_novedades_sample
    python manage.py load_novedades_sample --forzar
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from wagtail.images.models import Image
from wagtail.models import Site

from apps.informaciones.models import Novedad, NovedadesIndexPage


DATOS_NOVEDADES = [
    {
        "title": "Promoción de temporada en service completo",
        "titulo_corto": "20% off en el service completo",
        "resumen": "Aprovechá el 20% de descuento en el service completo hasta fin de mes.",
        "tipo": "promocion",
        "destacado": True,
        "imagen": "Taller principal",
        "contenido": (
            "<p>Durante todo el mes realizamos el <strong>service completo</strong> "
            "con un <strong>20% de descuento</strong> en mano de obra.</p>"
            "<p>Incluye: cambio de aceite y filtros, revisión de frenos, "
            "control de fluidos y chequeo general de luces.</p>"
            "<p>Turnos limitados. No acumulable con otras promociones.</p>"
        ),
    },
    {
        "title": "Oferta en baterías: cambiás la vieja y ahorrás",
        "titulo_corto": "Baterías con bonificación al entregar la usada",
        "resumen": "Bonificación especial al entregar tu batería usada con la compra de una nueva.",
        "tipo": "oferta",
        "destacado": True,
        "imagen": "Equipo tecnico",
        "contenido": (
            "<p>Llevá tu batería usada y recibí una <strong>bonificación</strong> "
            "sobre el precio de una batería nueva de primeras marcas.</p>"
            "<p>Instalación sin cargo en el acto. Válido hasta agotar stock.</p>"
        ),
    },
    {
        "title": "Nuevo equipo de diagnóstico computarizado",
        "titulo_corto": "Estrenamos equipo de diagnóstico",
        "resumen": "Diagnóstico electrónico de última generación para tu vehículo.",
        "tipo": "lanzamiento",
        "destacado": True,
        "imagen": "Zona de diagnostico",
        "contenido": (
            "<p>Incorporamos un <strong>equipo de diagnóstico computarizado</strong> "
            "de última generación que permite detectar fallas electrónicas y "
            "de motor en minutos.</p>"
            "<p>Consultá por el servicio de escaneo diagnóstico en nuestro centro.</p>"
        ),
    },
    {
        "title": "Nuevo servicio de alineación y balanceo 3D",
        "titulo_corto": "Alineación y balanceo con equipo 3D",
        "resumen": "Sumamos el servicio de alineación y balanceo con tecnología 3D.",
        "tipo": "noticia",
        "destacado": True,
        "imagen": "Vehiculo en servicio",
        "contenido": (
            "<p>Ampliamos nuestro centro con un nuevo <strong>servicio de "
            "alineación y balanceo 3D</strong> para mejorar el rendimiento "
            "y la vida útil de tus neumáticos.</p>"
            "<p>Turnos disponibles de lunes a sábado. Consultá tarifas en recepción.</p>"
        ),
    },
    {
        "title": "Rebaja de temporada en accesorios originales",
        "titulo_corto": "Rebajas en accesorios hasta agotar existencias",
        "resumen": "Rebaja directa en accesorios originales seleccionados de la temporada.",
        "tipo": "rebaja",
        "destacado": True,
        "orden": -1,
        "imagen": "Showroom de vehiculos",
        "contenido": (
            "<p>Durante esta temporada, seleccionamos una serie de "
            "<strong>accesorios originales</strong> con <strong>rebajas "
            "directas</strong> en el precio.</p>"
            "<p>Stock limitado. Aprovechá las rebajas en nuestro local "
            "hasta agotar existencias.</p>"
        ),
    },
]


class Command(BaseCommand):
    help = "Crea la página índice de novedades y novedades de ejemplo (ofertas, rebajas, etc.)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--forzar",
            action="store_true",
            help="Elimina las novedades existentes antes de recrearlas.",
        )

    def handle(self, *args, **options):
        forzar = options["forzar"]

        if forzar:
            Novedad.objects.all().delete()
            self.stdout.write(self.style.WARNING("Novedades anteriores eliminadas."))

        home = Site.objects.get(is_default_site=True).root_page

        indice = self._crear_indice(home)
        self._crear_novedades(indice)

        total = Novedad.objects.child_of(indice).count()
        self.stdout.write(self.style.SUCCESS(
            f"\nListo: índice en /{indice.slug}/ — {total} novedades creadas."
        ))

    def _crear_indice(self, home):
        existente = NovedadesIndexPage.objects.first()
        if existente:
            return existente

        indice = NovedadesIndexPage(
            title="Novedades",
            slug="novedades",
            introduccion=(
                "Promociones, ofertas, lanzamientos y novedades de "
                "Servicios Automotores S.A. ¡No te las pierdas!"
            ),
            dias_recientes=5,
        )
        home.add_child(instance=indice)
        indice.save_revision().publish()
        self.stdout.write(self.style.SUCCESS(f"  Índice creado: /{indice.slug}/"))
        return indice

    def _crear_novedades(self, indice):
        ahora = timezone.now()
        total = len(DATOS_NOVEDADES)

        for i, datos in enumerate(DATOS_NOVEDADES):
            slug_base = datos["title"].lower()
            for ch in (" ", ":", ".", ",", "¡", "!", "¿", "(", ")", "/", "—"):
                slug_base = slug_base.replace(ch, "-")
            slug_base = slug_base.replace("--", "-").strip("-")

            slug = slug_base
            counter = 1
            while indice.get_children().filter(slug=slug).exists():
                slug = f"{slug_base}-{counter}"
                counter += 1

            fecha_pub = ahora - timezone.timedelta(days=i, hours=2)

            novedad = Novedad(
                title=datos["title"],
                slug=slug,
                titulo_corto=datos["titulo_corto"],
                resumen=datos.get("resumen", ""),
                tipo=datos["tipo"],
                contenido=datos["contenido"],
                fecha_publicacion=fecha_pub,
                fecha_expiracion=None,
                destacado=datos["destacado"],
                orden=datos.get("orden", 0),
                activo=True,
            )

            titulo_imagen = datos.get("imagen")
            if titulo_imagen:
                imagen = Image.objects.filter(title__icontains=titulo_imagen).first()
                if imagen:
                    novedad.imagen = imagen
                else:
                    self.stdout.write(self.style.WARNING(
                        f"      aviso: imagen '{titulo_imagen}' no existe en la biblioteca"
                    ))

            existente = Novedad.objects.filter(slug=slug).first()
            if existente:
                self.stdout.write(f"      omiso: {slug} ya existe")
                continue

            indice.add_child(instance=novedad)
            self.stdout.write(self.style.SUCCESS(
                f"  - {novedad.nombre_tipo.upper():<14s} /{slug}/  ({datos['title']})"
            ))