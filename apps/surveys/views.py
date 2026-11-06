"""
Vistas del sistema de encuestas avanzado.

- vote_view: procesa el POST del formulario de votacion (todos los tipos).
- autosave_view: guarda progreso parcial en la sesion (JSON).
- encuesta_gracias: muestra el mensaje de agradecimiento.
- estadisticas_view: panel de estadisticas por tipo (solo staff).
- exportar_csv: exporta respuestas a CSV columnar (solo staff).
- encuesta_modal_data: endpoint JSON para el modal.
"""
import csv
import json
from datetime import datetime, time

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.core.mail import send_mail
from django.db import models
from django.db.models import Count
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.surveys.forms import EncuestaForm
from apps.surveys.logica import invalidar_cache_encuestas
from .models import (
    Encuesta,
    Opcion,
    Participacion,
    RespuestaEncuesta,
    TIPOS_ESCALA,
    TIPOS_MATRIZ,
    TIPOS_OPCIONES,
    TIPOS_RANKING,
    TIPOS_SINO,
    TIPOS_TEXTO,
    TIPOS_SLIDER,
)


def _step_to_aware(moment):
    """Vuelve consciente (tz) un datetime naive respetando USE_TZ."""
    from django.conf import settings

    if settings.USE_TZ and moment.tzinfo is None:
        return timezone.make_aware(moment)
    return moment


def _get_session_key(request):
    """Obtiene o crea la clave de sesion."""
    if not request.session.session_key:
        request.session.create()
    return request.session.session_key


def _sesion_autosave_key(encuesta_id):
    return f"survey_autosave_{encuesta_id}"


def _guardar_autosave(request, encuesta_id, respuestas):
    """Guarda las respuestas parciales en la sesion (dict pregunta_id -> valor)."""
    request.session[_sesion_autosave_key(encuesta_id)] = respuestas
    request.session.modified = True


def _leer_autosave(request, encuesta_id):
    return request.session.get(_sesion_autosave_key(encuesta_id), {})


# ── Persistencia de una respuesta segun tipo ─────────────────
def _respuesta_desde_cleaned(pregunta, participacion, valor):
    """Construye una RespuestaEncuesta a partir de un valor ya limpiado."""
    tipo = pregunta.tipo
    r = RespuestaEncuesta(
        participacion=participacion,
        pregunta=pregunta,
        valor_json=[],
    )
    if tipo in ("simple", "imagenes", "par"):
        r.opcion_id = int(valor)
        r.valor_json = [int(valor)]
    elif tipo == "multiple":
        ids = [int(x) for x in valor]
        r.valor_json = ids
        r.opcion_id = ids[0] if len(ids) == 1 else None
    elif tipo in TIPOS_ESCALA | {TIPOS_SLIDER, "numero"}:
        from decimal import Decimal

        num = Decimal(str(valor))
        if tipo == "numero" and num == num.to_integral_value():
            num = num.to_integral_value()
        r.valor_numero = num
    elif tipo == TIPOS_SINO:
        r.valor_booleano = valor == "si"
    elif tipo in TIPOS_TEXTO:
        r.valor_texto = valor
    elif tipo == "fecha":
        r.valor_fecha = _step_to_aware(datetime.combine(valor, time.min))
    elif tipo == "hora":
        r.valor_fecha = _step_to_aware(datetime.combine(timezone.localdate(), valor))
    elif tipo == TIPOS_RANKING:
        r.valor_json = [int(x) for x in valor]
    elif tipo == TIPOS_MATRIZ:
        r.valor_json = valor
    return r


