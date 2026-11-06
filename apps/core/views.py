import logging
import re

from django.conf import settings
from django.contrib import messages
from django.core.mail import BadHeaderError
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_http_methods, require_POST
from wagtail.models import Page

from apps.core.forms import ContactMessageForm
from apps.core.models import ContactSubmission

logger = logging.getLogger(__name__)


class _SearchPage:
    """Minimal namespace expected by base.html OG meta tags."""
    seo_title = ""
    title = "Búsqueda"
    search_description = ""
    og_image = None
    og_title = ""
    og_description = ""


def _safe_redirect(request):
    referer = request.META.get("HTTP_REFERER")
    if referer and url_has_allowed_host_and_scheme(
        referer,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return redirect(referer)
    return redirect("/")


@require_POST
def contact_submit(request: HttpRequest) -> HttpResponse:
    form = ContactMessageForm(request.POST)
    is_htmx = request.headers.get("HX-Request") == "true"

    if not form.is_valid():
        if is_htmx:
            return render(
                request,
                "core/includes/contact_form.html",
                {"form": form},
                status=200,
            )
        return _safe_redirect(request)

    data = form.cleaned_data

    if data.get("website"):
        if is_htmx:
            return render(request, "core/includes/contact_success.html", {})
        return _safe_redirect(request)

    submission = ContactSubmission.objects.create(
        name=data["nombre"],
        email=data["email"],
        phone=data.get("telefono", ""),
        message=data["mensaje"],
    )
    _notify(submission)

    if is_htmx:
        return render(request, "core/includes/contact_success.html", {})

    messages.success(request, "Tu mensaje fue enviado correctamente. ¡Gracias!")
    return _safe_redirect(request)


def _notify(submission: ContactSubmission) -> None:
    subject = f"[Web] Nueva consulta de {submission.name}".replace("\n", " ").strip()
    body = (
        f"Nombre: {submission.name}\n"
        f"Email: {submission.email}\n"
        f"Teléfono: {submission.phone or '-'}\n\n"
        f"{submission.message}"
    )
    try:
        from django.core.mail import EmailMessage

        email = EmailMessage(
            subject=subject,
            body=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[settings.CONTACT_TO_EMAIL],
            reply_to=[submission.email],
        )
        email.send(fail_silently=False)
    except (BadHeaderError, ConnectionError, Exception) as exc:
        logger.warning(
            "No se pudo enviar el email de contacto de %s: %s",
            submission.email,
            exc,
        )


@require_http_methods(["GET"])
def buscar(request: HttpRequest) -> HttpResponse:
    """Búsqueda unificada del sitio (páginas Wagtail + catálogo ERP)."""
    q = (request.GET.get("q") or "").strip()
    resultados = None

    if q:
        pages = (
            Page.objects.live().public().search(q)
            if q
            else Page.objects.none()
        )
        resultados = []
        for p in pages:
            labels = getattr(p.specific_class._meta, "verbose_name", "") or ""
            resultados.append((p, labels))
    return render(
        request,
        "core/buscar.html",
        {
            "page": _SearchPage(),
            "q": q,
            "resultados": resultados,
        },
    )


# ---------------------------------------------------------------------------
# API /api/buscar/?q=… — JSON para el buscador del navbar (modal de resultados)
# ---------------------------------------------------------------------------

# Máxima longitud del término para evitar consultas absurdas.
Q_MAX_LEN = 200
# Resultados por tipo en la respuesta del endpoint.
Q_LIMITE = 10


def _json_tipo(page) -> str:
    """Clasifica una página para el JSON del buscador."""
    clase = page.specific_class
    app = clase._meta.app_label
    nombre = (clase.__name__ or "").lower()
    if app == "informaciones":
        return "información" if "informacion" in nombre else "novedad"
    if app == "foro":
        return "foro"
    if app == "catalogo_erp":
        return "producto"
    if app == "mapa":
        return "mapa"
    return "página"


def _json_extracto(page, max_len: int = 160) -> str:
    """Extracto breve para el JSON, según el tipo de página."""
    try:
        sp = page.specific
    except Exception:
        return ""
    for attr in ("resumen", "subtitle", "search_description"):
        texto = getattr(sp, attr, None)
        if texto:
            texto = str(texto).strip()
            if texto:
                return texto[:max_len]
    cuerpo = getattr(sp, "cuerpo", None) or getattr(sp, "body", None)
    if cuerpo:
        texto = re.sub(r"<[^>]+>", " ", str(cuerpo))
        texto = re.sub(r"\s+", " ", texto).strip()
        if texto:
            return texto[:max_len]
    return ""


def _json_miniatura(page) -> str | None:
    """URL de un thumbnail (image_rendition) si la página tiene imagen."""
    try:
        sp = page.specific
    except Exception:
        return None
    img = (
        getattr(sp, "imagen", None)
        or getattr(sp, "header_image", None)
        or getattr(sp, "og_image", None)
    )
    if not img:
        return None
    try:
        return img.get_rendition("fill-120x90").url
    except Exception:
        try:
            return img.file.url
        except Exception:
            return None


def _json_resultado(page) -> dict:
    """Construye el dict de un resultado para el endpoint JSON."""
    return {
        "title": page.title,
        "excerpt": _json_extracto(page),
        "url": page.url,
        "type": _json_tipo(page),
        "image": _json_miniatura(page),
    }


@require_http_methods(["GET"])
def api_buscar(request: HttpRequest) -> JsonResponse:
    """`/api/buscar/?q=…` → JSON con resultados para el modal del navbar.

    Busca páginas live/públicas de Wagtail (incluye novedades, informaciones,
    foro y el catálogo ERP) y devuelve hasta ``Q_LIMITE`` resultados.

    Ejemplo de respuesta::

        {
          "query": "aceite",
          "count": 2,
          "results": [
            {"title": "…", "excerpt": "…", "url": "/…/",
             "type": "novedad", "image": "/media/…"}
          ]
        }
    """
    q = (request.GET.get("q") or "").strip()
    if not q:
        return JsonResponse({"query": "", "count": 0, "has_more": False, "results": []})
    q = q[:Q_MAX_LEN]

    try:
        encontrados = list(Page.objects.live().public().search(q)[: Q_LIMITE + 1])
    except Exception:
        try:
            from wagtail.search.query import Phrase

            encontrados = list(
                Page.objects.live().public().search(Phrase(q))[: Q_LIMITE + 1]
            )
        except Exception:
            encontrados = []

    # Pedimos uno de más para saber si hay resultados adicionales ("Ver todos").
    has_more = len(encontrados) > Q_LIMITE
    pages = encontrados[:Q_LIMITE]

    results = [_json_resultado(p) for p in pages]
    return JsonResponse(
        {
            "query": q,
            "count": len(results),
            "has_more": has_more,
            "results": results,
        }
    )
