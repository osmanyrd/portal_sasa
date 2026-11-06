"""Carga datos de ejemplo del Catálogo ERP.

Crea (o actualiza con ``--forzar``):
  - La página pública ``CatalogoERPPage`` bajo la página del sitio.
  - Una ``ConfiguracionERP`` de ejemplo (INACTIVA, pensada para adaptar).
  - Tres categorías de productos con métodos de búsqueda distintos.

Las categorías apuntan a tablas del ERP de ejemplo (``productos`` y
``stock_productos``) con columnas típicas. Adaptá los nombres a tu ERP real
desde el panel (Snippets → Categorías ERP).
"""

from django.core.management.base import BaseCommand
from django.utils.text import slugify

from apps.automotive.models import AutomotivePage
from apps.catalogo_erp.models import (
    CatalogoERPPage,
    CategoriaProductoERP,
    ConfiguracionERP,
)

INTRO = """
<p>Consultá en línea la disponibilidad de nuestros productos en cada
dependencia. Elegí una categoría y buscá por código, segmento o varios
criterios. Los datos provienen directo de nuestro sistema ERP.</p>
""".strip()

CATEGORIAS = [
    {
        "nombre": "Neumáticos",
        "descripcion": "Cubiertas de todo tipo para auto, utilitario y camión.",
        "tabla_origen": "productos",
        "campo_codigo": "codigo",
        "campo_nombre": "nombre",
        "campo_extra1": "marca",
        "campo_categoria": "categoria",
        "valor_categoria": "NEUMATICOS",
        "metodo_busqueda": "multiple",
        "orden": 1,
        "ayuda_busqueda": "Buscá un neumático por cualquiera de estos criterios:\n"
                          "• Código: NTM-20555R16\n"
                          "• Nombre: 205/55 R16, todo terreno, SUV\n"
                          "• Detalle: invierno, radial, reforzado\n"
                          "Ejemplos: NTM-17565R14 · NTM-23545R17 · NTM-24570R16",
        "imagen_contiene": "neumatico",
        "consulta_sql": (
            "SELECT p.codigo, p.nombre, p.marca AS extra1, "
            "COALESCE(d.nombre, s.codigo_dependencia) AS dependencia, "
            "COALESCE(s.cantidad, 0) AS cantidad "
            "FROM productos AS p "
            "LEFT JOIN stock_productos AS s ON s.codigo_producto::text = p.codigo::text "
            "LEFT JOIN dependencias AS d ON d.codigo::text = s.codigo_dependencia::text "
            "WHERE p.categoria = :q1 AND p.nombre ILIKE '%' || :q2 || '%' AND "
            "p.marca ILIKE '%' || :q3 || '%'"
        ),
        "usar_consulta_personalizada": False,
    },
    {
        "nombre": "Baterías",
        "descripcion": "Baterías de arranque y accesorios eléctricos.",
        "tabla_origen": "productos",
        "campo_codigo": "codigo",
        "campo_nombre": "nombre",
        "campo_extra1": "marca",
        "campo_categoria": "categoria",
        "valor_categoria": "BATERIAS",
        "metodo_busqueda": "multiple",
        "orden": 2,
        "ayuda_busqueda": "Buscá una batería por cualquiera de estos criterios:\n"
                          "• Código: BAT-12V60\n"
                          "• Nombre: 12V 60Ah 540A\n"
                          "• Detalle: libre de mantenimiento, placa seca\n"
                          "Ejemplos: BAT-12V45 · BAT-12V75 · BAT-24V120",
        "imagen_contiene": "bateria",
        "consulta_sql": (
            "SELECT p.codigo, p.nombre, p.marca AS extra1, "
            "COALESCE(d.nombre, s.codigo_dependencia) AS dependencia, "
            "COALESCE(s.cantidad, 0) AS cantidad "
            "FROM productos AS p "
            "LEFT JOIN stock_productos AS s ON s.codigo_producto::text = p.codigo::text "
            "LEFT JOIN dependencias AS d ON d.codigo::text = s.codigo_dependencia::text "
            "WHERE p.categoria = :q1 AND p.nombre ILIKE '%' || :q2 || '%' AND "
            "p.marca ILIKE '%' || :q3 || '%'"
        ),
        "usar_consulta_personalizada": False,
    },
    {
        "nombre": "Frenos",
        "descripcion": "Pastillas, discos, líquido y componentes del sistema de frenos.",
        "tabla_origen": "productos",
        "campo_codigo": "codigo",
        "campo_nombre": "nombre",
        "campo_extra1": "marca",
        "campo_categoria": "categoria",
        "valor_categoria": "FRENOS",
        "metodo_busqueda": "multiple",
        "orden": 3,
        "ayuda_busqueda": "Buscá un componente de frenos por cualquiera de estos criterios:\n"
                          "• Código: FRN-PSF015\n"
                          "• Nombre: pastillas delanteras, disco 280 mm\n"
                          "• Detalle: cerámico, orgánico, rueda trasera\n"
                          "Ejemplos: FRN-DSK280 · FRN-LIQ-DOT4 · FRN-PST215",
        "imagen_contiene": "frenos",
        "consulta_sql": (
            "SELECT p.codigo, p.nombre, p.marca AS extra1, "
            "COALESCE(d.nombre, s.codigo_dependencia) AS dependencia, "
            "COALESCE(s.cantidad, 0) AS cantidad "
            "FROM productos AS p "
            "LEFT JOIN stock_productos AS s ON s.codigo_producto::text = p.codigo::text "
            "LEFT JOIN dependencias AS d ON d.codigo::text = s.codigo_dependencia::text "
            "WHERE p.categoria = :q1 AND p.nombre ILIKE '%' || :q2 || '%' AND "
            "p.marca ILIKE '%' || :q3 || '%'"
        ),
        "usar_consulta_personalizada": False,
    },
    {
        "nombre": "Aceites y filtros",
        "descripcion": "Lubricantes, filtros de aceite y de aire.",
        "tabla_origen": "productos",
        "campo_codigo": "codigo",
        "campo_nombre": "nombre",
        "campo_extra1": "marca",
        "campo_categoria": "categoria",
        "valor_categoria": "ACEITES_FILTROS",
        "metodo_busqueda": "multiple",
        "orden": 4,
        "ayuda_busqueda": "Buscá un lubricante o filtro por cualquiera de estos criterios:\n"
                          "• Código: ACE-5W30\n"
                          "• Nombre: aceite 5W-30, filtro de aire\n"
                          "• Detalle: sintético, diésel, gasolina\n"
                          "Ejemplos: ACE-15W40 · FIL-ACE-004 · FIL-AIR-118",
        "imagen_contiene": "aceite",
        "consulta_sql": (
            "SELECT p.codigo, p.nombre, p.marca AS extra1, "
            "COALESCE(d.nombre, s.codigo_dependencia) AS dependencia, "
            "COALESCE(s.cantidad, 0) AS cantidad "
            "FROM productos AS p "
            "LEFT JOIN stock_productos AS s ON s.codigo_producto::text = p.codigo::text "
            "LEFT JOIN dependencias AS d ON d.codigo::text = s.codigo_dependencia::text "
            "WHERE p.categoria = :q1 AND p.nombre ILIKE '%' || :q2 || '%' AND "
            "p.marca ILIKE '%' || :q3 || '%'"
        ),
        "usar_consulta_personalizada": False,
    },
    {
        "nombre": "Búsqueda general",
        "descripcion": "Todos los repuestos sin filtrar por tipo.",
        "tabla_origen": "productos",
        "campo_codigo": "codigo",
        "campo_nombre": "nombre",
        "campo_extra1": "marca",
        "campo_categoria": "",
        "valor_categoria": "",
        "metodo_busqueda": "multiple",
        "orden": 5,
        "ayuda_busqueda": "Buscá en todo el catálogo por cualquiera de estos criterios:\n"
                          "• Código: el código exacto del repuesto\n"
                          "• Nombre: descripción del producto\n"
                          "• Detalle: marca, modelo o característica\n"
                          "Podés combinar los tres campos a la vez para afinar el resultado.",
        "imagen_contiene": "repuestos",
        "consulta_sql": (
            "SELECT p.codigo, p.nombre, p.marca AS extra1, "
            "COALESCE(d.nombre, s.codigo_dependencia) AS dependencia, "
            "COALESCE(s.cantidad, 0) AS cantidad "
            "FROM productos AS p "
            "LEFT JOIN stock_productos AS s ON s.codigo_producto::text = p.codigo::text "
            "LEFT JOIN dependencias AS d ON d.codigo::text = s.codigo_dependencia::text "
            "WHERE (p.codigo ILIKE '%' || :q1 || '%' OR "
            "p.nombre ILIKE '%' || :q2 || '%' OR "
            "p.marca ILIKE '%' || :q3 || '%')"
        ),
        "usar_consulta_personalizada": False,
    },
]

