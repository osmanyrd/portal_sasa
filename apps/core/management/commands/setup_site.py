from django.core.management.base import BaseCommand
from wagtail.models import Page, Site

from apps.core.models import ContactPage, GenericPage
from apps.home.models import HomePage


class Command(BaseCommand):
    help = (
        "Crea la estructura inicial del sitio: página de inicio, páginas "
        "interiores de ejemplo y configuración del Site. Es idempotente: "
        "puede ejecutarse varias veces sin duplicar contenido."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--hostname",
            default="localhost",
            help="Hostname para el registro Site de Wagtail.",
        )
        parser.add_argument(
            "--skip-demo-content",
            action="store_true",
            help="No crea las páginas de ejemplo.",
        )

    def handle(self, *args, **options):
        root = Page.get_first_root_node()
        site = Site.objects.filter(is_default_site=True).first()

        home = self._get_or_create(
            HomePage,
            slug="inicio",
            defaults={
                "title": "Inicio",
                "subtitle": "Soluciones que impulsan el crecimiento de su empresa",
            },
            parent=root,
        )

        if site is None:
            site = Site.objects.create(
                hostname=options["hostname"],
                port=80,
                root_page=home,
                is_default_site=True,
                site_name="Mi Empresa",
            )
            self.stdout.write(self.style.SUCCESS(f"Site creado ({site.hostname})."))
        elif site.root_page_id != home.id:
            site.root_page = home
            if options["hostname"] != "localhost":
                site.hostname = options["hostname"]
            site.save()
            self.stdout.write(self.style.SUCCESS("Site actualizado."))

        if not options["skip_demo_content"]:
            self._create_demo_content(home)

        self.stdout.write(self.style.SUCCESS("Estructura inicial lista."))

    def _get_or_create(self, model, slug, defaults, parent=None):
        existing = model.objects.filter(slug=slug).first()
        if existing:
            return existing
        instance = model(**{"slug": slug, **defaults})
        target = parent or Page.get_first_root_node()
        target.add_child(instance=instance)
        instance.save_revision().publish()
        self.stdout.write(self.style.SUCCESS(f"Página creada: {instance.title}"))
        return instance

    def _create_demo_content(self, home):
        nosotros = self._get_or_create(
            GenericPage,
            slug="quienes-somos",
            defaults={
                "title": "Quiénes somos",
                "subtitle": "Más de 20 años generando valor para nuestros clientes",
                "show_in_menus": True,
                "body": [
                    {
                        "type": "texto_rico",
                        "value": {
                            "content": (
                                "<h2>Nuestra historia</h2>"
                                "<p>Somos una empresa argentina dedicada a "
                                "brindar soluciones integrales. Combinamos "
                                "experiencia, talento humano y tecnología "
                                "para acompañar a cada cliente en el logro "
                                "de sus objetivos.</p>"
                                "<h3>Nuestros valores</h3>"
                                "<ul><li>Compromiso con la calidad.</li>"
                                "<li>Transparencia en cada proyecto.</li>"
                                "<li>Innovación constante.</li></ul>"
                            ),
                            "background": "bg-white",
                            "alignment": "text-start",
                            "spacing": "section-md",
                        },
                    },
                    {
                        "type": "features",
                        "value": {
                            "heading": "Por qué elegirnos",
                            "intro": "",
                            "items": [
                                {
                                    "icon": "award-fill",
                                    "title": "Experiencia comprobada",
                                    "description": "Cientos de proyectos "
                                    "exitosos respaldan nuestro trabajo.",
                                },
                                {
                                    "icon": "people-fill",
                                    "title": "Equipo especializado",
                                    "description": "Profesionales certificados "
                                    "en cada área de negocio.",
                                },
                                {
                                    "icon": "shield-check",
                                    "title": "Confianza total",
                                    "description": "Procesos transparentes y "
                                    "garantía por escrito.",
                                },
                            ],
                            "columns": "3",
                            "background": "bg-body-tertiary",
                            "alignment": "text-center",
                            "spacing": "section-md",
                        },
                    },
                ],
            },
            parent=home,
        )

        contacto = self._get_or_create(
            ContactPage,
            slug="contacto",
            defaults={
                "title": "Contacto",
                "show_in_menus": True,
                "intro": "<p>Completá el formulario y te responderemos dentro "
                "de las próximas 24 horas hábiles.</p>",
            },
            parent=home,
        )

        for page in (nosotros, contacto):
            if not page.show_in_menus:
                page.show_in_menus = True
                page.save()
