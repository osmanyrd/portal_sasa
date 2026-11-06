"""Configura el Catálogo ERP contra el PostgreSQL real de SASA.

Crea o actualiza (con ``--forzar``):

  - La ``ConfiguracionERP`` apuntando al ERP real, con la contraseña cifrada.
  - Las categorías de productos con su consulta de disponibilidad por UEB.
  - La página pública del catálogo, si no existe.

La contraseña **no** se guarda en el código: se toma de ``--password`` o de la
variable de entorno ``ERP_PASSWORD``.

Ejemplos::

    python manage.py configurar_erp_real --probar
    python manage.py configurar_erp_real --forzar --buscar 185
    python manage.py configurar_erp_real --listar
    set ERP_PASSWORD=... && python manage.py configurar_erp_real --forzar
"""

import os
import re

from django.core.management.base import BaseCommand, CommandError
from django.utils.text import slugify

from apps.automotive.models import AutomotivePage
from apps.catalogo_erp.models import (
    CatalogoERPPage,
    CategoriaProductoERP,
    ConfiguracionERP,
)
from apps.catalogo_erp.services import CatalogoError, buscar_productos, probar_conexion

# Parámetros del ERP real (la contraseña llega por --password / ERP_PASSWORD).
ERP_HOST = os.environ.get("ERP_HOST", "192.168.52.10")
ERP_PUERTO = int(os.environ.get("ERP_PUERTO", "5432"))
ERP_BD = os.environ.get("ERP_BD", "distra-sasa")
ERP_USUARIO = os.environ.get("ERP_USUARIO", "zeolides")

INTRO = """
<p>Consultá en línea la disponibilidad de nuestros productos en cada
dependencia. Los datos provienen directo de nuestro sistema ERP.</p>
""".strip()

# Solo codes de naturaleza válidos pasan a la consulta (se incrustan en el SQL
# como literales, no como parámetros, así que se validan).
CODIGO_NATURALEZA = re.compile(r"^[A-Z0-9_/]{1,20}$")

# Plantilla de disponibilidad por UEB (dependencia). Columnas requeridas por el
# catálogo: codigo, nombre, dependencia, cantidad; extra1 = naturaleza.
# El término único :q se busca a la vez en el número de pieza y en la
# denominación. Se usa NULLIF para poder dejarlo vacío y, además, la consulta
# se envuelve con un filtro por provincia (ver servicios._filtrar_por_provincia),
# de modo que el LIMIT se aplica ya filtrado.
PLANTILLA_CONSULTA = """
SELECT
  ind.numeropieza AS codigo,
  COALESCE(ind.denominacion, '') AS nombre,
  et.denominacion AS dependencia,
  COALESCE(SUM(pr.disponible), 0) AS cantidad,
  nat.denominacion AS extra1
FROM mod_logistica.dat_producto pr
INNER JOIN mod_datosmaestros.nom_indicador ind
  ON pr.idindicador = ind.idindicador
INNER JOIN mod_datosmaestros.nom_naturaleza nat
  ON ind.idnaturaleza = nat.idnaturaleza
INNER JOIN mod_estructuracomp.v_dametodasestructuras et
  ON (pr.idestructuracomun = et.idestructura AND et.idorgano = -2)
INNER JOIN mod_estructuracomp.v_dametodasestructuras dep
  ON (pr.idestructura = dep.idestructura AND dep.idorgano = -1)
INNER JOIN mod_logdistribucion.conf_depositopublico cdp
  ON cdp.iddeposito = dep.idestructura
WHERE
  NOT (pr.disponible = 0)
  AND (
    NULLIF(:q, '') IS NOT NULL
    AND (
      ind.numeropieza ILIKE '%' || :q || '%'
      OR COALESCE(ind.denominacion, '') ILIKE '%' || :q || '%'
    )
  ){filtro_naturaleza}
GROUP BY
  et.denominacion,
  nat.denominacion,
  ind.numeropieza,
  ind.denominacion
ORDER BY
  ind.numeropieza,
  et.denominacion
""".strip()


