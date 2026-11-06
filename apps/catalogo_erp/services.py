"""Conexión al ERP (PostgreSQL) y construcción de búsquedas de productos.

Solo lectura y con ``statement_timeout``. Todos los *valores* de las
consultas pasan como parámetros ``%s`` de psycopg2; los *identificadores*
(tablas, columnas, esquema) se citan con ``psycopg2.sql`` para evitar
inyección por configuración.
"""

import logging
import re
from decimal import Decimal

import psycopg2
from psycopg2 import sql

from apps.catalogo_erp.exceptions import CatalogoError
from apps.catalogo_erp.models import CategoriaProductoERP
from apps.catalogo_erp.provincias import resolver_uebs

logger = logging.getLogger(__name__)

LIMITE_RESULTADOS = 50
TIMEOUT_CONEXION_S = 8
# El término se busca con ILIKE '%texto%', que no puede usar un índice: la
# consulta recorre dat_producto entera (~521k filas) contra nom_indicador
# (~176k). Con la caché del ERP fría esa primera consulta ronda los 20-25 s,
# así que el tope va holgado: con 20 s caía en "statement timeout" y el
# buscador devolvía cero resultados en la primera búsqueda.
TIMEOUT_STATEMENT_MS = 30000

# Un "LIMIT n" al final de la consulta de la categoría se elimina cuando se
# filtra por provincia: el tope tiene que aplicarse DESPUÉS de filtrar, si no
# se truncan filas de otras provincias y el resultado sale incompleto.
_RE_LIMIT_FINAL = re.compile(r"\s+LIMIT\s+\d+\s*;?\s*$", re.IGNORECASE)
# ":q" sin dígito detrás, para no confundirlo con ":q1", ":q2" o ":q3".
_RE_PLACEHOLDER_Q = re.compile(r":q(?![0-9])")

# Se reexporta para que los módulos que ya hacen
# "from apps.catalogo_erp.services import CatalogoError" sigan funcionando.
__all__ = ["CatalogoError", "buscar_productos", "construir_consulta", "probar_conexion"]


_MARCAS_RED = (
    "timeout expired",
    "could not connect",
    "no route to host",
    "connection refused",
    "connection reset",
    "name or service not known",
    "temporary failure in name resolution",
    "network is unreachable",
    "ssl syscall error",
)


def _error_amigable(exc):
    """Traduce excepciones de psycopg2 a mensajes claros."""
    if isinstance(exc, CatalogoError):
        return str(exc)
    if isinstance(exc, psycopg2.OperationalError):
        texto = str(exc).lower()
        if getattr(exc, "pgcode", None) == "28P01" or "password authentication failed" in texto:
            return "Credenciales incorrectas: el ERP rechazó el usuario o la contraseña."
        if "no password supplied" in texto:
            return (
                "No hay contraseña guardada o no se pudo descifrar. Volvé a "
                "cargarla en Configuración ERP."
            )
        if any(marca in texto for marca in _MARCAS_RED):
            return (
                "No hay conexión de red con el ERP. Verificá que el host y el "
                "puerto sean correctos y que la red permita el acceso."
            )
        return "No se pudo conectar con el ERP. Verificá la configuración."
    if isinstance(exc, psycopg2.errors.UndefinedTable):
        codigo = exc.diag.sqlstate or ""
        detalle = getattr(exc, "diag", None) and exc.diag.message_primary or str(exc)
        return f"Tabla inexistente en el ERP ({codigo}): {detalle}"
    if isinstance(exc, psycopg2.errors.UndefinedColumn):
        return f"Columna inexistente en el ERP: {getattr(exc.diag, 'message_primary', str(exc))}"
    if isinstance(exc, psycopg2.errors.QueryCanceled):
        return "La consulta tardó demasiado y fue cancelada. Intentá un criterio más específico."
    return f"Error consultando el ERP: {exc.__class__.__name__}"


