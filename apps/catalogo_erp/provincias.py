"""Resolución de provincias → UEBs del ERP para filtrar la disponibilidad.

El ERP no guarda la provincia: sus unidades responsables de expendeduría (UEB)
solo tienen nombre (``et.denominacion`` en ``v_dametodasestructuras``). La
provincia se resuelve en Django emparejando ese nombre con las dependencias que
el cliente mantiene en el panel (modelo ``mapa.Dependencia``).

El emparejamiento se hace sobre el campo ``ueb_erp`` cuando está cargado; si
está vacío se cae al nombre de la dependencia. La comparación normaliza
mayúsculas, acentos y puntuación, de modo que "AGENCIA CAIBARIEN" del ERP
empareja con "Agencia Caibarién".
"""

import logging
import re
import unicodedata

from django.core.cache import cache

logger = logging.getLogger(__name__)

CACHE_PROVINCIAS = "catalogo_erp:provincias:uebs"
CACHE_MAPEADO = "catalogo_erp:provincias:mapeado"
CACHE_TTL_SEGUNDOS = 300

CODIGO_NACIONAL = "NAC"
NOMBRE_NACIONAL = "Nacional (todas)"

# UEBs del ERP que no son una agencia de una provincia: el almacén central y
# áreas de cobertura nacional. Concentran el stock más grande (UNIDAD LOGISTICA
# CENTRAL es el mayor depósito del ERP), así que sin esto sus productos no
# aparecen al filtrar por provincia. No se registran como ``Dependencia`` a
# propósito: el mapa público dibuja todas las dependencias activas y un
# almacén central no es un punto de venta.
UEB_SIN_PROVINCIA = (
    "UNIDAD LOGISTICA CENTRAL",
    "CASA MATRIZ",
    "MYPIME",
)

# UEBs que sí son agencia pero todavía no están cargadas en el mapa. Se asignan
# a una provincia hasta que exista su ``Dependencia`` y el negocio la ubique.
UEB_ASIGNADAS = {
    "AGENCIA PUERTO HABANA": "LH",
}

_RE_NO_ALFANUM = re.compile(r"[^A-Z0-9]")


def normalizar(texto):
    """Mayúsculas, sin acentos y sin puntuación.

    >>> normalizar("AGENCIA CAIBARIEN") == normalizar("Agencia Caibarién")
    True
    """
    descompuesto = unicodedata.normalize("NFKD", texto or "")
    sin_acentos = "".join(c for c in descompuesto if not unicodedata.combining(c))
    return _RE_NO_ALFANUM.sub("", sin_acentos.upper())


def _mapeo_sincronizado():
    """``True`` si alguna dependencia ya tiene ``ueb_erp`` confirmado.

    Es la señal de que ``sincronizar_uebs --aplicar`` ya corrió. Mientras no haya
    ninguna, el catálogo cae al ``nombre`` de la dependencia para no dejar el
    buscador vacío en un mapa todavía sin sincronizar.
    """
    from apps.mapa.models import Dependencia

    resultado = cache.get(CACHE_MAPEADO)
    if resultado is None:
        resultado = Dependencia.objects.filter(activo=True).exclude(ueb_erp="").exists()
        cache.set(CACHE_MAPEADO, resultado, CACHE_TTL_SEGUNDOS)
    return resultado


def _dependencias_de(provincia):
    """UEBs de una provincia, tal como las nombra el ERP.

    Cuando el mapeo ya fue sincronizado (``sincronizar_uebs --aplicar``), solo se
    usan los ``ueb_erp`` confirmados contra el ERP: así una dependencia que no
    existe allí (una filial, una tienda) no hace aparecer una provincia que
    siempre devolvería cero resultados. Si el mapeo aún no se sincronizó se cae
    al ``nombre`` de la dependencia.
    """
    from apps.mapa.models import Dependencia

    qs = list(
        Dependencia.objects.filter(provincia=provincia, activo=True)
        .only("nombre", "ueb_erp")
        .order_by("nombre")
    )
    sincronizado = _mapeo_sincronizado()

    nombres = []
    for dep in qs:
        if sincronizado:
            candidato = (dep.ueb_erp or "").strip()
        else:
            candidato = (dep.ueb_erp or "").strip() or (dep.nombre or "").strip()
        if candidato and _RE_NO_ALFANUM.sub("", normalizar(candidato)):
            nombres.append(candidato)

    return _unicos(nombres)


def _unicos(nombres):
    """Deduplica por forma normalizada conservando el texto original del ERP."""
    vistos, unicos = set(), []
    for nombre in nombres:
        clave = normalizar(nombre)
        if clave and clave not in vistos:
            vistos.add(clave)
            unicos.append(nombre)
    return unicos


def _asignadas_para(codigo):
    """UEBs de ``UEB_ASIGNADAS`` que corresponden a este código de provincia."""
    objetivo = normalizar(codigo)
    return [
        ueb
        for ueb, codigo_destino in UEB_ASIGNADAS.items()
        if normalizar(codigo_destino) == objetivo
    ]


