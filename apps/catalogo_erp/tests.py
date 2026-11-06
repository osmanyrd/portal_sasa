"""Pruebas del catálogo ERP.

Incluye pruebas unitarias (no necesitan el ERP) y una prueba de extremo a
extremo contra el ERP real que se omite si no hay contraseña en la variable de
entorno ``ERP_PASSWORD``::

    set ERP_PASSWORD=... && python manage.py test apps.catalogo_erp
"""

import json
import os
import socket
from decimal import Decimal
from unittest import mock

import psycopg2
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.files.base import ContentFile
from django.core.management.base import CommandError
from django.test import TestCase
from django.urls import reverse
from psycopg2 import sql

from apps.catalogo_erp import crypto
from apps.catalogo_erp.management.commands.configurar_erp_real import (
    DEFINICION_CATEGORIAS,
    consulta_disponibilidad,
)
from apps.catalogo_erp.models import CategoriaProductoERP, ConfiguracionERP
from apps.catalogo_erp.provincias import (
    CODIGO_NACIONAL,
    UEB_ASIGNADAS,
    UEB_SIN_PROVINCIA,
    _dependencias_de,
    es_nacional,
    normalizar,
    opciones_provincia,
    provincias_con_ueb,
    resolver_uebs,
    uebs_nacionales,
)
from apps.catalogo_erp.services import (
    CatalogoError,
    _agrupar,
    _cantidad,
    _consulta_personalizada,
    _error_amigable,
    _filtrar_por_provincia,
    abrir_conexion,
    buscar_productos,
    construir_consulta,
)
from apps.mapa.models import Dependencia, Provincia

HOST_ERP = os.environ.get("ERP_HOST", "192.168.52.10")
PUERTO_ERP = int(os.environ.get("ERP_PUERTO", "5432"))
PASSWORD_ERP = os.environ.get("ERP_PASSWORD", "")
User = get_user_model()

CONSULTA_NEUMATICOS = (
    "SELECT ind.numeropieza AS codigo, "
    "COALESCE(ind.denominacion, '') AS nombre, "
    "et.denominacion AS dependencia, "
    "COALESCE(SUM(pr.disponible), 0) AS cantidad, "
    "nat.denominacion AS extra1 "
    "FROM mod_logistica.dat_producto pr "
    "INNER JOIN mod_datosmaestros.nom_indicador ind "
    "ON pr.idindicador = ind.idindicador "
    "INNER JOIN mod_datosmaestros.nom_naturaleza nat "
    "ON ind.idnaturaleza = nat.idnaturaleza "
    "INNER JOIN mod_estructuracomp.v_dametodasestructuras et "
    "ON (pr.idestructuracomun = et.idestructura AND et.idorgano = -2) "
    "INNER JOIN mod_estructuracomp.v_dametodasestructuras dep "
    "ON (pr.idestructura = dep.idestructura AND dep.idorgano = -1) "
    "INNER JOIN mod_logdistribucion.conf_depositopublico cdp "
    "ON cdp.iddeposito = dep.idestructura "
    "WHERE NOT (pr.disponible = 0) AND nat.codigo = 'NEU' "
    "AND NULLIF(:q, '') IS NOT NULL "
    "AND (ind.numeropieza ILIKE '%' || :q || '%' "
    "OR COALESCE(ind.denominacion, '') ILIKE '%' || :q || '%') "
    "GROUP BY et.denominacion, nat.denominacion, ind.numeropieza, ind.denominacion "
    "ORDER BY ind.numeropieza, et.denominacion"
)


def _erp_alcanzable():
    """Comprueba rápido si se puede llegar al ERP, para omitir la prueba E2E."""
    try:
        with socket.create_connection((HOST_ERP, PUERTO_ERP), timeout=3):
            return True
    except OSError:
        return False


def _imagen(nombre="test.png"):
    """Crea una imagen Wagtail mínima (mapa_dependencia.foto es obligatorio)."""
    from io import BytesIO

    from PIL import Image as PILImage
    from wagtail.images import get_image_model

    buffer = BytesIO()
    PILImage.new("RGB", (1, 1), "white").save(buffer, format="PNG")
    imagen = get_image_model()(title=nombre)
    imagen.file.save(nombre, ContentFile(buffer.getvalue()), save=False)
    # Con save=False Django no calcula las dimensiones del archivo.
    imagen.width, imagen.height = 1, 1
    imagen.save()
    return imagen


class _Categoria:
    """Categoría falsa para probar la construcción de consultas sin la BD."""

    def __init__(self, **kwargs):
        self.slug = "prueba"
        self.activo = True
        self.usar_consulta_personalizada = False
        self.consulta_sql = ""
        self.metodo_busqueda = CategoriaProductoERP.METODO_MULTIPLE
        self.tabla_origen = "dat_producto"
        self.campo_codigo = "numeropieza"
        self.campo_nombre = "denominacion"
        self.campo_extra1 = ""
        self.campo_extra2 = ""
        self.campo_extra3 = ""
        self.campo_categoria = ""
        self.valor_categoria = ""
        self.__dict__.update(kwargs)