# ── Notificaciones ────────────────────────────────────────────
def _enviar_notificaciones(request, encuesta, participacion):
    """Envia notificacion al admin (si esta configurado) y confirmacion al
    participante (si dejo correo y esta activado)."""
    if encuesta.notificar_admin:
        destino_raw = encuesta.correo_admin or None
        from django.conf import settings

        destino = [x.strip() for x in destino_raw.split(",") if x.strip()] if destino_raw else [settings.DEFAULT_FROM_EMAIL]
        try:
            send_mail(
                subject=f"[Encuestas SASA] Nuevas respuestas: {encuesta.titulo_publico}",
                message=(
                    f"Se registro una nueva participacion en la encuesta "
                    f"'{encuesta.titulo_publico}'.\n\n"
                    f"Respuestas: {RespuestaEncuesta.objects.filter(participacion=participacion).count()}\n"
                    f"Momento: {timezone.now():%d/%m/%Y %H:%M}"
                ),
                from_email=None,
                recipient_list=destino,
                fail_silently=True,
            )
        except Exception:
            pass

    if encuesta.notificar_participante and participacion.correo_participante:
        try:
            send_mail(
                subject=encuesta.titulo_publico,
                message=f"{encuesta.mensaje_agradecimiento}\n\nEncuesta: {encuesta.titulo_publico}",
                from_email=None,
                recipient_list=[participacion.correo_participante],
                fail_silently=True,
            )
        except Exception:
            pass


# ── Modal data endpoint ───────────────────────────────────────
def encuesta_modal_data(request):
    """GET /encuestas/modal-data/ → JSON con los datos de la encuesta para el modal."""
    encuesta = None
    ahora = timezone.now()
    for enc in Encuesta.objects.filter(
        activa=True,
        tipo_encuesta="campana",
        mostrar_modal=True,
        mostrar_modal_primera_visita=True,
    ).order_by("-fecha_inicio"):
        if enc.esta_vigente():
            encuesta = enc
            break

    if not encuesta:
        return JsonResponse({"show_modal": False})

    session_key = _get_session_key(request)
    ya_completo = Participacion.objects.filter(
        encuesta=encuesta,
        session_key=session_key,
        completada=True,
    ).exists()

    if ya_completo:
        return JsonResponse({"show_modal": False})

    return JsonResponse({
        "show_modal": True,
        "encuesta_id": encuesta.pk,
        "titulo": encuesta.titulo_publico,
        "descripcion": encuesta.descripcion,
        "dias_supresion": encuesta.dias_supresion_modal,
        "url_formulario": f"/encuestas/{encuesta.pk}/votar/",
    })


# ── Aceptar encuesta ──────────────────────────────────────────
@require_POST
def aceptar_encuesta(request, encuesta_id):
    """POST /encuestas/<id>/aceptar/ → registra participacion si esta pendiente."""
    encuesta = get_object_or_404(Encuesta, pk=encuesta_id, activa=True)
    if not encuesta.esta_vigente():
        return JsonResponse({"error": "Encuesta no vigente."}, status=400)

    session_key = _get_session_key(request)
    if not encuesta.es_pendiente_para(session_key):
        return JsonResponse({"error": "Ya respondiste esta encuesta."}, status=400)

    participacion, _ = Participacion.objects.get_or_create(
        encuesta=encuesta,
        session_key=session_key,
        completada=False,
        defaults={"session_key": session_key},
    )

    return JsonResponse({"url_formulario": f"/encuestas/{encuesta.pk}/votar/"})


# ── Autoguardado parcial (sesion) ─────────────────────────────
@require_POST
def autosave_view(request, encuesta_id):
    """POST /encuestas/<id>/autoguardar/ → guarda progreso parcial en la sesion.

    Cuerpo: JSON {"respuestas": {"pregunta_<id>": valor}}
    """
    encuesta = get_object_or_404(Encuesta, pk=encuesta_id)
    if not encuesta.esta_vigente():
        return JsonResponse({"error": "Encuesta no vigente."}, status=400)

    try:
        payload = json.loads(request.body.decode("utf-8") or b"{}")
    except ValueError:
        return JsonResponse({"error": "JSON invalido."}, status=400)

    respuestas = payload.get("respuestas", {})
    current = _leer_autosave(request, encuesta.pk)
    current.update(respuestas)
    _guardar_autosave(request, encuesta.pk, current)

    return JsonResponse({"ok": True, "guardadas": len(current)})