def consulta_disponibilidad(naturalezas=(), limite=None):
    """Arma la consulta de disponibilidad filtrando por códigos de naturaleza.

    Sin ``naturalezas`` la búsqueda es general sobre todo el catálogo.
    """
    for codigo in naturalezas:
        if not CODIGO_NATURALEZA.match(codigo):
            raise CommandError(f"Código de naturaleza inválido: {codigo!r}")
    if naturalezas:
        lista = ", ".join(f"'{codigo}'" for codigo in naturalezas)
        filtro = f"\n  AND nat.codigo IN ({lista})"
    else:
        filtro = ""
    consulta = PLANTILLA_CONSULTA.format(filtro_naturaleza=filtro)
    if limite:
        consulta += f"\nLIMIT {int(limite)}"
    return consulta


AYUDA_BASE = (
    "Elegí la provincia y escribí parte del número de pieza o de la descripción "
    "del producto (no distingue mayúsculas de minúsculas).\n"
    "• Un solo campo busca a la vez en el código y en la descripción.\n"
    "• Ej.: 185, 185/70, R18, 12V60, 20W-50, PASTILLAS DE FRENO.\n"
    "Se muestra la cantidad disponible solo en las agencias de la provincia "
    "elegida. Se listan hasta 50 dependencias por consulta."
)

# (nombre, códigos de naturaleza, descripción, ayuda, límite, orden)
DEFINICION_CATEGORIAS = [
    (
        "Neumáticos",
        ["NEU"],
        "Cubiertas para autos, utilitarios y camiones, con stock por dependencia.",
        (
            "Escribí parte de la medida del neumático (con o sin barras):\n"
            "• 185  → todos los neumáticos cuya medida contiene 185\n"
            "• 185/70\n"
            "• R18\n"
            "• MTLD185/65R14\n" + AYUDA_BASE
        ),
        None,
        1,
    ),
    (
        "Neumáticos de motocicleta",
        ["NMT"],
        "Cubiertas para motocicletas y mototaxis.",
        (
            "Escribí parte de la medida (ej.: 3.00-17, 110-70):\n"
            "• 110-70\n"
            "• 3.00-17\n" + AYUDA_BASE
        ),
        None,
        2,
    ),
    (
        "Baterías",
        ["BAT", "BMT"],
        "Baterías para autos, camiones y motocicletas.",
        (
            "Escribí parte del modelo o de la capacidad:\n"
            "• 12V60\n"
            "• 95AH\n"
            "• 6N4\n" + AYUDA_BASE
        ),
        None,
        3,
    ),
    (
        "Aceites y lubricantes",
        ["GYL"],
        "Aceites, grasas, líquidos de freno y refrigerantes para vehículos.",
        (
            "Escribí parte del código o de la descripción:\n"
            "• 20W-50\n"
            "• RADICOOL\n"
            "• LIQUIDO DE FRENO\n" + AYUDA_BASE
        ),
        None,
        4,
    ),
    (
        "Filtros",
        ["FIL"],
        "Filtros de aceite, aire, combustible y habitáculo.",
        (
            "Escribí parte del código o de la descripción:\n"
            "• MVFL03032\n"
            "• FILTRO DE AIRE\n" + AYUDA_BASE
        ),
        None,
        5,
    ),
    (
        "Frenos",
        ["FRE"],
        "Pastillas, discos y componentes del sistema de frenos.",
        (
            "Escribí parte del código o de la descripción:\n"
            "• PASTILLAS DE FRENO\n"
            "• CABLE DE FRENO\n" + AYUDA_BASE
        ),
        None,
        6,
    ),
    (
        "Sistema de inyección",
        ["INY"],
        "Inyectores, bombas y piezas del sistema de inyección.",
        (
            "Escribí parte del código de pieza (ej.: 0430211052CEC):\n" + AYUDA_BASE
        ),
        None,
        7,
    ),
    (
        "Accesorios",
        ["ACC"],
        "Accesorios y equipamiento para vehículos.",
        (
            "Escribí parte del código o de la descripción:\n"
            "• PROBADOR\n"
            "• M123001\n" + AYUDA_BASE
        ),
        None,
        8,
    ),
    (
        "Búsqueda general",
        [],
        "Buscá cualquier producto del ERP por código o descripción.",
        (
            "Buscá por código o descripción en todo el catálogo:\n"
            "• 185\n"
            "• 12V60\n"
            "• 20W-50\n"
            "Los productos se listan hasta 200 dependencias por consulta."
        ),
        200,
        9,
    ),
]


