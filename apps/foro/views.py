"""Vistas de moderación del foro (panel de Wagtail).

Además de poder editar cada tema desde el explorador de páginas, se ofrece una
vista central de moderación (``/cms/foro/moderacion/``) donde el personal puede:

- Filtrar temas por estado y categoría (con búsqueda).
- Aprobar, cerrar o fijar temas individualmente.
- Aplicar las mismas acciones en lote a varios temas a la vez.

Este enfoque es autocontenido y estable frente a los cambios del explorador
de páginas de Wagtail.
"""

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from apps.foro.models import CategoriaForo, TemaForo


@staff_member_required
def moderacion(request):
    """Panel de moderación: lista temas con filtros y acciones en lote."""

    # ── Acciones en lote ──
    if request.method == "POST":
        accion = request.POST.get("accion")
        ids = request.POST.getlist("tema_ids")
        temas = TemaForo.objects.filter(pk__in=ids)

        if accion == "aprobar":
            n = temas.update(estado=TemaForo.ESTADO_APROBADO)
            messages.success(request, f"{n} tema(s) aprobado(s).")
        elif accion == "fijar":
            n = temas.update(estado=TemaForo.ESTADO_FIJADO)
            messages.success(request, f"{n} tema(s) fijado(s).")
        elif accion == "cerrar":
            n = temas.update(estado=TemaForo.ESTADO_CERRADO)
            messages.success(request, f"{n} tema(s) cerrado(s).")
        elif accion == "pendiente":
            n = temas.update(estado=TemaForo.ESTADO_PENDIENTE)
            messages.success(request, f"{n} tema(s) devuelto(s) a pendiente.")
        return redirect("foro_moderacion")

    # ── Filtros ──
    estado = request.GET.get("estado", "")
    categoria_id = request.GET.get("categoria", "")
    q = (request.GET.get("q") or "").strip()

    temas = TemaForo.objects.all().select_related("categoria", "autor").order_by("-fecha_creacion")

    if estado:
        temas = temas.filter(estado=estado)
    if categoria_id:
        temas = temas.filter(categoria_id=categoria_id)
    if q:
        temas = temas.filter(Q(title__icontains=q) | Q(cuerpo__icontains=q))

    categorias = CategoriaForo.objects.filter(activo=True).order_by("orden", "nombre")

    pagina = request.GET.get("page")
    paginator = Paginator(temas, 25)
    try:
        temas_pag = paginator.page(pagina)
    except PageNotAnInteger:
        temas_pag = paginator.page(1)
    except EmptyPage:
        temas_pag = paginator.page(paginator.num_pages)

    context = {
        "temas": temas_pag,
        "categorias": categorias,
        "estado": estado,
        "categoria_id": categoria_id,
        "q": q,
        "estados": TemaForo.ESTADO_CHOICES,
        "sidebar": False,  # vista de página completa dentro del admin
    }
    return render(request, "foro/admin/moderacion.html", context)


@staff_member_required
def moderar_tema(request, tema_id, accion):
    """Acción de moderación sobre un único tema (aprobar/fijar/cerrar/pendiente)."""
    tema = get_object_or_404(TemaForo, pk=tema_id)
    if accion == "aprobar":
        tema.estado = TemaForo.ESTADO_APROBADO
        messages.success(request, f"Tema aprobado: {tema.title}")
    elif accion == "fijar":
        tema.estado = TemaForo.ESTADO_FIJADO
        messages.success(request, f"Tema fijado: {tema.title}")
    elif accion == "cerrar":
        tema.estado = TemaForo.ESTADO_CERRADO
        messages.success(request, f"Tema cerrado: {tema.title}")
    elif accion == "pendiente":
        tema.estado = TemaForo.ESTADO_PENDIENTE
        messages.success(request, f"Tema devuelto a pendiente: {tema.title}")
    else:
        messages.error(request, "Acción no reconocida.")
        return redirect("foro_moderacion")
    tema.save(update_fields=["estado", "fecha_modificacion"])
    return redirect("foro_moderacion")