class _Config:
    """Configuración ERP falsa."""

    def __init__(self, **kwargs):
        self.host = HOST_ERP
        self.puerto = PUERTO_ERP
        self.nombre_bd = "distra-sasa"
        self.usuario = "zeolides"
        self.password_plana = PASSWORD_ERP
        self.schema = "public"
        self.tabla_stock = "stock_productos"
        self.campo_stock_codigo = "codigo_producto"
        self.campo_stock_dependencia = "codigo_dependencia"
        self.campo_stock_cantidad = "cantidad"
        self.tabla_dependencias = "dependencias"
        self.campo_dep_codigo = "codigo"
        self.campo_dep_nombre = "nombre"
        self.__dict__.update(kwargs)


class CantidadTests(TestCase):
    """``_cantidad`` debe producir algo serializable en JSON."""

    def test_decimal_entero_devuelve_int(self):
        self.assertEqual(_cantidad(Decimal("20.000000")), 20)
        self.assertIsInstance(_cantidad(Decimal("20.000000")), int)

    def test_decimal_con_fraccion_devuelve_float(self):
        self.assertEqual(_cantidad(Decimal("1.5")), 1.5)

    def test_none_y_no_numericos(self):
        self.assertEqual(_cantidad(None), 0)
        self.assertEqual(_cantidad("abc"), 0)
        self.assertEqual(_cantidad(True), 1)

    def test_decimal_nan_no_rompe(self):
        self.assertEqual(_cantidad(Decimal("NaN")), 0)

    def test_texto_numerico(self):
        self.assertEqual(_cantidad("7"), 7)


class AgruparTests(TestCase):
    """``_agrupar`` resuelve columnas por nombre, así que el orden no importa."""

    def test_extras_al_final(self):
        filas = [
            ("185/65R14", "NEUMATICO", "AGENCIA A", Decimal("5"), "NEUMATICOS"),
            ("185/65R14", "NEUMATICO", "AGENCIA B", Decimal("3"), "NEUMATICOS"),
            ("R18", "OTRO", "AGENCIA A", Decimal("1"), "NEUMATICOS"),
        ]
        nombres = ["codigo", "nombre", "dependencia", "cantidad", "extra1"]
        productos = _agrupar(filas, nombres)
        self.assertEqual([p["codigo"] for p in productos], ["185/65R14", "R18"])
        primero = productos[0]
        self.assertEqual(primero["extra1"], "NEUMATICOS")
        self.assertEqual(
            primero["disponibilidad"],
            [
                {"dependencia": "AGENCIA A", "cantidad": 5},
                {"dependencia": "AGENCIA B", "cantidad": 3},
            ],
        )
        # Debe serializarse sin necesitar default=str.
        json.dumps(productos)

    def test_extras_en_medio_orden_historico(self):
        filas = [("FIL-1", "Filtro", "ACEITE", "AGENCIA A", Decimal("7"))]
        nombres = ["codigo", "nombre", "extra1", "dependencia", "cantidad"]
        productos = _agrupar(filas, nombres)
        self.assertEqual(productos[0]["extra1"], "ACEITE")
        self.assertEqual(
            productos[0]["disponibilidad"],
            [{"dependencia": "AGENCIA A", "cantidad": 7}],
        )

    def test_sin_nombres_usa_orden_posicional(self):
        filas = [("FIL-1", "Filtro", "ACEITE", "AGENCIA A", Decimal("2"))]
        productos = _agrupar(filas, [])
        self.assertEqual(productos[0]["extra1"], "ACEITE")
        self.assertEqual(
            productos[0]["disponibilidad"],
            [{"dependencia": "AGENCIA A", "cantidad": 2}],
        )

    def test_suma_por_dependencia_y_salta_nulos(self):
        filas = [
            ("X", "X", "AGENCIA A", Decimal("1.5")),
            ("X", "X", "AGENCIA A", Decimal("2.5")),
            (None, "sin codigo", "AGENCIA B", Decimal("9")),
        ]
        productos = _agrupar(filas, ["codigo", "nombre", "dependencia", "cantidad"])
        self.assertEqual(len(productos), 1)
        self.assertEqual(productos[0]["disponibilidad"][0]["cantidad"], 4)