# Categorías plantilla de la carga anterior, que se reemplazan al usar --forzar.
VECIAS_SLUGS = [
    "repuestos-por-codigo-exacto",
    "repuestos-por-segmento",
    "busqueda-multiple",
]


def _imagen_por_titulo(texto):
    from django.apps import apps as dj_apps

    modelo = dj_apps.get_model("wagtailimages", "Image")
    return modelo.objects.filter(title__icontains=texto).order_by("pk").first()


def _imagen_por_pk(pk):
    from django.apps import apps as dj_apps

    modelo = dj_apps.get_model("wagtailimages", "Image")
    return modelo.objects.filter(pk=pk).first()


# Imágenes del sitio que se asignan a cada categoría (patrón → pk de Image).
# Se usan sólo como valor inicial: si el administrador ya le puso otra foto,
# no se reemplaza.
IMAGENES_CATEGORIA = {
    "Neumáticos": 4,          # Galería - Taller principal
    "Baterías": 6,            # Galería - Zona de diagnóstico
    "Frenos": 5,              # Galería - Equipo técnico
    "Aceites y filtros": 7,   # Galería - Vehículo en servicio
    "Búsqueda general": 3,    # Historia - Taller de reparación
}


class Command(BaseCommand):
    help = "Carga los datos de ejemplo del Catálogo ERP (página + config + categorías)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--forzar", action="store_true",
            help="Recrea/actualiza la configuración y las categorías aunque ya existan.",
        )

    def handle(self, *args, **options):
        forzar = options["forzar"]
        verbo = self.stdout.write

        # 1) Página pública -------------------------------------------------
        padre = AutomotivePage.objects.first()
        if padre is None:
            self.stderr.write("No se encontró una página raíz (AutomotivePage).")
            return

        pagina = CatalogoERPPage.objects.filter(slug="catalogo").first()
        if pagina is None:
            pagina = CatalogoERPPage(
                title="Catálogo",
                slug="catalogo",
                introduccion=INTRO,
            )
            padre.add_child(instance=pagina)
            pagina.save_revision().publish()
            verbo(f"Página creada: {pagina.url_path}")
        elif forzar:
            pagina.introduccion = INTRO
            pagina.save_revision().publish()
            verbo(f"Página actualizada: {pagina.url_path}")

        # 2) Configuración ERP (inactiva y de ejemplo) ----------------------
        config, creada = ConfiguracionERP.objects.get_or_create(
            host="localhost",
            defaults=dict(
                puerto=5432,
                nombre_bd="erp_servicios",
                usuario="usuario_lectura",
                password="password_de_ejemplo",
                schema="public",
                activo=False,
            ),
        )
        verbo(("Creada" if creada else "Ya existía") + f" Configuración ERP: {config}")

        # 3) Categorías -----------------------------------------------------
        if forzar:
            for slug_viejo in VECIAS_SLUGS:
                n = CategoriaProductoERP.objects.filter(slug=slug_viejo).delete()[0]
                if n:
                    verbo(f"Categoría anterior eliminada: {slug_viejo}")

        for dato in CATEGORIAS:
            slug = slugify(dato["nombre"])[:160]
            obj, creada = CategoriaProductoERP.objects.get_or_create(
                slug=slug,
                defaults={k: v for k, v in dato.items() if k != "imagen_contiene"},
            )
            if forzar and not creada:
                for campo, valor in dato.items():
                    if campo != "imagen_contiene":
                        setattr(obj, campo, valor)
            # Imagen: se asigna en la primera carga la foto por defecto del sitio;
            # si el administrador ya subió otra, se respeta.
            if not obj.imagen_id:
                img = _imagen_por_pk(IMAGENES_CATEGORIA.get(obj.nombre)) or _imagen_por_titulo(
                    dato.get("imagen_contiene", "")
                )
                if img:
                    obj.imagen = img
            obj.save()
            verbo(("Creada" if creada else "Actualizada") + f" categoría: {obj.nombre}")

        verbo("" if not forzar else "Listo.")
        verbo("Recordá: la Configuración ERP es de EJEMPLO y está INACTIVA; activala "
              "recién cuando apunte a tu PostgreSQL real (solo lectura).")