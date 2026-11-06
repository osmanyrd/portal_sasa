"""Carga datos de ejemplo del foro: 2 categorías, página índice y 5 temas
con un total de 10 respuestas.

Uso:
    python manage.py load_foro_sample [--forzar]
"""

from django.core.management.base import BaseCommand
from wagtail.models import Site

from apps.foro.models import CategoriaForo, ForoIndexPage, RespuestaForo, TemaForo


class Command(BaseCommand):
    help = "Crea categorías, la página del foro y temas/respuestas de ejemplo."

    def add_arguments(self, parser):
        parser.add_argument(
            "--forzar",
            action="store_true",
            help="Recrea los datos aunque ya existan (borra y vuelve a crear).",
        )

    def handle(self, *args, **options):
        forzar = options["forzar"]

        if forzar:
            self._limpiar()

        categorias = self._crear_categorias()
        indice = self._crear_indice()

        # Temas de ejemplo por categoría.
        plantillas = [
            ("Aceite sintético 5W-30: ¿cada cuánto cambiarlo?", categorias[0],
             "Recomendamos cambiar el aceite cada 8.000-10.000 km o 6 meses. Este tema "
             "es para compartir experiencias sobre marcas y viscosidades.",
             "Víctor"),
            ("¿Dónde comprar repuestos originales?", categorias[1],
             "Quisiera saber qué distribuidores de repuestos originales recomiendan para "
             "un Kia. Aquí van las opciones que han probado los miembros.",
             "Mariana"),
            ("Filtro de aire: cada cuánto revisarlo", categorias[0],
             "Experiencia con el mantenimiento preventivo del filtro de aire. Compartan "
             "sus kilómetros de referencia.",
             "Rogelio"),
            ("Accesorios para pick-up", categorias[1],
             "Ideas de accesorios útiles para una pick-up de trabajo: faldones, cobertor "
             "de caja y llantas ligeras.",
             "Dayana"),
            ("Mantenimiento de frenos en climas húmedos", categorias[0],
             "Tips para la revisión de frenos cuando la humedad es alta y el óxido de los "
             "discos aparece con más frecuencia.",
             "Alejandro"),
        ]

        if TemaForo.objects.count() == 0:
            for titulo, cat, cuerpo, autor_anon in plantillas:
                tema = TemaForo(
                    title=titulo,
                    categoria=cat,
                    estado=TemaForo.ESTADO_APROBADO,
                    nombre_anonimo=autor_anon,
                    cuerpo=self._html(cuerpo),
                )
                # Un Page debe crearse como hijo de otro Page para tener path/depth.
                indice.add_child(instance=tema)
                self.stdout.write(self.style.SUCCESS(f"  - Tema: {titulo}"))
        else:
            self.stdout.write(self.style.WARNING("Ya existen temas; se omiten (usa --forzar para recrear)."))

        self._crear_respuestas(indice)

        self.stdout.write(self.style.SUCCESS("Datos de ejemplo del foro listos."))

    def _html(self, texto):
        from apps.foro.forms import html_seguro

        return html_seguro(texto)

    def _limpiar(self):
        RespuestaForo.objects.all().delete()
        TemaForo.objects.all().delete()
        self.stdout.write(self.style.WARNING("Datos anteriores eliminados."))

    def _crear_categorias(self):
        datos = [
            ("Mecánica y mantenimiento", "mecanica", "bi-wrench-adjustable",
             "Dudas y consejos sobre mantenimiento y reparación.", 1),
            ("Repuestos y accesorios", "repuestos", "bi-gear",
             "Repuestos, accesorios y recomendaciones de compra.", 2),
        ]
        cats = []
        for nombre, slug, icono, desc, orden in datos:
            cat, _ = CategoriaForo.objects.get_or_create(
                slug=slug,
                defaults={
                    "nombre": nombre,
                    "descripcion": desc,
                    "icono": icono,
                    "orden": orden,
                    "activo": True,
                },
            )
            cats.append(cat)
        self.stdout.write(self.style.SUCCESS("Categorías listas."))
        return cats

    def _crear_indice(self):
        indice = ForoIndexPage.objects.first()
        if indice:
            return indice

        home = Site.objects.get(is_default_site=True).root_page
        indice = ForoIndexPage(
            title="Foro de la comunidad",
            slug="foro",
            introduccion=self._html(
                "Este es el espacio donde clientes y amigos pueden plantear dudas, "
                "compartir experiencias y recibir consejos de nuestro equipo de "
                "Servicios Automotores."
            ),
            reglas=self._html(
                "Sé respetuoso.\n"
                "Mantén los temas dentro del ámbito del foro.\n"
                "No publiques datos personales ni información de contacto sensible.\n"
                "Los moderadores pueden eliminar contenido inapropiado."
            ),
            allow_anonymous=True,
            moderacion_previa=True,
        )
        home.add_child(instance=indice)
        indice.save_revision().publish()
        self.stdout.write(self.style.SUCCESS(f"Índice creado: /{indice.slug}/"))
        return indice

    def _crear_respuestas(self, indice):
        temas = list(TemaForo.objects.child_of(indice).filter(estado=TemaForo.ESTADO_APROBADO))
        if not temas:
            return
        if RespuestaForo.objects.count() > 0:
            return

        autores = ["Carlos", "Lucía", "Pedro", "Sofía", "Ernesto"]
        cuerpos = [
            "Totalmente de acuerdo. En mi caso lo hice a los 9.000 km y noté la diferencia.",
            "Gracias por compartir. ¿Alguien ha probado la otra marca?",
            "Buena información, lo tendré en cuenta para el próximo mantenimiento.",
            "Añado que conviene revisar también la bomba de aceite.",
            "En mi experiencia el precio varía bastante entre distribuidores.",
        ]
        total = 10
        n = 0
        for i in range(total):
            tema = temas[i % len(temas)]
            RespuestaForo.objects.create(
                tema=tema,
                nombre_anonimo=autores[i % len(autores)],
                cuerpo=self._html(cuerpos[i % len(cuerpos)]),
                aprobado=True,
            )
            n += 1
        self.stdout.write(self.style.SUCCESS(f"Respuestas creadas: {n}."))