class ConsultaPersonalizadaTests(TestCase):
    """Validación y escapado de la consulta SQL que escribe el administrador."""

    def test_escapa_porcentajes_literales(self):
        categoria = _Categoria(
            usar_consulta_personalizada=True,
            consulta_sql=(
                "SELECT a AS codigo, b AS nombre, c AS dependencia, d AS cantidad "
                "FROM t WHERE b ILIKE '%' || :q1 || '%'"
            ),
        )
        consulta, params = _consulta_personalizada(categoria, {"q1": "185"})
        # El % literal del LIKE se envía como %% y psycopg2 lo reduce a un solo %.
        self.assertIn("'%%' || %s || '%%'", consulta)
        self.assertEqual(params, ["185"])

    def test_solo_permite_select(self):
        categoria = _Categoria(
            usar_consulta_personalizada=True,
            consulta_sql="DROP TABLE productos",
        )
        with self.assertRaises(CatalogoError):
            _consulta_personalizada(categoria, {"q1": "x"})

    def test_rechaza_punto_y_coma(self):
        categoria = _Categoria(
            usar_consulta_personalizada=True,
            consulta_sql=(
                "SELECT 1 AS codigo, 2 AS nombre, 3 AS dependencia, 4 AS cantidad; "
                "DROP TABLE x"
            ),
        )
        with self.assertRaises(CatalogoError):
            _consulta_personalizada(categoria, {"q1": "x"})

    def test_agrega_limit_si_no_existe(self):
        categoria = _Categoria(
            usar_consulta_personalizada=True,
            consulta_sql=(
                "SELECT 1 AS codigo, 2 AS nombre, 3 AS dependencia, 4 AS cantidad "
                "WHERE 1 = :q1"
            ),
        )
        consulta, _ = _consulta_personalizada(categoria, {"q1": "1"})
        self.assertIn("LIMIT 50", consulta)

    def test_respeta_limit_propio(self):
        categoria = _Categoria(
            usar_consulta_personalizada=True,
            consulta_sql=(
                "SELECT 1 AS codigo, 2 AS nombre, 3 AS dependencia, 4 AS cantidad LIMIT 7"
            ),
        )
        consulta, _ = _consulta_personalizada(categoria, {"q1": "1"})
        self.assertIn("LIMIT 7", consulta)
        self.assertNotIn("LIMIT 50", consulta)

    def test_exige_al_menos_un_criterio(self):
        categoria = _Categoria(
            usar_consulta_personalizada=True,
            consulta_sql=(
                "SELECT 1 AS codigo, 2 AS nombre, 3 AS dependencia, 4 AS cantidad "
                "WHERE numeropieza LIKE '%' || :q1 || '%'"
            ),
        )
        with self.assertRaises(CatalogoError):
            _consulta_personalizada(categoria, {"q1": "   "})

    def test_cada_placeholder_se_usa_una_vez(self):
        categoria = _Categoria(
            usar_consulta_personalizada=True,
            consulta_sql=(
                "SELECT 1 AS codigo, 2 AS nombre, 3 AS dependencia, 4 AS cantidad "
                "WHERE a = :q1 AND b = :q2"
            ),
        )
        consulta, params = _consulta_personalizada(categoria, {"q1": "1", "q2": "2"})
        self.assertEqual(params, ["1", "2"])
        self.assertEqual(consulta.count("%s"), 2)

    def test_placeholder_repetido_se_parametriza_en_cada_uso(self):
        categoria = _Categoria(
            usar_consulta_personalizada=True,
            consulta_sql=(
                "SELECT 1 AS codigo, 2 AS nombre, 3 AS dependencia, 4 AS cantidad "
                "WHERE (NULLIF(:q1, '') IS NOT NULL AND a ILIKE '%' || :q1 || '%')"
            ),
        )
        consulta, params = _consulta_personalizada(categoria, {"q1": "185"})
        self.assertEqual(params, ["185", "185"])
        self.assertEqual(consulta.count("%s"), 2)
        self.assertNotIn(":q1", consulta)

    def test_placeholder_repetido_con_termino_vacio_no_filtra(self):
        categoria = _Categoria(
            usar_consulta_personalizada=True,
            consulta_sql=(
                "SELECT 1 AS codigo, 2 AS nombre, 3 AS dependencia, 4 AS cantidad "
                "WHERE (NULLIF(:q1, '') IS NOT NULL AND a ILIKE '%' || :q1 || '%') "
                "AND b = :q2"
            ),
        )
        consulta, params = _consulta_personalizada(categoria, {"q1": "", "q2": "x"})
        self.assertEqual(params, ["", "", "x"])
        self.assertNotIn(":q1", consulta)

    def test_construir_consulta_delega_en_la_personalizada(self):
        categoria = _Categoria(
            usar_consulta_personalizada=True,
            consulta_sql=(
                "SELECT 1 AS codigo, 2 AS nombre, 3 AS dependencia, 4 AS cantidad "
                "WHERE numeropieza LIKE '%' || :q1 || '%'"
            ),
        )
        consulta, params = construir_consulta(categoria, _Config(), {"q1": "185"})
        self.assertEqual(params, ["185"])
        self.assertIsInstance(consulta, str)

    def test_placeholder_q_se_expande_una_vez_por_aparicion(self):
        categoria = _Categoria(
            usar_consulta_personalizada=True,
            consulta_sql=(
                "SELECT 1 AS codigo, 2 AS nombre, 3 AS dependencia, 4 AS cantidad "
                "WHERE (NULLIF(:q, '') IS NOT NULL AND a ILIKE '%' || :q || '%' "
                "OR b ILIKE '%' || :q || '%')"
            ),
        )
        consulta, params = _consulta_personalizada(categoria, {"q": "185"})
        self.assertEqual(params, ["185", "185", "185"])
        self.assertNotIn(":q", consulta)
        self.assertEqual(consulta.count("%s"), 3)

    def test_placeholder_q_vacio_pide_criterio(self):
        categoria = _Categoria(
            usar_consulta_personalizada=True,
            consulta_sql="SELECT 1 AS codigo WHERE NULLIF(:q, '') IS NOT NULL",
        )
        with self.assertRaises(CatalogoError):
            _consulta_personalizada(categoria, {"q": "   "})

    def test_q_no_se_confunde_con_q1(self):
        categoria = _Categoria(
            usar_consulta_personalizada=True,
            consulta_sql="SELECT 1 AS codigo WHERE a = :q1 AND b = :q",
        )
        _consulta, params = _consulta_personalizada(categoria, {"q": "x", "q1": "y"})
        self.assertEqual(params, ["y", "x"])

    def test_filtro_por_provincia_mueve_el_limit(self):
        consulta, params = _filtrar_por_provincia(
            "SELECT codigo, dependencia, cantidad FROM x LIMIT 50", [], ["AGENCIA A", "AGENCIA B"]
        )
        partes = consulta._wrapped
        # El LIMIT interno se elimina para no truncar filas de otras provincias.
        self.assertNotIn("LIMIT", str(partes[0]))
        # ... y el externo queda con su propio parámetro al final.
        self.assertEqual(params, ["AGENCIA A", "AGENCIA B", 50])
        self.assertIsInstance(consulta, sql.Composed)
        self.assertIn(sql.Identifier("dependencia"), partes)
        # El IN de UEBs va en un Composed anidado; el único Placeholder suelto
        # es el del LIMIT externo (las 2 UEBs viajan en params).
        self.assertEqual(sum(isinstance(p, sql.Placeholder) for p in partes), 1)


    def test_filtro_por_provincia_no_interpola_uebs(self):
        consulta, params = _filtrar_por_provincia(
            "SELECT codigo, dependencia FROM x", [], ["A'; DROP TABLE x--"]
        )
        self.assertEqual(params, ["A'; DROP TABLE x--", 50])
        for parte in consulta._wrapped:
            self.assertNotIn("DROP TABLE", str(parte))

    def test_filtro_por_provincia_limita_productos_no_filas(self):
        """Con muchas UEBs (opción nacional) el tope debe ser de productos.

        Si el LIMIT se aplicara a las filas producto×UEB, la opción nacional
        devolvería menos productos que una provincia con pocas agencias.
        """
        consulta, _params = _filtrar_por_provincia(
            "SELECT codigo, dependencia, cantidad FROM x LIMIT 50", [], ["A", "B"]
        )
        # quote_ident necesita una conexión real; sin ella devolvemos el nombre tal cual.
        with mock.patch("psycopg2.extensions.quote_ident", lambda s, ctx=None: s):
            texto = consulta.as_string(None)
        # Se eligen códigos distintos y luego se recuperan todas sus filas.
        self.assertIn("DISTINCT", texto)
        self.assertIn("INNER JOIN", texto)
        self.assertIn("ORDER BY", texto)
        # El límite externo ya no recorta la consulta interna.
        self.assertNotIn("FROM x LIMIT", texto)

    def test_construir_consulta_con_uebs_envuelve_y_filtra(self):
        categoria = _Categoria(
            usar_consulta_personalizada=True,
            consulta_sql=(
                "SELECT 1 AS codigo, 2 AS nombre, 3 AS dependencia, 4 AS cantidad "
                "WHERE a ILIKE '%' || :q || '%'"
            ),
        )
        consulta, params = construir_consulta(
            categoria, _Config(), {"q": "185"}, uebs=["AGENCIA A", "AGENCIA B"]
        )
        self.assertIsInstance(consulta, sql.Composed)
        self.assertIn(sql.Identifier("dependencia"), consulta._wrapped)
        self.assertEqual(params, ["185", "AGENCIA A", "AGENCIA B", 50])