def categoria_por_defecto(nombre, naturalezas, descripcion, ayuda, limite, orden):
    """Arma el diccionario de campos de una categoría del catálogo."""
    return {
        "nombre": nombre,
        "descripcion": descripcion,
        "ayuda_busqueda": ayuda,
        "tabla_origen": "dat_producto",
        "campo_codigo": "numeropieza",
        "campo_nombre": "denominacion",
        "consulta_sql": consulta_disponibilidad(naturalezas, limite=limite),
        "usar_consulta_personalizada": True,
        "metodo_busqueda": CategoriaProductoERP.METODO_MULTIPLE,
        "orden": orden,
        "activo": True,
    }


class Command(BaseCommand):
    help = "Configura el Catálogo ERP contra el PostgreSQL real (config + categorías)."

    def add_arguments(self, parser):
        parser.add_argument("--host", default=ERP_HOST, help=f"Host del ERP (def. {ERP_HOST}).")
        parser.add_argument("--puerto", type=int, default=ERP_PUERTO, help="Puerto PostgreSQL.")
        parser.add_argument("--nombre-bd", default=ERP_BD, help="Nombre de la base de datos.")
        parser.add_argument("--usuario", default=ERP_USUARIO, help="Usuario de solo lectura.")
        parser.add_argument(
            "--password",
            default=os.environ.get("ERP_PASSWORD", ""),
            help="Contraseña del ERP (o variable de entorno ERP_PASSWORD).",
        )
        parser.add_argument(
            "--inactivo", action="store_true",
            help="Guarda la configuración sin activarla.",
        )
        parser.add_argument(
            "--forzar", action="store_true",
            help="Actualiza los datos aunque la configuración ya exista.",
        )
        parser.add_argument(
            "--probar", action="store_true",
            help="Prueba la conexión al ERP al terminar.",
        )
        parser.add_argument(
            "--buscar", metavar="PIEZA", default="",
            help="Ejecuta una búsqueda de prueba (ej.: --buscar 185) y muestra el resultado.",
        )
        parser.add_argument(
            "--provincia", metavar="PROV", default="LH",
            help="Provincia para --buscar (código PR, LH… o pk; def. LH).",
        )
        parser.add_argument(
            "--en-todas", action="store_true",
            help="Con --buscar, prueba el término en todas las categorías.",
        )
        parser.add_argument(
            "--listar", action="store_true",
            help="Muestra las categorías que se van a configurar y termina.",
        )

    def handle(self, *args, **options):
        verbo = self.stdout.write

        if options["listar"]:
            self._listar()
            return

        config = ConfiguracionERP.obtener()
        if config is None:
            config = ConfiguracionERP()
        elif not options["forzar"]:
            verbo(
                f"Ya existe una configuración ({config}); se usa --forzar para actualizarla. "
                "Las categorías se sincronizan igual."
            )

        cambios = {
            "host": options["host"],
            "puerto": options["puerto"],
            "nombre_bd": options["nombre_bd"],
            "usuario": options["usuario"],
            "activo": not options["inactivo"],
        }
        for campo, valor in cambios.items():
            setattr(config, campo, valor)
        if options["password"]:
            # save() la cifra con Fernet; nunca se guarda en claro.
            config.password = options["password"]
        elif not config.pk:
            raise CommandError(
                "Falta la contraseña: pasala con --password o definí ERP_PASSWORD."
            )
        config.save()
        verbo(f"Configuración guardada: {config} (activa={config.activo})")

        pagina = self._asegurar_pagina()
        categorias = self._sincronizar_categorias()

        if options["probar"] or options["buscar"]:
            self._verificar(config, categorias, options)

        if pagina:
            verbo(f"Página del catálogo: {pagina.url}")

    def _listar(self):
        self.stdout.write("Categorías que se configuran:")
        for nombre, naturalezas, desc, ayuda, limite, orden in DEFINICION_CATEGORIAS:
            etiqueta = ", ".join(naturalezas) if naturalezas else "todo el catálogo"
            self.stdout.write(f"  {orden}. {nombre} [{etiqueta}]")

    def _sincronizar_categorias(self):
        """Crea o actualiza las categorías y desactiva las de ejemplo."""
        verbo = self.stdout.write
        guardadas = []
        for definicion in DEFINICION_CATEGORIAS:
            nombre, naturalezas, desc, ayuda, limite, orden = definicion
            campos = categoria_por_defecto(nombre, naturalezas, desc, ayuda, limite, orden)
            categoria, creada = CategoriaProductoERP.objects.get_or_create(
                slug=slugify(nombre)[:160],
                defaults=campos,
            )
            if not creada:
                for campo, valor in campos.items():
                    setattr(categoria, campo, valor)
                categoria.save()
            verbo(("Creada " if creada else "Actualizada ") + f"categoría: {categoria}")
            guardadas.append(categoria)

        # Las categorías de ejemplo apuntan a tablas inexistentes en el ERP real.
        sobrantes = CategoriaProductoERP.objects.exclude(
            slug__in=[c.slug for c in guardadas]
        )
        for categoria in sobrantes:
            categoria.activo = False
            categoria.save(update_fields=["activo"])
            verbo(f"Desactivada categoría de ejemplo: {categoria}")
        return guardadas

    def _asegurar_pagina(self):
        """Crea la página pública del catálogo si todavía no existe."""
        pagina = CatalogoERPPage.objects.filter(slug="catalogo").first()
        if pagina is not None:
            return pagina
        padre = AutomotivePage.objects.first()
        if padre is None:
            self.stderr.write("No se encontró una página raíz (AutomotivePage); omito la página.")
            return None
        pagina = CatalogoERPPage(title="Catálogo", slug="catalogo", introduccion=INTRO)
        padre.add_child(instance=pagina)
        pagina.save_revision().publish()
        return pagina

    def _verificar(self, config, categorias, options):
        """Prueba conexión y, si se pidió, ejecuta búsquedas reales."""
        ok, mensaje = probar_conexion(config)
        (self.stdout.write if ok else self.stderr.write)(f"Conexión: {mensaje}")
        if not ok:
            return
        termino = options["buscar"]
        if not termino:
            return
        objetivos = categorias if options["en_todas"] else categorias[:1]
        provincia = options["provincia"]
        for categoria in objetivos:
            try:
                productos = buscar_productos(categoria, {"q": termino}, provincia)
            except CatalogoError as exc:
                self.stderr.write(f"[{categoria.nombre}] '{termino}': FALLÓ - {exc}")
                continue
            self.stdout.write(
                f"[{categoria.nombre}] '{termino}' en {provincia}: {len(productos)} producto(s)"
            )
            for producto in productos[:5]:
                self.stdout.write(f"  - {producto['codigo']} | {producto['nombre']}")
                for disp in producto["disponibilidad"]:
                    self.stdout.write(f"      {disp['dependencia']}: {disp['cantidad']}")