def provincias_con_ueb(forzar=False):
    """Provincias activas que tienen al menos una UEB: ``[(Provincia, [uebs])]``."""
    datos = None if forzar else cache.get(CACHE_PROVINCIAS)
    if datos is not None:
        return _rehidratar(datos)

    from apps.mapa.models import Provincia

    resultado = []
    for provincia in Provincia.objects.filter(activo=True).order_by("orden", "nombre"):
        # Las UEBs asignadas a mano (UEB_ASIGNADAS) se agregan a las de su
        # provincia, así el mapa puede completarse sin crear dependencias
        # ficticias que aparecerían como marcadores públicos.
        uebs = _unicos(_dependencias_de(provincia) + _asignadas_para(provincia.codigo))
        if uebs:
            resultado.append((provincia, uebs))

    cache.set(
        CACHE_PROVINCIAS,
        [(p.pk, p.codigo, p.nombre, p.orden, uebs) for p, uebs in resultado],
        CACHE_TTL_SEGUNDOS,
    )
    return resultado


def _rehidratar(datos):
    from apps.mapa.models import Provincia

    provincias = {
        p.pk: p for p in Provincia.objects.filter(pk__in=[d[0] for d in datos])
    }
    return [
        (provincias[pk], uebs) for pk, _cod, _nombre, _orden, uebs in datos if pk in provincias
    ]


def limpiar_cache():
    cache.delete(CACHE_PROVINCIAS)
    cache.delete(CACHE_MAPEADO)


def provincia_por_referencia(valor):
    """Busca una provincia por código (PR, LH…) o por pk. ``None`` si no existe."""
    from apps.mapa.models import Provincia

    valor = (valor or "").strip()
    if not valor:
        return None
    codigo = valor.upper()
    provincia = Provincia.objects.filter(codigo=codigo, activo=True).first()
    if provincia is not None:
        return provincia
    if valor.isdigit():
        return Provincia.objects.filter(pk=int(valor), activo=True).first()
    return Provincia.objects.filter(nombre__iexact=valor, activo=True).first()


def opciones_provincia():
    """Lista ``[{"codigo", "nombre"}]`` para el ``<select>`` del buscador.

    Al final se agrega la opción nacional: es la única forma de ver el stock de
    los almacenes que no pertenecen a una provincia (sobre todo UNIDAD LOGISTICA
    CENTRAL, el mayor depósito del ERP). Se deja de última para que la provincia
    por defecto siga siendo una provincia real.
    """
    opciones = [
        {"codigo": provincia.codigo, "nombre": provincia.nombre}
        for provincia, _ in provincias_con_ueb()
    ]
    if opciones:
        opciones.append({"codigo": CODIGO_NACIONAL, "nombre": NOMBRE_NACIONAL})
    return opciones


def es_nacional(valor):
    """``True`` si la referencia apunta a la opción nacional."""
    return normalizar(valor) in {normalizar(CODIGO_NACIONAL), "TODAS", "NACIONAL"}


def uebs_nacionales():
    """Todas las UEBs mapeadas más las que no pertenecen a una provincia."""
    todas = []
    for _provincia, uebs in provincias_con_ueb():
        todas.extend(uebs)
    return _unicos(todas + list(UEB_SIN_PROVINCIA))


def provincia_por_defecto():
    """Provincia inicial del buscador.

    Se prioriza La Habana y, si no, la primera provincia (por orden) que tenga
    UEBs mapeadas. Devuelve ``None`` si todavía no hay ninguna mapeada.
    """
    candidatas = provincias_con_ueb()
    if not candidatas:
        return None
    for provincia, _uebs in candidatas:
        if normalizar(provincia.codigo) == "LH":
            return provincia
    return candidatas[0][0]

def resolver_uebs(valor):
    """Devuelve ``(provincia, uebs)`` a partir de la referencia recibida.

    Para la opción nacional devuelve ``(None, uebs)`` con todas las UEBs: la
    provincia no es un filtro real ahí, es la unión de todo.

    Lanza ``CatalogoError`` con un mensaje utilizable si falta o no es válida.
    """
    from apps.catalogo_erp.exceptions import CatalogoError

    valor = (valor or "").strip()
    if not valor:
        raise CatalogoError("Elegí la provincia donde querés consultar la disponibilidad.")

    if es_nacional(valor):
        uebs = uebs_nacionales()
        if not uebs:
            raise CatalogoError("Todavía no hay agencias con stock registradas.")
        return None, uebs

    provincia = provincia_por_referencia(valor)
    if provincia is None:
        raise CatalogoError("La provincia indicada no existe o no está disponible.")

    for candidate, uebs in provincias_con_ueb():
        if candidate.pk == provincia.pk:
            return provincia, uebs

    raise CatalogoError(
        f"Por ahora no tenemos agencias con stock registradas en {provincia.nombre}."
    )