class ConsultaGeneradaTests(TestCase):
    """La consulta automática exige criterios y parametriza los valores."""

    def test_exige_criterio_en_metodo_multiple(self):
        categoria = _Categoria(metodo_busqueda=CategoriaProductoERP.METODO_MULTIPLE)
        with self.assertRaises(CatalogoError):
            construir_consulta(categoria, _Config(), {"q1": "", "q2": "", "q3": ""})

    def test_codigo_exacto_parametriza(self):
        categoria = _Categoria(
            metodo_busqueda=CategoriaProductoERP.METODO_CODIGO,
            campo_extra1="marca",
        )
        consulta, params = construir_consulta(categoria, _Config(), {"q": "FIL-1"})
        self.assertEqual(params, ["FIL-1"])
        # El valor viaja como parámetro, nunca interpolado en el SQL.
        partes = " ".join(str(parte) for parte in consulta._wrapped)
        self.assertNotIn("FIL-1", partes)
        self.assertIn("marca", partes)


class _ErrorConexion(psycopg2.OperationalError):
    """``OperationalError`` con ``pgcode`` controlable (es de solo lectura)."""

    def __init__(self, mensaje, pgcode=None):
        super().__init__(mensaje)
        self._pgcode = pgcode

    @property
    def pgcode(self):
        return self._pgcode


class ErrorConexionTests(TestCase):
    """Los fallos de conexión deben distinguir causa: red, credenciales o cifrado."""

    def test_credenciales_rechazadas_no_se_reportan_como_red(self):
        exc = _ErrorConexion('FATAL:  password authentication failed for user "x"', "28P01")
        self.assertIn("Credenciales incorrectas", _error_amigable(exc))

    def test_credenciales_rechazadas_sin_pgcode_tambien_se_detectan(self):
        exc = _ErrorConexion('FATAL:  password authentication failed for user "x"')
        self.assertIn("Credenciales incorrectas", _error_amigable(exc))

    def test_timeout_se_reporta_como_red(self):
        exc = psycopg2.OperationalError(
            'connection to server at "192.168.52.10", port 5432 failed: timeout expired'
        )
        self.assertIn("conexión de red", _error_amigable(exc))

    def test_host_inalcanzable_se_reporta_como_red(self):
        exc = psycopg2.OperationalError("could not connect to server: No route to host")
        self.assertIn("conexión de red", _error_amigable(exc))

    def test_sin_contrasena_descifrada_avisa_del_cifrado(self):
        config = _Config(password="gAAAAcifrado", password_plana="")
        with self.assertRaises(CatalogoError) as ctx:
            abrir_conexion(config)
        self.assertIn("SECRET_KEY", str(ctx.exception))

    def test_error_de_criptografia_pasa_verbatim(self):
        self.assertEqual(_error_amigable(CatalogoError("mensaje")), "mensaje")


