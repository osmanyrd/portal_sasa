"""Sincroniza el mapeo ``mapa.Dependencia.ueb_erp`` con las UEBs del ERP.

La vista ERP no tiene columna de provincia: la única forma de saber a qué
provincia pertenece un punto de venta es cruzarlo contra la UEB que el ERP
devuelve en ``dependencia`` (``v_dametodasestructuras`` con ``idorgano = -2``).

Por eso el catálogo guarda el nombre EXACTO de la UEB en la dependencia local
(``ueb_erp``) en vez de normalizar en cada búsqueda: acentos, mayúsculas y
puntuación del ERP nosorprenden en runtime.

Salida típica::

    python manage.py sincronizar_uebs --listar
    python manage.py sincronizar_uebs --aplicar
"""

import unicodedata

import psycopg2
from django.core.cache import cache
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.catalogo_erp.models import ConfiguracionERP
from apps.catalogo_erp.services import probar_conexion
from apps.mapa.models import Dependencia

# Se mantienen en minúsculas y sin acentos para comparar de forma tolerante.
CONSULTA_UEBS = """
SELECT DISTINCT et.denominacion
FROM mod_estructuracomp.v_dametodasestructuras et
WHERE et.idorgano = -2
ORDER BY et.denominacion
"""


def normalizar(texto):
    """Minúsculas, sin acentos y sin puntuación (usado solo para comparar)."""
    if not texto:
        return ""
    plano = unicodedata.normalize("NFKD", str(texto))
    plano = "".join(c for c in plano if not unicodedata.combining(c))
    return "".join(c for c in plano.lower() if c.isalnum() or c.isspace()).strip()


class Command(BaseCommand):
    help = "Audita y sincroniza el mapeo provincia→UEB del catálogo ERP."

    def add_arguments(self, parser):
        parser.add_argument(
            "--listar",
            action="store_true",
            help="Solo muestra el mapeo actual y termina (no escribe nada).",
        )
        parser.add_argument(
            "--aplicar",
            action="store_true",
            help="Guarda el mapeo encontrado en mapa.Dependencia.ueb_erp.",
        )
        parser.add_argument(
            "--provincia",
            default="",
            help="Limita la sincronización a una provincia (código PR, LH… o pk).",
        )

    def handle(self, *args, **options):
        verbo = self.stdout.write

        config = ConfiguracionERP.activa()
        if config is None:
            raise CommandError("No hay Configuración ERP activa.")

        ok, mensaje = probar_conexion(config)
        if not ok:
            raise CommandError(f"No se pudo conectar al ERP: {mensaje}")
        verbo(f"Conexión: {mensaje}")

        # 1) UEBs reales del ERP
        try:
            with psycopg2.connect(
                host=config.host,
                port=config.puerto,
                dbname=config.nombre_bd,
                user=config.usuario,
                password=config.password_plana,
                connect_timeout=8,
                options="-c statement_timeout=20000",
            ) as conexion:
                with conexion.cursor() as cur:
                    cur.execute(CONSULTA_UEBS)
                    uebs_erp = [fila[0] for fila in cur.fetchall()]
        except psycopg2.Error as exc:
            raise CommandError(f"No se pudieron leer las UEBs del ERP: {exc}") from exc

        if not uebs_erp:
            raise CommandError("El ERP no devolvió ninguna UEB. Revisar la vista ERP.")

        indice_erp = {normalizar(ueb): ueb for ueb in uebs_erp}

        # 2) Dependencias locales candidatas
        filtro = {}
        if options["provincia"]:
            from apps.catalogo_erp.provincias import provincia_por_referencia

            provincia = provincia_por_referencia(options["provincia"])
            if provincia is None:
                raise CommandError(f"Provincia inválida: {options['provincia']}")
            filtro["provincia"] = provincia
            verbo(f"Provincia: {provincia} ({provincia.codigo})")

        dependencias = Dependencia.objects.filter(activo=True, **filtro).select_related(
            "provincia"
        )

        emparejadas, sin_ueb, ya_fijas = [], [], 0
        cambios = []
        for dep in dependencias:
            # 1) si ya hay ueb_erp explícita y existe en el ERP, la respetamos
            if dep.ueb_erp and normalizar(dep.ueb_erp) in indice_erp:
                ya_fijas += 1
                continue
            # 2) si no, intentamos emparejar por el nombre exacto
            exacto = indice_erp.get(normalizar(dep.nombre))
            if exacto is None:
                sin_ueb.append(dep)
                continue
            emparejadas.append((dep, exacto))
            if dep.ueb_erp != exacto:
                cambios.append((dep, exacto))

        verbo("")
        verbo(f"UEBs distintas en el ERP: {len(uebs_erp)}")
        verbo(f"Dependencias activas revisadas: {dependencias.count()}")
        verbo(f"  ya tienen UEB fija:   {ya_fijas}")
        verbo(f"  emparejadas por nombre: {len(emparejadas)}")
        verbo(f"  sin UEB equivalente:     {len(sin_ueb)}")

        if cambios:
            verbo("")
            verbo("Cambios a aplicar:")
            for dep, exacto in cambios:
                verbo(f"  - {dep}  ->  ueb_erp='{exacto}'")

        if sin_ueb:
            verbo("")
            verbo("Dependencias sin UEB en el ERP (quedan sin stock):")
            for dep in sin_ueb:
                verbo(f"  - {dep} [{dep.provincia_id}]")

        # 3) UEBs del ERP que ninguna dependencia local reclama
        reclamadas = {normalizar(d.ueb_erp) for d in dependencias if d.ueb_erp}
        reclamadas.update(normalizar(e) for _, e in emparejadas)
        huerfanas = [ueb for norm, ueb in indice_erp.items() if norm not in reclamadas]
        if huerfanas:
            verbo("")
            verbo("UEBs del ERP sin dependencia local (quedan fuera del catálogo):")
            for ueb in huerfanas:
                verbo(f"  - {ueb}")

        if options["aplicar"] and cambios:
            with transaction.atomic():
                for dep, exacto in cambios:
                    dep.ueb_erp = exacto
                    dep.save(update_fields=["ueb_erp"])
            cache.clear()
            verbo("")
            verbo(f"Aplicados {len(cambios)} cambio(s) en mapa.Dependencia.ueb_erp.")
        elif options["aplicar"]:
            verbo("")
            verbo("No hubo cambios que aplicar.")
        else:
            verbo("")
            verbo("Solo simulación: usá --aplicar para guardar los cambios.")