def abrir_conexion(config):
    """Conecta a PostgreSQL en modo solo lectura con timeout corto."""
    if config.password and not config.password_plana:
        raise CatalogoError(
            "No se pudo descifrar la contraseña guardada: la SECRET_KEY del "
            "servidor es distinta de la usada al cifrarla. Volvé a guardar la "
            "contraseña en Configuración ERP."
        )
    conn = psycopg2.connect(
        host=config.host,
        port=config.puerto,
        dbname=config.nombre_bd,
        user=config.usuario,
        password=config.password_plana,
        connect_timeout=TIMEOUT_CONEXION_S,
        options=(
            f"-c statement_timeout={TIMEOUT_STATEMENT_MS} "
            "-c default_transaction_read_only=on"
        ),
    )
    return conn


def probar_conexion(config):
    """Prueba la conexión (SELECT 1). Devuelve (ok, mensaje)."""
    try:
        with abrir_conexion(config) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                cur.fetchone()
        return True, "Conexión exitosa al ERP."
    except Exception as exc:  # noqa: BLE001 - se traduce a mensaje
        logger.exception("Prueba de conexión ERP fallida")
        return False, _error_amigable(exc)


# ---------------------------------------------------------------------------
# Construcción de la consulta (identificadores citados, valores parametrizados)
# ---------------------------------------------------------------------------
def _columna(tabla_alias, nombre):
    """Columna ``alias.nombre`` con identificadores citados."""
    return sql.SQL(".").join((sql.Identifier(tabla_alias), sql.Identifier(nombre)))


def _consulta_personalizada(categoria, terminos, agregar_limite=True):
    """Procesa la consulta SQL personalizada de la categoría.

    Acepta el placeholder unificado ``:q`` (término único que busca a la vez en
    código y nombre) y, por compatibilidad, ``:q1``/``:q2``/``:q3``.

    Valida que sea SELECT y reemplaza los placeholders por parámetros seguros.
    """
    raw_sql = categoria.consulta_sql.strip()

    # Validación básica de seguridad: solo SELECT
    normalized = " ".join(raw_sql.lower().split())
    if not normalized.startswith("select"):
        raise CatalogoError(
            "La consulta personalizada debe empezar con SELECT. "
            "No se permiten INSERT, UPDATE, DELETE ni otras operaciones."
        )

    if ";" in raw_sql.rstrip(";").rstrip():
        raise CatalogoError(
            "La consulta personalizada no debe contener puntos y coma (;)."
        )

    # Mapeo de placeholders a valores del buscador
    termino = (terminos.get("q") or "").strip()
    valores = {
        ":q": termino,
        ":q1": (terminos.get("q1") or "").strip(),
        ":q2": (terminos.get("q2") or "").strip(),
        ":q3": (terminos.get("q3") or "").strip(),
    }

    # Verificar que al menos un placeholder tenga valor
    placeholders_requeridos = set()
    for placeholder in (":q1", ":q2", ":q3"):
        if placeholder in raw_sql:
            placeholders_requeridos.add(placeholder)
    if _RE_PLACEHOLDER_Q.search(raw_sql):
        placeholders_requeridos.add(":q")

    if placeholders_requeridos and not any(valores[p] for p in placeholders_requeridos):
        raise CatalogoError(
            "Ingresá al menos un criterio de búsqueda para esta categoría."
        )

    # psycopg2 interpreta los "%" de la consulta como marcas de formato, así que
    # los "%" literales que escribe el administrador (p. ej. LIKE '%') se escapan
    # como "%%" ANTES de inyectar los placeholders posicionales "%s".
    sql_safe = raw_sql.replace("%", "%%")

    # Reemplazar cada placeholder por un parámetro seguro (%s). Se admite el
    # mismo placeholder varias veces (p. ej. para comprobar si viene vacío y
    # usarlo como patrón): cada aparición agrega su propio parámetro. Se
    # sustituyen primero los nombres largos para que ":q1" no se coma el ":q".
    params = []
    for indice, placeholder in enumerate((":q1", ":q2", ":q3", ":q"), start=1):
        marca = f"\x00{indice}\x00"
        while placeholder in sql_safe:
            sql_safe = sql_safe.replace(placeholder, marca, 1)
            params.append(valores[placeholder])
    for indice in (1, 2, 3, 4):
        sql_safe = sql_safe.replace(f"\x00{indice}\x00", "%s")

    # Agregar LIMIT si no tiene
    if agregar_limite and "limit" not in normalized:
        sql_safe += f" LIMIT {LIMITE_RESULTADOS}"

    return sql_safe, params