class ConsultaDisponibilidadTests(TestCase):
    """Generador de consultas por naturaleza del comando de configuración."""

    def test_sin_naturalezas_no_filtra(self):
        consulta = consulta_disponibilidad([])
        self.assertNotIn("nat.codigo IN", consulta)
        # El filtro de texto está siempre, para que exija un criterio.
        self.assertIn("NULLIF(:q, '')", consulta)

    def test_filtra_por_lista_de_codigos(self):
        consulta = consulta_disponibilidad(["BAT", "BMT"])
        self.assertIn("nat.codigo IN ('BAT', 'BMT')", consulta)

    def test_rechaza_codigo_invalido(self):
        for malo in ("neu", "BAT'); DROP TABLE x; --", "con espacio", ""):
            with self.subTest(codigo=malo):
                with self.assertRaises(CommandError):
                    consulta_disponibilidad([malo])

    def test_limite_explicito_se_agrega(self):
        self.assertTrue(consulta_disponibilidad([], limite=200).rstrip().endswith("LIMIT 200"))

    def test_sin_limite_lo_agrega_el_servicio(self):
        self.assertNotIn("LIMIT", consulta_disponibilidad([]).upper())

    def test_cada_aparicion_del_placeholder_se_parametriza(self):
        consulta = consulta_disponibilidad(["NEU"])
        # Con NULLIF + ILIKE el término único :q se usa tres veces (NULLIF,
        # código y descripción); el servicio debe parametrizar las tres.
        categoria = _Categoria(usar_consulta_personalizada=True, consulta_sql=consulta)
        _sql, params = _consulta_personalizada(categoria, {"q": "185"})
        self.assertEqual(params, ["185", "185", "185"])

    def test_todas_las_categorias_generan_sql_valido(self):
        for nombre, naturalezas, _desc, _ayuda, _limite, _orden in DEFINICION_CATEGORIAS:
            with self.subTest(categoria=nombre):
                consulta = consulta_disponibilidad(naturalezas)
                self.assertTrue(consulta.lstrip().upper().startswith("SELECT"))
                self.assertNotIn(";", consulta)
                # La plantilla real ya no usa los tres términos del buscador.
                for termino in (":q1", ":q2", ":q3"):
                    self.assertNotIn(termino, consulta)
                self.assertIn(":q", consulta)


class CryptoTests(TestCase):
    def test_cifrar_descifrar_ida_y_vuelta(self):
        token = crypto.cifrar("secreto-123")
        self.assertTrue(token)
        self.assertNotIn("secreto-123", token)
        self.assertEqual(crypto.descifrar(token), "secreto-123")

    def test_descifrar_basura_devuelve_vacio(self):
        self.assertEqual(crypto.descifrar("no-es-un-token"), "")

    def test_modelo_cifra_la_contrasena(self):
        config = ConfiguracionERP.objects.create(
            host=HOST_ERP,
            puerto=PUERTO_ERP,
            nombre_bd="distra-sasa",
            usuario="zeolides",
            password="clave-en-claro",
            activo=True,
        )
        config.refresh_from_db()
        self.assertNotEqual(config.password, "clave-en-claro")
        self.assertEqual(config.password_plana, "clave-en-claro")

    def test_contrasena_vacia_conserva_la_actual(self):
        config = ConfiguracionERP.objects.create(
            host=HOST_ERP,
            puerto=PUERTO_ERP,
            nombre_bd="distra-sasa",
            usuario="zeolides",
            password="original",
        )
        config.password = ""
        config.save()
        config.refresh_from_db()
        self.assertEqual(config.password_plana, "original")

    def test_solo_una_configuracion_activa(self):
        uno = ConfiguracionERP.objects.create(
            host="a", puerto=5432, nombre_bd="b", usuario="c", password="p", activo=True
        )
        dos = ConfiguracionERP.objects.create(
            host="d", puerto=5432, nombre_bd="e", usuario="f", password="p", activo=True
        )
        uno.refresh_from_db()
        self.assertFalse(uno.activo)
        self.assertTrue(dos.activo)
        self.assertEqual(ConfiguracionERP.activa().pk, dos.pk)