# ── Votar ─────────────────────────────────────────────────────
def vote_view(request, encuesta_id):
    """GET: formulario de la encuesta. POST: procesa y guarda respuestas."""
    encuesta = get_object_or_404(Encuesta, pk=encuesta_id, activa=True)

    if not encuesta.esta_vigente():
        messages.warning(request, "Esta encuesta no esta vigente o ya cerro.")
        return redirect("/")

    session_key = _get_session_key(request)
    if not encuesta.es_pendiente_para(session_key):
        messages.info(request, "Ya participaste en esta encuesta. Si es fija, podras responder de nuevo mas adelante.")
        return redirect("/")

    participacion, _ = Participacion.objects.get_or_create(
        encuesta=encuesta,
        session_key=session_key,
        completada=False,
        defaults={"session_key": session_key},
    )

    autosave = _leer_autosave(request, encuesta.pk) if encuesta.autoguardar else {}
    preguntas = list(encuesta.preguntas_ordenadas())

    initial = {}
    if autosave:
        for pregunta in preguntas:
            valor = autosave.get(f"pregunta_{pregunta.pk}")
            if valor is None:
                continue
            if pregunta.tipo in ("multiple", TIPOS_RANKING, TIPOS_MATRIZ):
                try:
                    initial[f"pregunta_{pregunta.pk}"] = json.loads(valor) if isinstance(valor, str) else valor
                except ValueError:
                    initial[f"pregunta_{pregunta.pk}"] = valor
            elif pregunta.tipo in TIPOS_TEXTO:
                initial[f"pregunta_{pregunta.pk}"] = valor
            elif pregunta.tipo in TIPOS_OPCIONES:
                try:
                    initial[f"pregunta_{pregunta.pk}"] = json.loads(valor) if isinstance(valor, str) else valor
                except ValueError:
                    initial[f"pregunta_{pregunta.pk}"] = valor
            elif pregunta.tipo in ("fecha", "hora", TIPOS_SINO):
                initial[f"pregunta_{pregunta.pk}"] = valor
            else:
                try:
                    initial[f"pregunta_{pregunta.pk}"] = json.loads(valor) if isinstance(valor, str) else valor
                except ValueError:
                    initial[f"pregunta_{pregunta.pk}"] = valor

    if request.method == "POST":
        form = EncuestaForm(encuesta, request.POST, initial=initial)
        if form.is_valid():
            # Borrar respuestas parciales previas de esta participacion (reintentos)
            RespuestaEncuesta.objects.filter(participacion=participacion).delete()

            correo = request.POST.get("correo_participante", "").strip()
            if correo:
                participacion.correo_participante = correo
                participacion.save(update_fields=["correo_participante"])

            respuestas = []
            for pregunta in preguntas:
                field_name = f"pregunta_{pregunta.pk}"
                valor = form.cleaned_data.get(field_name)
                if valor in (None, ""):
                    continue
                respuestas.append(_respuesta_desde_cleaned(pregunta, participacion, valor))

            RespuestaEncuesta.objects.bulk_create(respuestas)

            participacion.completada = True
            participacion.fecha_completada = timezone.now()
            participacion.save(update_fields=["completada", "fecha_completada"])

            invalidar_cache_encuestas(session_key)
            if encuesta.autoguardar:
                request.session.pop(_sesion_autosave_key(encuesta.pk), None)

            _enviar_notificaciones(request, encuesta, participacion)

            messages.success(request, encuesta.mensaje_agradecimiento)
            return render(request, "surveys/gracias.html", {"encuesta": encuesta})
        else:
            messages.error(request, "Hubo un error al procesar tu respuesta. Revisa las preguntas marcadas.")
    else:
        form = EncuestaForm(encuesta, initial=initial)

    return render(request, "surveys/votar.html", {
        "encuesta": encuesta,
        "form": form,
        "preguntas": preguntas,
        "autosave": autosave,
    })