def _filtrar_por_provincia(interna, params, uebs, limite=LIMITE_RESULTADOS):
    """Envuelve la consulta de la categoría para limitar la disponibilidad a ``uebs``.

    El filtro se aplica en SQL sobre la columna ``dependencia`` (UEB) del
    resultado, moviendo el ``LIMIT`` hacia la consulta externa. Filtrar en
    Python después del ``LIMIT`` devolvería conteos incompletos.

    El tope es de PRODUCTOS, no de filas: cada fila es un par producto×UEB, así
    que un tope de filas devolvería menos productos en la opción nacional (17
    UEBs) que en una provincia con dos agencias. Por eso se filtra primero y
    después se eligen ``limite`` códigos distintos, trayendo todas las filas de
    esos códigos para no recortarles la disponibilidad.
    """
    if isinstance(interna, str):
        interna = sql.SQL(_RE_LIMIT_FINAL.sub("", interna))
    marcas = sql.SQL(", ").join(sql.Placeholder() for _ in uebs)
    consulta = sql.SQL(
        "WITH disponibilidad AS ("
        "  SELECT * FROM ({interna}) AS {alias_interna}"
        "), filtrada AS ("
        "  SELECT * FROM disponibilidad WHERE {col_dep} IN ({marcas})"
        "), elegido AS ("
        "  SELECT DISTINCT {col_codigo} AS codigo FROM filtrada"
        "  ORDER BY {col_codigo} LIMIT {limite}"
        ") "
        "SELECT filtrada.* FROM filtrada "
        "INNER JOIN elegido ON elegido.codigo = filtrada.{col_codigo} "
        "ORDER BY filtrada.{col_codigo}, filtrada.{col_dep}"
    ).format(
        interna=interna,
        alias_interna=sql.Identifier("disponibilidad_total"),
        marcas=marcas,
        col_dep=sql.Identifier("dependencia"),
        col_codigo=sql.Identifier("codigo"),
        limite=sql.Placeholder(),
    )
    return consulta, list(params) + list(uebs) + [limite]