class EndpointTests(TestCase):
    """Validaciones del endpoint público que no tocan el ERP."""

    def setUp(self):
        cache.clear()  # provincias_con_ueb() cachea ~5 min
        self.provincia = Provincia.objects.create(codigo="PR", nombre="Pinar del Río")
        Dependencia.objects.create(
            provincia=self.provincia,
            nombre="Pinar del Rio",
            direccion="",
            foto=_imagen(),
        )
        self.categoria = CategoriaProductoERP.objects.create(
            nombre="Neumaticos",
            metodo_busqueda=CategoriaProductoERP.METODO_MULTIPLE,
            usar_consulta_personalizada=True,
            consulta_sql=(
                "SELECT 1 AS codigo, 2 AS nombre, 3 AS dependencia, 4 AS cantidad "
                "WHERE 1 = :q"
            ),
        )

    def test_categoria_id_invalido(self):
        respuesta = self.client.get("/api/catalogo/buscar/", {"categoria_id": "abc"})
        self.assertEqual(respuesta.status_code, 200)
        self.assertFalse(respuesta.json()["ok"])

    def test_categoria_inexistente(self):
        respuesta = self.client.get("/api/catalogo/buscar/", {"categoria_id": "999999"})
        self.assertEqual(respuesta.status_code, 200)
        self.assertFalse(respuesta.json()["ok"])

    def test_provincia_obligatoria(self):
        respuesta = self.client.get(
            "/api/catalogo/buscar/", {"categoria_id": self.categoria.pk, "q": "185"}
        )
        cuerpo = respuesta.json()
        self.assertFalse(cuerpo["ok"])
        self.assertIn("provincia", cuerpo["error"].lower())

    def test_provincia_inexistente(self):
        respuesta = self.client.get(
            "/api/catalogo/buscar/",
            {"categoria_id": self.categoria.pk, "q": "185", "provincia": "ZZ"},
        )
        cuerpo = respuesta.json()
        self.assertFalse(cuerpo["ok"])
        self.assertIn("provincia", cuerpo["error"].lower())

    def test_termino_obligatorio(self):
        # Con configuración activa el error del término vacío se detecta al
        # construir la consulta, antes de abrir conexión al ERP.
        ConfiguracionERP.objects.create(
            host="127.0.0.1", puerto=5432, nombre_bd="x", usuario="x",
            password="dummy", activo=True,
        )
        respuesta = self.client.get(
            "/api/catalogo/buscar/",
            {"categoria_id": self.categoria.pk, "provincia": "PR"},
        )
        cuerpo = respuesta.json()
        self.assertFalse(cuerpo["ok"])
        self.assertIn("criterio", cuerpo["error"].lower())

    def test_sin_configuracion_activa(self):
        respuesta = self.client.get(
            "/api/catalogo/buscar/",
            {"categoria_id": self.categoria.pk, "q": "185", "provincia": "PR"},
        )
        cuerpo = respuesta.json()
        self.assertFalse(cuerpo["ok"])
        self.assertIn("activ", cuerpo["error"].lower())


class ProvinciasTests(TestCase):
    """Resolución de provincia → UEBs, incluido el acierto por acentos."""

    def setUp(self):
        cache.clear()  # provincias_con_ueb() cachea ~5 min
        self.provincia = Provincia.objects.create(codigo="PR", nombre="Pinar del Río")
        self.otra = Provincia.objects.create(codigo="MTZ", nombre="Matanzas")
        self.foto = _imagen()
        self.dep_pr = Dependencia.objects.create(
            provincia=self.provincia, nombre="Pinar del Rio", direccion="", foto=self.foto
        )
        self.dep_mtz = Dependencia.objects.create(
            provincia=self.otra, nombre="MATANZAS", direccion="", foto=self.foto
        )


    def test_normalizar_ignora_acentos_y_puntuacion(self):
        self.assertEqual(normalizar("Pinar del Rio."), "PINARDELRIO")
        self.assertEqual(normalizar("MATANZÁS"), "MATANZAS")
        self.assertEqual(normalizar("AGENCIA CAIBARIEN"), normalizar("Agencia Caibarién"))


    def test_resuelve_por_codigo(self):
        provincia, uebs = resolver_uebs("pr")
        self.assertEqual(provincia.pk, self.provincia.pk)
        self.assertEqual(uebs, ["Pinar del Rio"])

    def test_resuelve_por_pk(self):
        provincia, _ = resolver_uebs(str(self.provincia.pk))
        self.assertEqual(provincia.pk, self.provincia.pk)

    def test_ueb_explicita_gana_al_nombre(self):
        self.dep_pr.ueb_erp = "Pinar del Rio"
        self.dep_pr.save()
        self.dep_pr.refresh_from_db()
        _provincia, uebs = resolver_uebs("PR")
        self.assertEqual(uebs, ["Pinar del Rio"])

    def test_sin_provincia_devuelve_error(self):
        with self.assertRaises(CatalogoError):
            resolver_uebs("")

    def test_provincia_sin_dependencias_activas(self):
        vacia = Provincia.objects.create(codigo="IJ", nombre="Isla de la Juventud")
        with self.assertRaises(CatalogoError) as ctx:
            resolver_uebs("IJ")
        self.assertIn(vacia.nombre, str(ctx.exception))

    def test_dependencia_inactiva_no_cuenta(self):
        self.dep_pr.activo = False
        self.dep_pr.save()
        with self.assertRaises(CatalogoError):
            resolver_uebs("PR")

    def test_ueb_asignada_se_agrega_a_su_provincia(self):
        """Una UEB sin Dependencia (UEB_ASIGNADAS) entra igual en su provincia."""
        Provincia.objects.create(codigo="LH", nombre="La Habana")
        _provincia, uebs = resolver_uebs("LH")
        esperadas = [ueb for ueb, codigo in UEB_ASIGNADAS.items() if codigo == "LH"]
        self.assertTrue(esperadas)
        self.assertEqual(uebs, esperadas)

    def test_ueb_asignada_no_se_agrega_a_otra_provincia(self):
        _provincia, uebs = resolver_uebs("PR")
        self.assertNotIn("AGENCIA PUERTO HABANA", uebs)
        self.assertEqual(uebs, ["Pinar del Rio"])

    def test_opciones_incluyen_nacional_al_final(self):
        opciones = opciones_provincia()
        codigos = [o["codigo"] for o in opciones]
        self.assertIn(CODIGO_NACIONAL, codigos)
        self.assertEqual(codigos[-1], CODIGO_NACIONAL)

    def test_sin_provincias_no_ofrece_nacional(self):
        Provincia.objects.all().update(activo=False)
        cache.clear()
        self.assertEqual(opciones_provincia(), [])

    def test_nacional_devuelve_todas_las_uebs(self):
        _provincia, uebs = resolver_uebs(CODIGO_NACIONAL)
        for _p, uebs_provincia in provincias_con_ueb():
            for ueb in uebs_provincia:
                self.assertIn(ueb, uebs)

    def test_nacional_incluye_almacenes_sin_provincia(self):
        """UNIDAD LOGISTICA CENTRAL es el mayor depósito: debe ser alcanzable."""
        _provincia, uebs = resolver_uebs(CODIGO_NACIONAL)
        for ueb in UEB_SIN_PROVINCIA:
            self.assertIn(ueb, uebs)

    def test_nacional_no_devuelve_provincia(self):
        provincia, _uebs = resolver_uebs(CODIGO_NACIONAL)
        self.assertIsNone(provincia)

    def test_nacional_sin_uebs_devuelve_error(self):
        Provincia.objects.all().update(activo=False)
        Dependencia.objects.all().update(activo=False)
        cache.clear()
        with mock.patch("apps.catalogo_erp.provincias.UEB_SIN_PROVINCIA", ()):
            with self.assertRaises(CatalogoError):
                resolver_uebs(CODIGO_NACIONAL)

    def test_es_nacional_acepta_alias(self):
        self.assertTrue(es_nacional("NAC"))
        self.assertTrue(es_nacional("nac"))
        self.assertTrue(es_nacional("Todas"))
        self.assertFalse(es_nacional("LH"))

    def test_uebs_nacionales_sin_duplicados(self):
        uebs = uebs_nacionales()
        self.assertEqual(len(uebs), len({normalizar(u) for u in uebs}))



