"""
Comando de administración: indexar_contenido

Recorre todas las páginas publicadas del sitio y genera fragmentos
de conocimiento en DocumentoConocimiento para el chatbot.

Uso:
    python manage.py indexar_contenido
    python manage.py indexar_contenido --limpiar  (borra y re-indexa todo)
    python manage.py indexar_contenido --verbose   (muestra detalle)
"""
import re
import textwrap

from django.core.management.base import BaseCommand
from wagtail.models import Page

from apps.chatbot.models import DocumentoConocimiento


# Fragmentos manuales predefinidos (FAQ, info fija)
FRAGMENTOS_ESTATICOS = [
    # ── Empresa ───────────────────────────────────────────
    {
        "titulo": "¿Qué es Servicios Automotores S.A?",
        "contenido": (
            "Servicios Automotores S.A es una empresa con más de 20 años de experiencia "
            "especializada en mantenimiento, reparación y venta de vehículos. "
            "Contamos con instalaciones de más de 3,000 m² equipadas con tecnología "
            "de última generación y un equipo de más de 40 profesionales certificados."
        ),
        "fuente_url": "#nosotros",
        "fuente_titulo": "Sobre nosotros",
        "categoria": "empresa",
    },
    {
        "titulo": "Misión",
        "contenido": (
            "Nuestra misión es brindar soluciones automotrices integrales con calidad, "
            "eficiencia y compromiso."
        ),
        "fuente_url": "#nosotros",
        "fuente_titulo": "Sobre nosotros",
        "categoria": "empresa",
    },
    {
        "titulo": "Visión",
        "contenido": (
            "Nuestra visión es ser la empresa líder en servicios automotrices "
            "reconocida por nuestra excelencia."
        ),
        "fuente_url": "#nosotros",
        "fuente_titulo": "Sobre nosotros",
        "categoria": "empresa",
    },
    {
        "titulo": "Valores",
        "contenido": (
            "Nuestros valores son: integridad, profesionalismo, innovación y un "
            "compromiso inquebrantable con el cliente."
        ),
        "fuente_url": "#nosotros",
        "fuente_titulo": "Sobre nosotros",
        "categoria": "empresa",
    },
    {
        "titulo": "Estadísticas de la empresa",
        "contenido": (
            "Más de 20 años de experiencia, más de 15,000 clientes satisfechos, "
            "más de 40 técnicos certificados, más de 5,000 vehículos atendidos al año."
        ),
        "fuente_url": "#nosotros",
        "fuente_titulo": "Sobre nosotros",
        "categoria": "empresa",
    },

    # ── Servicios detallados ──────────────────────────────
    {
        "titulo": "Venta de vehículos",
        "contenido": (
            "Venta de vehículos nuevos y seminuevos con las mejores marcas del mercado. "
            "Ofrecemos asesoría personalizada, financiamiento flexible y garantía "
            "en cada vehículo. Visítanos para conocer nuestro inventario disponible."
        ),
        "fuente_url": "#servicios",
        "fuente_titulo": "Servicios",
        "categoria": "servicios",
    },
    {
        "titulo": "Mantenimiento preventivo",
        "contenido": (
            "Servicio de mantenimiento preventivo para mantener tu vehículo en óptimas "
            "condiciones. Incluye cambio de aceite, filtros, frenos, alineación, "
            "balanceo, revisión de sistema de enfriamiento y más. Programa tu cita."
        ),
        "fuente_url": "#servicios",
        "fuente_titulo": "Servicios",
        "categoria": "servicios",
    },
    {
        "titulo": "Reparación integral",
        "contenido": (
            "Reparación integral de vehículos: motor, transmisión, suspensión, "
            "sistema eléctrico, dirección y más. Contamos con tecnología de diagnóstico "
            "computarizado y repuestos originales. Garantía en todos los trabajos."
        ),
        "fuente_url": "#servicios",
        "fuente_titulo": "Servicios",
        "categoria": "servicios",
    },
    {
        "titulo": "Diagnóstico computarizado",
        "contenido": (
            "Diagnóstico computarizado de última generación para detectar fallas "
            "en el sistema electrónico, motor, transmisión y otros componentes "
            "de tu vehículo. Resultados precisos y rápidos."
        ),
        "fuente_url": "#servicios",
        "fuente_titulo": "Servicios",
        "categoria": "servicios",
    },
    {
        "titulo": "Grúa y asistencia vial 24 horas",
        "contenido": (
            "Servicio de grúa y asistencia vial disponible las 24 horas del día, "
            "los 7 días de la semana. Asistencia inmediata donde quiera que te "
            "encuentres. Llámanos al +52 (55) 1234-5678."
        ),
        "fuente_url": "#servicios",
        "fuente_titulo": "Servicios",
        "categoria": "servicios",
    },
    {
        "titulo": "Repuestos y accesorios",
        "contenido": (
            "Venta de repuestos originales y accesorios automotrices de las mejores "
            "marcas. Contamos con amplio stock y pedidos especiales. "
            "Calidad garantizada en cada producto."
        ),
        "fuente_url": "#servicios",
        "fuente_titulo": "Servicios",
        "categoria": "servicios",
    },
    {
        "titulo": "Garantía de servicios",
        "contenido": (
            "Todos nuestros servicios de reparación incluyen garantía de servicio "
            "y utilizamos repuestos originales de las mejores marcas del mercado automotor."
        ),
        "fuente_url": "#servicios",
        "fuente_titulo": "Servicios",
        "categoria": "servicios",
    },
    {
        "titulo": "Resumen de servicios",
        "contenido": (
            "Ofrecemos los siguientes servicios: venta de vehículos, mantenimiento "
            "preventivo, reparación integral, diagnóstico computarizado, grúa y asistencia "
            "vial 24 horas, repuestos y accesorios. Todos con garantía de servicio."
        ),
        "fuente_url": "#servicios",
        "fuente_titulo": "Servicios",
        "categoria": "servicios",
    },

    # ── Ubicación ─────────────────────────────────────────
    {
        "titulo": "Dirección",
        "contenido": (
            "Estamos ubicados en Av. Principal #1250, esquina con Calle 5, "
            "Zona Industrial, Ciudad de México, CP 03100."
        ),
        "fuente_url": "#acceso",
        "fuente_titulo": "Ubicación",
        "categoria": "ubicacion",
    },
    {
        "titulo": "Horario de atención",
        "contenido": (
            "Nuestro horario de atención es de lunes a viernes de 8:00 AM a 6:00 PM "
            "y sábados de 8:00 AM a 2:00 PM."
        ),
        "fuente_url": "#acceso",
        "fuente_titulo": "Ubicación",
        "categoria": "ubicacion",
    },
    {
        "titulo": "Transporte público",
        "contenido": (
            "Estación de metro \"Industrial\" a 400 metros. Líneas 1 y 9. "
            "Autobuses urbanos rutas 15, 22 y 45 con parada frente a nuestras instalaciones."
        ),
        "fuente_url": "#acceso",
        "fuente_titulo": "Ubicación",
        "categoria": "ubicacion",
    },
    {
        "titulo": "Parqueo",
        "contenido": (
            "Contamos con estacionamiento gratuito para clientes dentro "
            "de nuestras instalaciones."
        ),
        "fuente_url": "#acceso",
        "fuente_titulo": "Ubicación",
        "categoria": "ubicacion",
    },

    # ── Contacto ──────────────────────────────────────────
    {
        "titulo": "Teléfonos de contacto",
        "contenido": (
            "Puedes llamarnos al +52 (55) 1234-5678 o al +52 (55) 8765-4321."
        ),
        "fuente_url": "#contacto",
        "fuente_titulo": "Contacto",
        "categoria": "contacto",
    },
    {
        "titulo": "Correo electrónico",
        "contenido": (
            "Puedes escribirnos a info@serviciosautomotores.com o "
            "ventas@serviciosautomotores.com."
        ),
        "fuente_url": "#contacto",
        "fuente_titulo": "Contacto",
        "categoria": "contacto",
    },
    {
        "titulo": "Redes sociales",
        "contenido": (
            "Síguenos en Facebook @ServiciosAutomotoresSA, Instagram "
            "@servicios_automotores, LinkedIn: Servicios Automotores S.A. "
            "También puedes contactarnos por WhatsApp al +52 (55) 1234-5678."
        ),
        "fuente_url": "#contacto",
        "fuente_titulo": "Contacto",
        "categoria": "contacto",
    },
    {
        "titulo": "Cotización y presupuesto",
        "contenido": (
            "Para solicitar una cotización, puedes llenar el formulario de contacto "
            "en la sección de Contacto, enviarnos un WhatsApp al +52 (55) 1234-5678, "
            "o escribirnos a ventas@serviciosautomotores.com. Nuestro equipo te "
            "responderá en menos de 24 horas con una propuesta personalizada."
        ),
        "fuente_url": "#contacto",
        "fuente_titulo": "Contacto",
        "categoria": "contacto",
    },
]