def construir_consulta(categoria, config, terminos, uebs=None):
    """Devuelve (sql, params) para buscar productos y su disponibilidad.

    ``terminos``: dict con ``q`` (término único) o ``q1``/``q2``/``q3``
    (método "multiple", en desuso).
    ``uebs``: si viene, la consulta se envuelve para devolver solo la
    disponibilidad de esas unidades (filtro por provincia).
    """

    def campo(nombre):
        if not nombre:
            return None
        return _columna("p", nombre)

    def extra(nombre):
        sql_expr = campo(nombre)
        if sql_expr is None:
            return None
        return sql.SQL("").join((sql_expr, sql.SQL(" AS "), sql.Identifier("extra")))

    # --- Consulta personalizada del admin --------------------------------
    if categoria.usar_consulta_personalizada and categoria.consulta_sql.strip():
        consulta, params = _consulta_personalizada(
            categoria, terminos, agregar_limite=not uebs
        )
        if uebs:
            return _filtrar_por_provincia(consulta, params, uebs)
        return consulta, params

    # Columnas seleccionadas
    extras_config = [
        categoria.campo_extra1,
        categoria.campo_extra2,
        categoria.campo_extra3,
    ]
    seleccion = [
        _columna("p", categoria.campo_codigo) + sql.SQL(" AS codigo"),
        _columna("p", categoria.campo_nombre) + sql.SQL(" AS nombre"),
    ]
    for i, nombre_extra in enumerate(extras_config, start=1):
        if nombre_extra:
            seleccion.append(_columna("p", nombre_extra) + sql.SQL(f" AS extra{i}"))

    seleccion += [
        sql.SQL("COALESCE(d.{dep_nombre}, s.{dep_codigo_stock})").format(
            dep_nombre=sql.Identifier(config.campo_dep_nombre),
            dep_codigo_stock=sql.Identifier(config.campo_stock_dependencia),
        ) + sql.SQL(" AS dependencia"),
        sql.SQL("COALESCE(s.{cant}, 0)").format(
            cant=sql.Identifier(config.campo_stock_cantidad)
        ) + sql.SQL(" AS cantidad"),
    ]

    base = sql.SQL(
        "SELECT {seleccion} "
        "FROM {schema}.{origen} AS p "
        "LEFT JOIN {schema}.{stock} AS s "
        "  ON s.{stock_codigo}::text = p.{codigo}::text "
        "LEFT JOIN {schema}.{deps} AS d "
        "  ON d.{dep_codigo}::text = s.{stock_dep}::text "
    ).format(
        seleccion=sql.SQL(", ").join(seleccion),
        schema=sql.Identifier(config.schema),
        origen=sql.Identifier(categoria.tabla_origen),
        stock=sql.Identifier(config.tabla_stock),
        stock_codigo=sql.Identifier(config.campo_stock_codigo),
        stock_dep=sql.Identifier(config.campo_stock_dependencia),
        codigo=sql.Identifier(categoria.campo_codigo),
        deps=sql.Identifier(config.tabla_dependencias),
        dep_codigo=sql.Identifier(config.campo_dep_codigo),
    )

    condiciones = []
    params = []

    def like(columna, valor, prefijo=False, contener=True):
        if prefijo:
            params.append(f"{valor}%")
        elif contener:
            params.append(f"%{valor}%")
        else:
            params.append(valor)
        return sql.SQL("{col} ILIKE {p}").format(col=columna, p=sql.Placeholder())

    metodo = categoria.metodo_busqueda
    q = (terminos.get("q") or "").strip()

    if metodo == CategoriaProductoERP.METODO_CODIGO:
        if not q:
            raise CatalogoError("Ingresá el código exacto del producto para buscar.")
        condiciones.append(
            sql.SQL("{col} = {p}").format(
                col=_columna("p", categoria.campo_codigo), p=sql.Placeholder()
            )
        )
        params.append(q)

    elif metodo == CategoriaProductoERP.METODO_SEGMENTO:
        if not q:
            raise CatalogoError("Ingresá el segmento / prefijo del código para buscar.")
        condiciones.append(like(_columna("p", categoria.campo_codigo), q, prefijo=True))

    elif metodo == CategoriaProductoERP.METODO_DESCRIPCION:
        if not q:
            raise CatalogoError("Ingresá una palabra clave de la descripción para buscar.")
        condiciones.append(
            sql.SQL("({a} ILIKE {p1} OR {b} ILIKE {p2})").format(
                a=_columna("p", categoria.campo_nombre),
                b=_columna("p", categoria.campo_codigo),
                p1=sql.Placeholder(),
                p2=sql.Placeholder(),
            )
        )
        params += [f"%{q}%", f"%{q}%"]

    elif metodo == CategoriaProductoERP.METODO_MULTIPLE:
        objetivos = [categoria.campo_codigo, categoria.campo_nombre]
        if categoria.campo_extra1:
            objetivos.append(categoria.campo_extra1)
        valores = [
            (terminos.get("q1") or "").strip(),
            (terminos.get("q2") or "").strip(),
            (terminos.get("q3") or "").strip(),
        ]
        activas = [(col, val) for col, val in zip(objetivos, valores) if val]
        if not activas:
            raise CatalogoError("Ingresá al menos un criterio de búsqueda.")
        for col, val in activas:
            condiciones.append(like(_columna("p", col), val, contener=True))

    else:  # pragma: no cover - método desconocido
        raise CatalogoError("Método de búsqueda no soportado para esta categoría.")

    if categoria.campo_categoria and categoria.valor_categoria:
        condiciones.append(
            sql.SQL("{col} = {p}").format(
                col=_columna("p", categoria.campo_categoria), p=sql.Placeholder()
            )
        )
        params.append(categoria.valor_categoria)

    consulta = sql.SQL(" {where} {order} {limite}").format(
        where=sql.SQL("WHERE ") + sql.SQL(" AND ").join(condiciones),
        order=sql.SQL(
            "ORDER BY p.{codigo} ASC, dependencia ASC"
        ).format(codigo=sql.Identifier(categoria.campo_codigo)),
        limite=(
            sql.SQL("")
            if uebs
            else sql.SQL("LIMIT {}").format(sql.Literal(LIMITE_RESULTADOS))
        ),
    )

    completa = base + consulta
    if uebs:
        return _filtrar_por_provincia(completa, params, uebs)
    return completa, params