class BotonProbarConexionTests(TestCase):
    """Botón del panel: POST protegido, mensaje correcto y registro del test."""

    def setUp(self):
        self.admin = User.objects.create_superuser("panel", "p@ejemplo.com", "clave-de-prueba")
        self.client.force_login(self.admin)
        self.url = reverse("catalogo_erp_probar_conexion")

    def test_exige_post(self):
        self.assertEqual(self.client.get(self.url).status_code, 405)

    def test_exige_usuario_autenticado(self):
        self.client.logout()
        respuesta = self.client.post(self.url)
        self.assertEqual(respuesta.status_code, 302)
        self.assertIn("/login/", respuesta["Location"])

    def test_sin_configuracion_avisa(self):
        respuesta = self.client.post(self.url)
        self.assertEqual(respuesta.status_code, 302)
        self.assertIn("configuraci", str(list(respuesta.wsgi_request._messages)[0]).lower())

    def test_exito_registra_ultimo_test(self):
        config = ConfiguracionERP.objects.create(
            host="h", puerto=5432, nombre_bd="b", usuario="u", password="p", activo=True
        )
        with mock.patch("apps.catalogo_erp.admin_views.probar_conexion", return_value=(True, "OK")):
            respuesta = self.client.post(self.url, {"id": str(config.pk)})
        self.assertEqual(respuesta.status_code, 302)
        config.refresh_from_db()
        self.assertIsNotNone(config.ultimo_test)

    def test_fallo_muestra_el_error(self):
        config = ConfiguracionERP.objects.create(
            host="h", puerto=5432, nombre_bd="b", usuario="u", password="p", activo=True
        )
        with mock.patch(
            "apps.catalogo_erp.admin_views.probar_conexion",
            return_value=(False, "No hay conexión de red con el ERP."),
        ):
            respuesta = self.client.post(self.url, {"id": str(config.pk)})
        self.assertEqual(respuesta.status_code, 302)
        config.refresh_from_db()
        self.assertIsNotNone(config.ultimo_test)