def _extraer_texto_de_bloque(value, profundidad=0):
    """Extrae texto plano de un bloque StreamField recursivamente."""
    if profundidad > 10:
        return ""
    if isinstance(value, str):
        # Limpiar HTML
        texto = re.sub(r"<[^>]+>", " ", value)
        return re.sub(r"\s+", " ", texto).strip()
    if isinstance(value, dict):
        # Para dicts de StreamField, extraer solo valores de texto
        partes = []
        for k, v in value.items():
            if k in ("type", "source", "html", "style"):
                continue
            texto = _extraer_texto_de_bloque(v, profundidad + 1)
            if texto:
                partes.append(texto)
        return " ".join(partes)
    if isinstance(value, list):
        partes = []
        for item in value:
            texto = _extraer_texto_de_bloque(item, profundidad + 1)
            if texto:
                partes.append(texto)
        return " ".join(partes)
    # StructValue y otros tipos Wagtail
    if hasattr(value, "source"):
        texto = str(value.source) if value.source else ""
        texto = re.sub(r"<[^>]+>", " ", texto)
        return re.sub(r"\s+", " ", texto).strip()
    if hasattr(value, "value"):
        return _extraer_texto_de_bloque(value.value, profundidad + 1)
    return ""


def _dividir_en_fragmentos(texto, max_len=500):
    """Divide un texto largo en fragmentos por párrafos o por longitud."""
    if not texto or len(texto.strip()) < 30:
        return []
    # Limpiar HTML básico
    texto = re.sub(r"<[^>]+>", " ", texto)
    texto = re.sub(r"\s+", " ", texto).strip()

    # Filtrar ruido común
    patrones_ruido = [
        r"^\d{4}\s+Servicios Automotores",  # footer "2026 Servicios..."
        r"Todos los derechos reservados",    # footer
        r"Política de privacidad",           # footer
        r"Términos y condiciones",           # footer
        r"Ver más información",              # enlace de chatbot
        r"^\d+\.\d+\s+-?\d+\.\d+$",         # solo coordenadas "19.43 -99.13"
        r"^SA$",                             # solo marca
        r"^Servicios Automotores S\.A$",     # solo nombre
        r"^StructValue",                     # datos internos Wagtail
        r"^\s*$",                            # vacíos
    ]
    for patron in patrones_ruido:
        texto = re.sub(patron, "", texto, flags=re.IGNORECASE)

    texto = texto.strip()
    if len(texto) < 30:
        return []

    if len(texto) <= max_len:
        return [texto]

    # Dividir por oraciones
    partes = re.split(r"(?<=[.!?])\s+", texto)
    fragmentos = []
    actual = ""
    for parte in partes:
        if len(actual) + len(parte) + 1 > max_len:
            if actual:
                fragmentos.append(actual.strip())
            actual = parte
        else:
            actual = actual + " " + parte if actual else parte
    if actual.strip():
        fragmentos.append(actual.strip())
    return fragmentos


