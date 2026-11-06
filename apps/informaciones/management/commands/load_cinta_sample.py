"""Carga datos de ejemplo para la cinta de informaciones (ticker).

Crea 3 informaciones de cinta (``InformacionCinta``) de ejemplo y activa la
cinta en la configuración global (``ConfiguracionCinta.activada = True``).

Uso:
    python manage.py load_cinta_sample
    python manage.py load_cinta_sample --forzar   # limpia y recrea
"""

from django.core.management.base import BaseCommand

from apps.informaciones.models import ConfiguracionCinta, InformacionCinta


DATOS_CINTA = [
    {
        "texto": "Taller cerrado el 1 de septiembre por mantenimiento eléctrico. ¡Disculpe las molestias!",
        "tipo": "alerta",
        "enlace": None,
        "orden": 1,
        "color_fondo": "#C1121F",
        "color_texto": "#FFFFFF",
        "velocidad": 30,
    },
    {
        "texto": "Promoción: descuento del 15% en mantenimiento preventivo hasta fin de mes.",
        "tipo": "promocion",
        "enlace": "https://wa.me/525512345678",
        "orden": 2,
        "color_fondo": "#000000",
        "color_texto": "#FFFFFF",
        "velocidad": 30,
    },
    {
        "texto": "Nuevos repuestos originales disponibles. Visite nuestro catálogo.",
        "tipo": "comunicado",
        "enlace": "/catalogo/",
        "orden": 3,
        "color_fondo": "#E63946",
        "color_texto": "#FFFFFF",
        "velocidad": 30,
    },
]


class Command(BaseCommand):
    help = "Crea 3 informaciones de cinta de ejemplo y activa la cinta."

    def add_arguments(self, parser):
        parser.add_argument(
            "--forzar",
            action="store_true",
            help="Elimina las informaciones de cinta existentes antes de recrearlas.",
        )

    def handle(self, *args, **options):
        if options["forzar"]:
            InformacionCinta.objects.all().delete()
            self.stdout.write(self.style.WARNING("Informaciones de cinta anteriores eliminadas."))

        creadas = 0
        for datos in DATOS_CINTA:
            existente = InformacionCinta.objects.filter(texto=datos["texto"]).first()
            if existente:
                self.stdout.write(f"  omiso: ya existe — {datos['texto'][:50]}…")
                continue
            InformacionCinta.objects.create(**datos)
            creadas += 1
            self.stdout.write(self.style.SUCCESS(
                f"  + {datos['tipo'].upper():<12s} {datos['texto'][:52]}"
            ))

        # Activa la cinta para que se muestre en el frontend.
        config = ConfiguracionCinta.obtener()
        if not config.activada:
            config.activada = True
            config.save()
            self.stdout.write(self.style.SUCCESS("  Configuración: cinta ACTIVADA."))
        else:
            self.stdout.write("  Configuración: ya estaba activada.")

        total = InformacionCinta.objects.filter(activo=True).count()
        self.stdout.write(self.style.SUCCESS(
            f"\nListo: {creadas} nueva(s) — {total} informaciones de cinta activas."
        ))