# ── Estadisticas (solo staff) ─────────────────────────────────
@staff_member_required
def estadisticas_view(request, encuesta_id):
    """Muestra estadisticas detalladas de una encuesta por tipo de pregunta."""
    encuesta = get_object_or_404(Encuesta, pk=encuesta_id)
    total_completadas = encuesta.total_participaciones()
    estadisticas = encuesta.estadisticas()

    return render(request, "surveys/estadisticas.html", {
        "encuesta": encuesta,
        "total_completadas": total_completadas,
        "estadisticas": estadisticas,
    })


# ── Exportar CSV ──────────────────────────────────────────────
@staff_member_required
def exportar_csv(request, encuesta_id):
    """Exporta respuestas en formato columnar: una fila por participacion
    y una columna por pregunta (formato adaptado al tipo)."""
    encuesta = get_object_or_404(Encuesta, pk=encuesta_id)

    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = (
        f'attachment; filename="encuesta_{encuesta.pk}_respuestas.csv"'
    )

    preguntas = list(encuesta.preguntas_ordenadas())
    writer = csv.writer(response)
    header = ["Participacion", "Fecha", "Correo"]
    header += [f"P: {p.texto}" for p in preguntas]
    if encuesta.preguntar_correo:
        header += ["Correo participante"]
    writer.writerow(header)

    preguntas_ids = [p.pk for p in preguntas]
    opciones_por_pregunta = (
        Opcion.objects.filter(pregunta_id__in=preguntas_ids)
        .order_by("orden", "pk")
    )
    texto_opcion = {o.pk: o.texto for o in opciones_por_pregunta}

    participaciones = (
        Participacion.objects.filter(
            encuesta=encuesta, completada=True,
        )
        .order_by("fecha_completada")
        .prefetch_related("respuestas")
    )

    def valor_csv(r):
        """Versión CSV de una respuesta sin consultar la BD."""
        pregunta_tipo = r.pregunta.tipo
        if pregunta_tipo in TIPOS_ESCALA | {TIPOS_SLIDER, "numero"}:
            return r.valor_numero
        if pregunta_tipo == TIPOS_SINO:
            return "Si" if r.valor_booleano else "No"
        if pregunta_tipo == "fecha":
            return r.valor_fecha.date().isoformat() if r.valor_fecha else ""
        if pregunta_tipo == "hora":
            return r.valor_fecha.strftime("%H:%M") if r.valor_fecha else ""
        if pregunta_tipo in TIPOS_TEXTO:
            return r.valor_texto
        if pregunta_tipo == TIPOS_MATRIZ:
            if isinstance(r.valor_json, dict):
                return "; ".join(f"{k}: {v}" for k, v in r.valor_json.items())
            return ""
        textos = []
        ids = r.valor_json if isinstance(r.valor_json, list) else []
        if r.opcion_id and r.opcion_id not in ids:
            ids = [r.opcion_id] + ids
        if ids:
            textos = [texto_opcion.get(i, str(i)) for i in ids]
        return ", ".join(textos)

    for part in participaciones:
        respuestas = {r.pregunta_id: r for r in part.respuestas.all()}
        fila = [
            part.id,
            part.fecha_completada.strftime("%d/%m/%Y %H:%M") if part.fecha_completada else "",
            part.correo_participante or "",
        ]
        for p in preguntas:
            r = respuestas.get(p.pk)
            fila.append(valor_csv(r) if r else "")
        writer.writerow(fila)

    return response


# ── Lista de encuestas (staff) ───────────────────────────────
@staff_member_required
def encuesta_list_view(request):
    """Lista todas las encuestas agrupadas por tipo con links a estadisticas."""
    qs = Encuesta.objects.annotate(
        total_completadas=Count(
            "participaciones",
            filter=models.Q(participaciones__completada=True),
        )
    ).order_by("-fecha_inicio")

    grupos = [
        {
            "titulo": "Encuestas de campana",
            "tipo": "campana",
            "buscar": "de campana",
            "objeto": qs.filter(tipo_encuesta="campana"),
        },
        {
            "titulo": "Encuestas fijas",
            "tipo": "fija",
            "buscar": "fijas",
            "objeto": qs.filter(tipo_encuesta="fija"),
        },
    ]

    return render(request, "surveys/encuesta_list.html", {
        "grupos": grupos,
    })