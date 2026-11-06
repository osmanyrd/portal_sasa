"""Vista API simple de informaciones recientes.

Reutiliza la misma lógica que el context processor, de modo que navbar, cartel
y API son siempre coherentes.

Respuesta JSON::

    {
      "conteo": 3,
      "indice_url": "/informaciones/",
      "recientes": [
        {"id": 10, "titulo": "...", "tipo": "aviso",
         "fecha": "2026-08-28T10:00:00-03:00", "url": "..."},
        ...
      ]
    }
"""

from django.http import JsonResponse

from apps.informaciones.context_processors import _calcular


def informaciones_recientes_api(request):
    """GET ``/api/informaciones/recientes/`` -> JSON de recientes."""
    datos = _calcular()

    body = {
        "conteo": datos["info_conteo"],
        "indice_url": datos["info_indice_url"],
        "recientes": [
            {
                "id": i["id"],
                "titulo": i["titulo"],
                "tipo": i["tipo"],
                "categoria": i.get("categoria", "informacion"),
                "fecha": i["fecha"].isoformat() if i["fecha"] else None,
                "url": i["url"],
            }
            for i in datos["info_recientes"]
        ],
    }
    return JsonResponse(body)
