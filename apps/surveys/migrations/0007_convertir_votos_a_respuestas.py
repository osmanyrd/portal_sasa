"""
Migración de datos: convierte los Votos históricos (modelo legacy) en
RespuestaEncuesta para que las estadísticas y CSV nuevas lean una sola fuente.

- simple: una RespuestaEncuesta por (participacion, pregunta) con opcion + valor_json=[id].
- multiple: una RespuestaEncuesta que agrupa todos los votos de esa pregunta.
"""
from django.db import migrations


def _convertir_votos(apps, schema_editor):
    Voto = apps.get_model("surveys", "Voto")
    RespuestaEncuesta = apps.get_model("surveys", "RespuestaEncuesta")
    Pregunta = apps.get_model("surveys", "Pregunta")

    agrupados = {}
    for voto in Voto.objects.select_related("pregunta").order_by("id"):
        clave = (voto.participacion_id, voto.pregunta_id)
        agrupados.setdefault(clave, {
            "participacion_id": voto.participacion_id,
            "pregunta": voto.pregunta,
            "opcion_ids": [],
            "fecha": voto.fecha_voto,
        })
        if voto.opcion_id is not None:
            agrupados[clave]["opcion_ids"].append(voto.opcion_id)

    crear = []
    for datos in agrupados.values():
        pregunta = datos["pregunta"]
        opc_ids = datos["opcion_ids"]
        primera = opc_ids[0] if opc_ids else None
        crear.append(
            RespuestaEncuesta(
                participacion_id=datos["participacion_id"],
                pregunta_id=pregunta.id,
                opcion_id=primera if pregunta.tipo == "simple" else None,
                valor_json=opc_ids,
                valor_booleano=None,
                fecha_respuesta=datos["fecha"],
            )
        )

    RespuestaEncuesta.objects.bulk_create(crear)


class Migration(migrations.Migration):

    dependencies = [
        ("surveys", "0006_preguntas_interactivas"),
    ]

    operations = [
        migrations.RunPython(_convertir_votos, migrations.RunPython.noop),
    ]