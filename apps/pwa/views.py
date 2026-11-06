"""PWA de Servicios Automotores S.A.

Servidores para el Web App Manifest, el Service Worker y la página offline.
Todo se sirve vía Django para garantizar las rutas de raíz (/manifest.webmanifest,
/sw.js, /offline.html) y los Content-Type correctos.
"""
from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.template.loader import render_to_string
from django.views.decorators.cache import cache_control

ICONOS = [
    ("icons/icon-192.png", "192x192", "any"),
    ("icons/icon-512.png", "512x512", "any"),
    ("icons/maskable-512.png", "512x512", "maskable"),
]


def _abs(request, path):
    # URLs construidas desde el host de la petición (sin usar).
    return request.build_absolute_uri(path)


@cache_control(max_age=86400)
def manifest(request):
    """GET /manifest.webmanifest — Web App Manifest (JSON).

    Las rutas start_url/scope/iconos son RELATIVAS ("/"): el navegador las
    resuelve contra el origen actual del documento. Así Chrome valida
    instalabilidad aunque el usuario entre por localhost, 127.0.0.1 o
    cualquier dominio (evita fallos por origen distinto en los iconos).
    """
    data = {
        "id": "/",
        "name": "Servicios Automotores S.A",
        "short_name": "SASA",
        "description": "Sitio oficial de Servicios Automotores S.A",
        "start_url": "/",
        "scope": "/",
        "display": "standalone",
        "orientation": "any",
        "background_color": "#FFFFFF",
        "theme_color": "#E63946",
        "categories": ["business", "automotive"],
        "icons": [
            {
                "src": settings.STATIC_URL + i,
                "sizes": s,
                "type": "image/png",
                "purpose": p,
            }
            for i, s, p in ICONOS
        ],
        "shortcuts": [
            {
                "name": "Catálogo",
                "url": "/catalogo/",
                "description": "Ver el catálogo de productos",
            },
            {
                "name": "Foro",
                "url": "/foro/",
                "description": "Ir al foro de la comunidad",
            },
        ],
    }
    response = JsonResponse(
        data,
        content_type="application/manifest+json; charset=utf-8",
        json_dumps_params={"ensure_ascii": False},
    )
    return response


@cache_control(no_cache=True, no_store=True, must_revalidate=True)
def service_worker(request):
    """GET /sw.js — Service Worker (alcance raíz).

    Se sirve sin caché para que el navegador compruebe actualizaciones.
    El cuerpo es una plantilla: genera la lista de precaché usando {% static %}.
    """
    body = render_to_string(
        "pwa/sw.js", {"STATIC_URL": settings.STATIC_URL}
    )
    response = HttpResponse(
        body, content_type="text/javascript; charset=utf-8"
    )
    response["Service-Worker-Allowed"] = "/"
    return response


def offline(request):
    """GET /offline.html — Página "Sin conexión" (precacheada por el SW)."""
    return render(request, "pwa/offline.html")