class Command(BaseCommand):
    help = "Indexa el contenido del sitio para el chatbot."

    def add_arguments(self, parser):
        parser.add_argument(
            "--limpiar",
            action="store_true",
            help="Borra todos los documentos existentes y re-indexa.",
        )
        parser.add_argument(
            "--verbose",
            action="store_true",
            help="Muestra detalle de cada documento creado.",
        )

    def handle(self, *args, **options):
        verbose = options["verbose"]

        if options["limpiar"]:
            count = DocumentoConocimiento.objects.all().count()
            DocumentoConocimiento.objects.all().delete()
            self.stdout.write(self.style.WARNING(f"Borrados {count} documentos anteriores."))
            self.stdout.write("")

        self.stdout.write(self.style.HTTP_INFO("=== Indexando contenido del sitio ===\n"))

        total = 0

        # 1. Fragmentos estáticos
        self.stdout.write(self.style.MIGRATE_HEADING("Fragmentos estáticos (FAQ, info fija):"))
        for frag in FRAGMENTOS_ESTATICOS:
            doc, created = DocumentoConocimiento.objects.get_or_create(
                titulo=frag["titulo"],
                defaults=frag,
            )
            if created:
                total += 1
                if verbose:
                    self.stdout.write(f"  + {frag['titulo']}")
            else:
                if verbose:
                    self.stdout.write(f"  = {frag['titulo']} (ya existe)")

        # 2. Páginas Wagtail publicadas — solo extraer títulos de sección
        # (Los detalles de servicios, ubicación, contacto ya están en fragmentos estáticos)
        self.stdout.write(self.style.MIGRATE_HEADING("\nPáginas Wagtail publicadas:"))
        pages = Page.objects.live().specific()

        for page in pages:
            textos = []

            # Solo extraer títulos y subtítulos de StreamField (no párrafos completos)
            for field_name in ["hero", "about", "services", "gallery", "location", "contact"]:
                if hasattr(page, field_name):
                    sf = getattr(page, field_name)
                    for block in sf:
                        # Extraer solo campos de tipo CharBlock/TextBlock (títulos)
                        if hasattr(block, "value") and isinstance(block.value, dict):
                            for key in ("section_tag", "title", "intro"):
                                if key in block.value and isinstance(block.value[key], str):
                                    textos.append(block.value[key])

            # Title siempre se indexa
            textos.append(page.title)

            # Generar fragmentos
            url = page.url or ""
            titulo_pagina = page.title
            fragmentos_texto = []
            for texto in textos:
                fragmentos_texto.extend(_dividir_en_fragmentos(texto))

            # Guardar cada fragmento
            for i, fragmento in enumerate(fragmentos_texto):
                if len(fragmento.strip()) < 20:
                    continue
                # Determinar categoría
                cat = "general"
                cat_lower = fragmento.lower()
                if any(w in cat_lower for w in ["servicio", "reparación", "venta", "mantenimiento", "diagnóstico", "grúa"]):
                    cat = "servicios"
                elif any(w in cat_lower for w in ["dirección", "ubicación", "horario", "metro", "parqueo", "estacionamiento"]):
                    cat = "ubicacion"
                elif any(w in cat_lower for w in ["teléfono", "correo", "email", "whatsapp", "contacto", "formulario"]):
                    cat = "contacto"
                elif any(w in cat_lower for w in ["misión", "visión", "valores", "historia", "experiencia", "años"]):
                    cat = "empresa"

                titulo_doc = f"{titulo_pagina} — Fragmento {i + 1}" if len(textos) > 1 else titulo_pagina

                doc, created = DocumentoConocimiento.objects.get_or_create(
                    titulo=titulo_doc,
                    fuente_url=url,
                    defaults={
                        "contenido": fragmento,
                        "fuente_titulo": titulo_pagina,
                        "categoria": cat,
                    },
                )
                if created:
                    total += 1
                    if verbose:
                        self.stdout.write(f"  + [{cat}] {titulo_doc} ({len(fragmento)} chars)")

        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(f"Indexación completa. {total} documentos nuevos creados.")
        )
        self.stdout.write(
            f"Total en base: {DocumentoConocimiento.objects.count()} documentos."
        )
