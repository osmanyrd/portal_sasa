"""Smoke tests: verifican que las páginas clave del sitio renderizan sin errores.

Detectan regresiones como tags de plantilla inexistentes (p. ej. el que
rompía el mapa de dependencias) o páginas que lanzan excepciones.
"""

from django.test import TestCase
from django.urls import reverse

from wagtail.models import Page, Site

from apps.home.models import HomePage
from apps.mapa.models import MapaDependenciasPage


class SmokePagesTest(TestCase):
    """Todas las páginas publicadas deben responder 200 sin excepciones."""

    @classmethod
    def setUpTestData(cls):
        root = Site.objects.first().root_page
        cls.root = root

        # Asegurar una HomePage del proyecto bajo la raíz.
        home = HomePage.objects.filter(depth__gt=1).first()
        if home is None:
            home = HomePage(title="Inicio")
            cls.root.add_child(instance=home)
        cls.home = home

        # Asegurar una página de mapa publicada (si no existe, crear).
        mapa = MapaDependenciasPage.objects.filter(live=True).first()
        if mapa is None:
            mapa = MapaDependenciasPage(title="Mapa de Dependencias")
            cls.home.add_child(instance=mapa)
        cls.mapa = mapa

        # Publicar página de mapa (add_child deja draft).
        if not cls.mapa.live:
            cls.mapa.save_revision().publish()

    def test_home_responds_200(self):
        resp = self.client.get(self.home.url)
        self.assertEqual(resp.status_code, 200)

    def test_mapa_dependencias_renders_svg(self):
        resp = self.client.get(self.mapa.url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'class="provincia"')
        self.assertContains(resp, 'data-codigo="LH"')

    def test_cms_login_responds_200(self):
        resp = self.client.get(reverse("wagtailadmin_login"))
        self.assertEqual(resp.status_code, 200)

    def test_all_live_pages_render_200(self):
        live_pages = Page.objects.filter(live=True).exclude(depth__lt=2)
        client = self.client
        for page in live_pages:
            url = page.url
            if not url:
                continue
            with self.subTest(page=page.url_path, url=url):
                resp = client.get(url)
                self.assertEqual(
                    resp.status_code, 200,
                    f"{page.url_path} respondió {resp.status_code}",
                )