"""Tests del motor y de la API del chatbot."""
import json

from django.test import Client, TestCase
from django.urls import reverse

from apps.chatbot.models import DocumentoConocimiento
from apps.chatbot import views


class MotorChatbotTests(TestCase):
    """Pruebas del motor de búsqueda con documentos de muestra."""

    @classmethod
    def setUpTestData(cls):
        DocumentoConocimiento.objects.create(
            titulo="Teléfonos de contacto",
            contenido="Puedes llamarnos al +52 (55) 1234-5678 de lunes a viernes.",
            categoria="contacto",
            fuente_url="#contacto",
            activo=True,
        )
        DocumentoConocimiento.objects.create(
            titulo="Horario de atención",
            contenido="Atendemos de lunes a viernes de 8:00 AM a 6:00 PM y sábados de 8:00 AM a 2:00 PM.",
            categoria="ubicacion",
            fuente_url="#contacto",
            activo=True,
        )
        DocumentoConocimiento.objects.create(
            titulo="Cotización y presupuesto",
            contenido="Para una cotización, llena el formulario de contacto o escríbenos a ventas@example.com.",
            categoria="contacto",
            fuente_url="#contacto",
            activo=True,
        )
        DocumentoConocimiento.objects.create(
            titulo="Misión",
            contenido="Nuestra misión es brindar soluciones automotrices integrales con calidad.",
            categoria="empresa",
            fuente_url="#nosotros",
            activo=True,
        )
        DocumentoConocimiento.objects.create(
            titulo="Visión",
            contenido="Nuestra visión es ser líder en servicios automotrices.",
            categoria="empresa",
            fuente_url="#nosotros",
            activo=True,
        )

    def setUp(self):
        # Evitar cache de documentos entre pruebas
        views._docs_cache = None
        views._docs_cache_key = None

    def test_saludo(self):
        r = views.buscar_respuesta("hola")
        self.assertTrue(r["respondido"])
        self.assertIn("Hola", r["respuesta"])

    def test_telefono_singular_vs_plural(self):
        r = views.buscar_respuesta("cual es el telefono")
        self.assertTrue(r["respondido"])
        self.assertIn("1234-5678", r["respuesta"])

    def test_sinonimo_precio(self):
        r = views.buscar_respuesta("cuanto cuesta")
        self.assertTrue(r["respondido"])
        self.assertIn("cotización", r["respuesta"].lower())

    def test_mision_con_empresa_prefiere_mision(self):
        r = views.buscar_respuesta("cual es la mision de la empresa")
        self.assertTrue(r["respondido"])
        self.assertIn("misión", r["respuesta"].lower())

    def test_horario(self):
        r = views.buscar_respuesta("cuales son sus horarios")
        self.assertTrue(r["respondido"])
        self.assertIn("8:00 AM", r["respuesta"])

    def test_no_encontrado(self):
        r = views.buscar_respuesta("zxqwp vidente absolutamente")
        self.assertFalse(r["respondido"])
        self.assertTrue(r["sugerencias"])

    def test_sugerencias_siempre_presentes(self):
        r = views.buscar_respuesta("telefonos")
        self.assertTrue(r["sugerencias"])


class ApiChatbotTests(TestCase):
    """Pruebas de los endpoints HTTP del chatbot."""

    @classmethod
    def setUpTestData(cls):
        DocumentoConocimiento.objects.create(
            titulo="Teléfonos de contacto",
            contenido="Puedes llamarnos al +52 (55) 1234-5678.",
            categoria="contacto",
            fuente_url="#contacto",
            activo=True,
        )

    def test_consulta_ok(self):
        resp = self.client.post(
            reverse("chatbot:consulta"),
            data=json.dumps({"pregunta": "cual es el telefono"}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["respondido"])
        self.assertIn("1234-5678", data["respuesta"])
        self.assertIn("conversacion_id", data)
        self.assertTrue(data["sugerencias"])

    def test_consulta_corta(self):
        resp = self.client.post(
            reverse("chatbot:consulta"),
            data=json.dumps({"pregunta": "x"}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.json()["respondido"])

    def test_feedback_up(self):
        resp = self.client.post(
            reverse("chatbot:consulta"),
            data=json.dumps({"pregunta": "telefono"}),
            content_type="application/json",
        )
        cid = resp.json()["conversacion_id"]
        conv = DocumentoConocimiento.objects.none()
        from apps.chatbot.models import RegistroConversacion

        self.assertTrue(RegistroConversacion.objects.filter(id=cid).exists())

        fb = self.client.post(
            reverse("chatbot:feedback"),
            data=json.dumps({"conversacion_id": cid, "feedback": "up"}),
            content_type="application/json",
        )
        self.assertEqual(fb.status_code, 200)
        self.assertTrue(fb.json()["ok"])
        RegistroConversacion.objects.get(id=cid).feedback == "up"

    def test_feedback_invalido(self):
        fb = self.client.post(
            reverse("chatbot:feedback"),
            data=json.dumps({"conversacion_id": "abc", "feedback": "meh"}),
            content_type="application/json",
        )
        self.assertEqual(fb.status_code, 400)