# ---------------------------------------------------------------------------
# Ejecución y agrupación de resultados
# ---------------------------------------------------------------------------
def _cantidad(valor):
    """Convierte una cantidad del ERP a un número serializable en JSON.

    PostgreSQL devuelve ``numeric`` como ``Decimal``, que ``JsonResponse`` no
    sabe serializar. Los valores enteros se devuelven como ``int`` para que el
    frontend los muestre sin decimales (``Decimal('20.000000')`` → ``20``).
    """
    if valor is None:
        return 0
    if isinstance(valor, Decimal):
        if valor.is_nan() or valor.is_infinite():
            return 0
        if valor == valor.to_integral_value():
            return int(valor)
        return float(valor)
    if isinstance(valor, bool):
        return int(valor)
    if isinstance(valor, (int, float)):
        return valor
    try:
        numero = float(valor)
    except (TypeError, ValueError):
        return 0
    return int(numero) if numero.is_integer() else numero


COLUMNAS_REQUERIDAS = ("codigo", "nombre", "dependencia", "cantidad")


def _posiciones(nombres):
    """Resuelve la posición de cada campo relevante a partir de los nombres.

    Así el orden de las columnas devueltas por el ERP deja de importar (lo
    habitual es ``codigo, nombre, dependencia, cantidad, extra1``). Si falta
    alguna columna requerida se recurre al orden posicional histórico:
    ``codigo, nombre, [extras...], dependencia, cantidad``.
    """
    nombres = [str(nombre).strip().lower() for nombre in nombres or []]
    total = len(nombres)

    def indice(nombre, respaldo):
        return nombres.index(nombre) if nombre in nombres else respaldo

    if total:
        i_codigo = indice("codigo", 0)
        i_nombre = indice("nombre", 1)
        i_dependencia = indice("dependencia", total - 2)
        i_cantidad = indice("cantidad", total - 1)
    else:
        i_codigo, i_nombre, i_dependencia, i_cantidad = 0, 1, 2, 3

    if any(nombre.startswith("extra") for nombre in nombres):
        i_extras = [indice(f"extra{i}", None) for i in (1, 2, 3)]
    else:
        cantidad_extras = max(0, total - 4)
        i_extras = [2 + i if i < cantidad_extras else None for i in range(3)]

    return i_codigo, i_nombre, i_extras, i_dependencia, i_cantidad


def _nombres_por_defecto(filas):
    """Deduce los nombres de columna por posición si el ERP no los devolvió.

    Orden histórico documentado: ``codigo, nombre, [extras...], dependencia,
    cantidad``.
    """
    if not filas:
        return []
    ancho = len(filas[0])
    extras = max(0, ancho - 4)
    return (
        ["codigo", "nombre"]
        + [f"extra{i + 1}" for i in range(extras)]
        + ["dependencia", "cantidad"]
    )