class CatalogoErpE2ETests(TestCase):
    """Prueba real contra el ERP; se omite sin ``ERP_PASSWORD`` o sin red."""

    def setUp(self):
        if not PASSWORD_ERP or not _erp_alcanzable():
            self.skipTest("ERP no configurado o inalcanzable (requiere ERP_PASSWORD)")

        cache.clear()
        ConfiguracionERP.objects.all().delete()
        self.config = ConfiguracionERP.objects.create(
            host=HOST_ERP,
            puerto=PUERTO_ERP,
            nombre_bd="distra-sasa",
            usuario="zeolides",
            password=PASSWORD_ERP,
            activo=True,
        )
        self.categoria = CategoriaProductoERP.objects.create(
            nombre="Neumaticos",
            metodo_busqueda=CategoriaProductoERP.METODO_MULTIPLE,
            usar_consulta_personalizada=True,
            consulta_sql=CONSULTA_NEUMATICOS,
        )
        # UEBs reales del ERP: el aislamiento por provincia se comprueba contra
        # dependencias que existen de verdad en la base del ERP.
        foto = _imagen()
        self.pinar = Provincia.objects.create(codigo="PR", nombre="Pinar del Río")
        self.habana = Provincia.objects.create(codigo="LH", nombre="La Habana")
        self.matanzas = Provincia.objects.create(codigo="MTZ", nombre="Matanzas")
        for provincia, nombre in (
            (self.pinar, "Agencia Pinar del Rio"),
            (self.habana, "Agencia Habana del Este"),
            (self.habana, "Agencia Varadero"),
            (self.matanzas, "Agencia Matanzas"),
        ):
            Dependencia.objects.create(
                provincia=provincia,
                nombre=nombre,
                direccion="",
                foto=foto,
                # Nombre exacto de la UEB en el ERP.
                ueb_erp=nombre.upper().replace("AGENCIA HABANA", "AGENCIA HABANA"),
            )

    def test_consulta_real_devuelve_disponibilidad_por_dependencia(self):
        productos = buscar_productos(self.categoria, {"q": "185"}, "PR")
        self.assertTrue(productos, "El ERP deberia devolver pneumaticos con '185'")
        dependencias = {d["dependencia"] for p in productos for d in p["disponibilidad"]}
        self.assertEqual(dependencias, {"AGENCIA PINAR DEL RIO"}, dependencias)
        json.dumps(productos)

    def test_filtro_por_provincia_excluye_otras_uebs(self):
        # Un mismo término devuelve una UEB distinta según la provincia elegida.
        pinar = buscar_productos(self.categoria, {"q": "185"}, "PR")
        habana = buscar_productos(self.categoria, {"q": "185"}, "LH")
        matanzas = buscar_productos(self.categoria, {"q": "185"}, "MTZ")
        por_provincia = {
            "PR": {d["dependencia"] for p in pinar for d in p["disponibilidad"]},
            "LH": {d["dependencia"] for p in habana for d in p["disponibilidad"]},
            "MTZ": {d["dependencia"] for p in matanzas for d in p["disponibilidad"]},
        }
        self.assertEqual(por_provincia["PR"], {"AGENCIA PINAR DEL RIO"})
        self.assertTrue(por_provincia["LH"], "LH debería devolver sus agencias")
        self.assertEqual(por_provincia["MTZ"], {"AGENCIA MATANZAS"})
        # Ningún sneaking entre provincias.
        self.assertFalse(por_provincia["MTZ"] & por_provincia["LH"])
        self.assertFalse(por_provincia["MTZ"] & por_provincia["PR"])

    def test_termino_unico_busca_en_codigo_y_descripcion(self):
        # Código: 'RUNCLC' solo aparece en numeropieza, nunca en la descripción.
        por_codigo = buscar_productos(self.categoria, {"q": "RUNCLC"}, "PR")
        self.assertTrue(por_codigo, "El término debe buscar en el número de pieza")
        for producto in por_codigo:
            self.assertIn("RUNCLC", producto["codigo"].upper())
        # Descripción: 'NEUMATICO LIGERO' solo existe en la denominación.
        por_descripcion = buscar_productos(self.categoria, {"q": "NEUMATICO LIGERO"}, "PR")
        self.assertTrue(por_descripcion, "El término debe buscar en la descripción")
        for producto in por_descripcion:
            self.assertIn("NEUMATICO LIGERO", producto["nombre"].upper())
            self.assertNotIn("NEUMATICO LIGERO", producto["codigo"].upper())
        # El mismo campo :q cubre las dos cosas.
        self.assertTrue({p["codigo"] for p in por_codigo + por_descripcion})



    def test_provincia_inexistente_devuelve_error_legible(self):
        respuesta = self.client.get(
            "/api/catalogo/buscar/",
            {"categoria_id": self.categoria.pk, "q": "185", "provincia": "ZZ"},
        )
        cuerpo = respuesta.json()
        self.assertFalse(cuerpo["ok"])
        self.assertIn("provincia", cuerpo["error"].lower())

    def test_sin_provincia_devuelve_error_legible(self):
        respuesta = self.client.get(
            "/api/catalogo/buscar/", {"categoria_id": self.categoria.pk, "q": "185"}
        )
        cuerpo = respuesta.json()
        self.assertFalse(cuerpo["ok"])
        self.assertIn("provincia", cuerpo["error"].lower())

    def test_endpoint_devuelve_json_valido(self):
        respuesta = self.client.get(
            "/api/catalogo/buscar/",
            {"categoria_id": self.categoria.pk, "q": "R18", "provincia": "LH"},
        )
        cuerpo = respuesta.json()
        self.assertEqual(respuesta.status_code, 200)
        self.assertTrue(cuerpo["ok"], cuerpo.get("error"))
        for producto in cuerpo["productos"]:
            for disp in producto["disponibilidad"]:
                self.assertIsInstance(disp["cantidad"], (int, float))

    def test_endpoint_acepta_q1_legacy(self):
        respuesta = self.client.get(
            "/api/catalogo/buscar/",
            {"categoria_id": self.categoria.pk, "q1": "R18", "provincia": "LH"},
        )
        cuerpo = respuesta.json()
        self.assertTrue(cuerpo["ok"], cuerpo.get("error"))

    def test_sin_resultados_devuelve_lista_vacia(self):
        respuesta = self.client.get(
            "/api/catalogo/buscar/",
            {
                "categoria_id": self.categoria.pk,
                "q": "zzz-no-existe",
                "provincia": "LH",
            },
        )
        cuerpo = respuesta.json()
        self.assertTrue(cuerpo["ok"])
        self.assertEqual(cuerpo["productos"], [])


