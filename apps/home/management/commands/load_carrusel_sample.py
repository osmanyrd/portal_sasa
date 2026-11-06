"""
Comando para cargar datos de ejemplo del carrusel de inicio.

Uso:
    python manage.py load_carrusel_sample
"""

from django.core.management.base import BaseCommand
from wagtail.images import get_image_model

from apps.core.models import BannerCarrusel
from apps.informaciones.models import Novedad


class Command(BaseCommand):
    help = "Crea datos de ejemplo para el carrusel de inicio (banner + novedades)"

    def handle(self, *args, **options):
        Image = get_image_model()

        # Buscar una imagen existente para usar como placeholder
        img = Image.objects.first()
        if not img:
            self.stdout.write(self.style.WARNING(
                "No hay imágenes en la biblioteca. Subí una imagen primero."
            ))
            return

        # --- Banner ---
        banner, created = BannerCarrusel.objects.get_or_create(
            titulo="Servicios Automotores S.A",
            defaults={
                "subtitulo": "Especialistas en mantenimiento, reparación y venta de vehículos. Confianza y calidad que garantizan tu movilidad.",
                "imagen": img,
                "boton_texto": "Servicios",
                "boton_enlace": "/servicios/",
                "boton2_texto": "Contáctenos",
                "boton2_enlace": "#contacto",
                "activo": True,
                "orden": 0,
            },
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f"Banner creado: {banner.titulo}"))
        else:
            self.stdout.write(f"Banner ya existe: {banner.titulo}")

        # --- Novedades para carrusel ---
        novedades = Novedad.objects.filter(live=True).order_by("-fecha_publicacion")[:3]
        count = 0
        for i, nov in enumerate(novedades):
            if not nov.aparecer_en_carrusel:
                nov.aparecer_en_carrusel = True
                nov.orden_carrusel = (i + 1) * 10
                nov.save(update_fields=["aparecer_en_carrusel", "orden_carrusel"])
                count += 1
                self.stdout.write(f"  Novedad marcada para carrusel: {nov.title}")

        if count:
            self.stdout.write(self.style.SUCCESS(f"{count} novedad(es) marcada(s) para el carrusel."))
        else:
            self.stdout.write("Las novedades ya estaban marcadas o no hay novedades disponibles.")

        self.stdout.write(self.style.SUCCESS("Datos del carrusel cargados correctamente."))