def _agrupar(filas, nombres):
    """Agrupa filas (producto × dependencia) por producto y suma cantidades.

    ``nombres`` son los nombres de columna tal como los devuelve el ERP; las
    columnas ``extra1..3`` son opcionales y se muestran en la ficha del producto.
    """
    i_codigo, i_nombre, i_extras, i_dependencia, i_cantidad = _posiciones(
        nombres or _nombres_por_defecto(filas)
    )
    productos, orden = {}, []
    for fila in filas:
        codigo = fila[i_codigo] if i_codigo < len(fila) else None
        if codigo is None:
            continue
        if codigo not in productos:
            productos[codigo] = {
                "codigo": codigo,
                "nombre": fila[i_nombre] if i_nombre < len(fila) else None,
                "extra1": None,
                "extra2": None,
                "extra3": None,
                "disponibilidad": {},
            }
            orden.append(codigo)
        resumen = productos[codigo]
        for i, posicion in enumerate(i_extras):
            if posicion is not None and posicion < len(fila):
                valor = fila[posicion]
                if resumen[f"extra{i + 1}"] is None and valor is not None:
                    resumen[f"extra{i + 1}"] = valor
        dependencia = fila[i_dependencia] if i_dependencia < len(fila) else None
        cantidad = fila[i_cantidad] if i_cantidad < len(fila) else None
        deps = resumen["disponibilidad"]
        deps[dependencia] = deps.get(dependencia, 0) + _cantidad(cantidad)

    for codigo in orden:
        disponibilidad = [
            {"dependencia": dep, "cantidad": cant}
            for dep, cant in productos[codigo]["disponibilidad"].items()
        ]
        productos[codigo]["disponibilidad"] = disponibilidad
    return [productos[codigo] for codigo in orden]


def buscar_productos(categoria, terminos, provincia):
    """Consulta el ERP y devuelve los productos con la disponibilidad de ``provincia``.

    ``provincia`` es obligatorio: es el código (PR, LH…) o el pk de la provincia
    elegida por el usuario. La disponibilidad se limita a las UEBs de esa
    provincia.
    """
    from apps.catalogo_erp.models import ConfiguracionERP

    # La provincia se resuelve primero: es una validación de la petición (BD
    # local) y debe poder|reportar el error aunque el ERP no esté configurado.
    _provincia, uebs = resolver_uebs(provincia)

    config = ConfiguracionERP.activa()
    if config is None:
        raise CatalogoError(
            "El catálogo no está configurado todavía. Activá la Configuración ERP desde el panel."
        )
    if not categoria or not categoria.activo:
        raise CatalogoError("La categoría solicitada no está disponible.")

    sql_query, params = construir_consulta(categoria, config, terminos, uebs=uebs)

    try:
        with abrir_conexion(config) as conn:
            with conn.cursor() as cur:
                cur.execute(sql_query, params)
                filas = cur.fetchall()
                nombres = [d.name for d in cur.description] if cur.description else []
    except psycopg2.Error as exc:
        logger.warning("Fallo ERP (%s): %s", categoria.slug, exc)
        raise CatalogoError(_error_amigable(exc)) from exc
    except IndexError as exc:
        logger.error(
            "Consulta personalizada de '%s': número de parámetros incorrecto (%s)",
            categoria.slug,
            exc,
        )
        raise CatalogoError(
            "La consulta personalizada de esta categoría tiene un número de "
            "parámetros que no coincide con sus placeholders :q, :q1, :q2 o :q3."
        ) from exc
    except Exception as exc:  # noqa: BLE001
        logger.exception("Error inesperado al consultar el ERP")
        raise CatalogoError(_error_amigable(exc)) from exc

    return _agrupar(filas, nombres)