"""
Chatbot RAG — Endpoints API.

  POST /api/chatbot/consulta/   → responder una pregunta
  POST /api/chatbot/feedback/   → calificar la última respuesta (up/down o 1-5)
  POST /api/chatbot/escalar/    → solicitar contacto con un humano
  POST /api/chatbot/historial/  → historial de la sesión
  POST /api/chatbot/limpiar/    → cerrar la sesión actual
  GET  /api/chatbot/info/       → config pública del widget (sin secretos)

El motor clásico se conserva en `clasico.py`: las intenciones cordiales se
responden ahí y es el fallback si el motor RAG falla sin red / sin LLM.
"""
import json
import logging

from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET
from django.views.decorators.http import require_POST

from apps.chatbot.clasico import SUGERENCIAS_DEFAULT, buscar_respuesta as buscar_clasico
from apps.chatbot.ia import generar_respuesta
from apps.chatbot.models import (
    ConfiguracionChatbot,
    ConversacionChat,
    LeadChatbot,
    MensajeChat,
    RegistroConversacion,
)

logger = logging.getLogger(__name__)

MIN_PREGUNTA = 3


def _payload(request) -> dict:
    try:
        body = request.body or b"{}"
        data = json.loads(body)
        if not isinstance(data, dict):
            return {}
        return data
    except (json.JSONDecodeError, ValueError):
        return {}


def _get_client_ip(request) -> str:
    x_forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded:
        return x_forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "")


# ── Consulta principal ──────────────────────────────────────────────────────── #


@csrf_exempt
@require_POST
def consulta_chatbot(request):
    """POST /api/chatbot/consulta/  → { "pregunta": "...", "session_id": "..." }"""
    data = _payload(request)
    pregunta = (data.get("pregunta") or "").strip()
    session_id = (data.get("session_id") or "").strip()
    ip = _get_client_ip(request)

    if len(pregunta) < MIN_PREGUNTA:
        return JsonResponse({
            "respuesta": "Escribe al menos 3 caracteres para que pueda ayudarte.",
            "respondido": False,
            "puntuacion": 0.0,
            "fuentes": [],
            "sugerencias": SUGERENCIAS_DEFAULT,
            "session_id": session_id,
        })

    # 0) Intenciones cordiales con el motor clásico (rápido y sin costo)
    try:
        clasico = buscar_clasico(pregunta)
        if clasico.get("intencion"):
            return JsonResponse({
                "respuesta": clasico["respuesta"],
                "respondido": True,
                "puntuacion": 1.0,
                "fuentes": [],
                "backend": "clasico",
                "sugerencias": clasico.get("sugerencias", []),
                "session_id": session_id,
            })
    except Exception:
        logger.warning("Motor clásico falló; continuando con RAG", exc_info=True)

    # 1) Motor RAG (con fallbacks internos)
    try:
        resultado = generar_respuesta(request, pregunta, session_id, ip)
    except Exception:
        logger.exception("Error procesando consulta RAG; usando fallback clásico")
        try:
            clasico = buscar_clasico(pregunta)
            return JsonResponse({
                "respuesta": clasico["respuesta"],
                "respondido": clasico["respondido"],
                "puntuacion": clasico["puntuacion"],
                "fuentes": [],
                "backend": "clasico",
                "sugerencias": clasico.get("sugerencias", []),
                "session_id": session_id,
            })
        except Exception:
            return JsonResponse({"error": "No se pudo procesar la consulta."}, status=500)

    return JsonResponse(resultado)


# ── Feedback / calificación ─────────────────────────────────────────────────── #


@csrf_exempt
@require_POST
def feedback_chatbot(request):
    """
    POST /api/chatbot/feedback/
    Body: { "session_id": "...", "valoracion": "up"|"down" }  (o "puntuacion": 1-5)
    También acepta "conversacion_id" para el registro legacy.
    """
    data = _payload(request)
    session_id = (data.get("session_id") or "").strip()
    conversacion_id = (data.get("conversacion_id") or "").strip()
    valoracion = (data.get("valoracion") or data.get("feedback") or "").strip()
    puntuacion_num = data.get("puntuacion")

    actualizado = 0

    # 1) Legacy por id de registro
    if conversacion_id:
        try:
            if valoracion in ("up", "down"):
                actualizado += RegistroConversacion.objects.filter(id=conversacion_id).update(
                    feedback=valoracion)
            elif puntuacion_num is not None:
                reg = RegistroConversacion.objects.filter(id=conversacion_id).first()
                if reg:
                    reg.respondido = bool(puntuacion_num) or reg.respondido
                    reg.feedback = "up" if puntuacion_num else "down"
                    reg.save(update_fields=["feedback", "respondido"])
                    actualizado += 1
        except Exception:
            logger.warning("Feedback legacy no aplicado", exc_info=True)

    # 2) Feedback del último mensaje del bot en la sesión
    if session_id:
        ultimo_bot = (
            MensajeChat.objects.filter(
                conversacion__session_key=session_id,
                conversacion__sesion_cerrada=False,
                rol="bot",
            )
            .order_by("-timestamp")
            .first()
        )
        if ultimo_bot:
            if valoracion == "up":
                ultimo_bot.calificacion = 1
                actualizado += 1
            elif valoracion == "down":
                ultimo_bot.calificacion = 0
                actualizado += 1
            elif puntuacion_num is not None:
                ultimo_bot.calificacion = min(5, max(1, int(puntuacion_num)))
                actualizado += 1
            if actualizado:
                ultimo_bot.save(update_fields=["calificacion"])

    if not actualizado:
        return JsonResponse({"ok": False, "error": "Sesión o conversación no encontrada."}, status=404)
    return JsonResponse({"ok": True})


# ── Escalado a humano ───────────────────────────────────────────────────────── #


@csrf_exempt
@require_POST
def escalar_chatbot(request):
    """
    POST /api/chatbot/escalar/
    Body: { "session_id": "...", "nombre": "...", "telefono": "...", "motivo": "..." }
    """
    data = _payload(request)
    session_id = (data.get("session_id") or "").strip()
    motivo = (data.get("motivo") or "").strip()
    nombre = (data.get("nombre") or "").strip()
    telefono = (data.get("telefono") or "").strip()
    ip = _get_client_ip(request)

    if not session_id and not motivo:
        return JsonResponse({"ok": False, "error": "Parámetros inválidos."}, status=400)

    conversacion = (
        ConversacionChat.objects.filter(session_key=session_id, sesion_cerrada=False)
        .order_by("-iniciada_en")
        .first()
    ) if session_id else None

    if not motivo:
        ultimo_usr = (
            conversacion.mensajes.filter(rol="usuario").order_by("-timestamp").first()
            if conversacion else None
        )
        motivo = (ultimo_usr.contenido if ultimo_usr else "")[:1500]

    LeadChatbot.objects.create(
        conversacion=conversacion,
        nombre=nombre,
        telefono=telefono,
        motivo=motivo,
    )
    if conversacion:
        conversacion.sesion_cerrada = True
        conversacion.cerrada_en = timezone.now()
        conversacion.save(update_fields=["sesion_cerrada", "cerrada_en"])

    try:
        from apps.chatbot.models import ConfiguracionChatbot

        cfg = ConfiguracionChatbot.obtener()
    except Exception:
        cfg = None
    mensaje = (cfg.mensaje_escalado if cfg else "") or (
        "Un asesor humano te contactará lo antes posible. ¡Gracias por escribirnos!"
    )
    return JsonResponse({"ok": True, "mensaje": mensaje})


# ── Historial de la sesión ──────────────────────────────────────────────────── #


@csrf_exempt
@require_POST
def historial_chatbot(request):
    """POST /api/chatbot/historial/ → { "session_id": "..." }"""
    data = _payload(request)
    session_id = (data.get("session_id") or "").strip()
    if not session_id:
        return JsonResponse({"error": "session_id requerido."}, status=400)

    conversacion = (
        ConversacionChat.objects.filter(session_key=session_id)
        .order_by("-iniciada_en")
        .first()
    )
    if not conversacion:
        return JsonResponse({"historial": [], "session_id": session_id})

    mensajes = [
        {
            "rol": m.rol,
            "contenido": m.contenido,
            "timestamp": m.timestamp.isoformat(),
        }
        for m in conversacion.mensajes.order_by("timestamp")[:100]
    ]
    return JsonResponse({"historial": mensajes, "session_id": session_id})


# ── Limpiar / cerrar sesión ─────────────────────────────────────────────────── #


@csrf_exempt
@require_POST
def limpiar_chatbot(request):
    """POST /api/chatbot/limpiar/ → { "session_id": "..." }"""
    data = _payload(request)
    session_id = (data.get("session_id") or "").strip()
    if session_id:
        actualizado = (
            ConversacionChat.objects.filter(session_key=session_id, sesion_cerrada=False)
            .order_by("-iniciada_en")
            .first()
        )
        if actualizado:
            actualizado.sesion_cerrada = True
            actualizado.cerrada_en = timezone.now()
            actualizado.save(update_fields=["sesion_cerrada", "cerrada_en"])
    return JsonResponse({"ok": True, "session_id": session_id, "nueva": True})


# ── Info pública del widget ─────────────────────────────────────────────────── #


@require_GET
def info_chatbot(request):
    """GET /api/chatbot/info/ → configuración pública (sin API keys)."""
    cfg = ConfiguracionChatbot.obtener(request)
    try:
        from apps.chatbot.embeddings import disponibilidad

        emb_disp = disponibilidad(cfg)
    except Exception:
        emb_disp = {}
    return JsonResponse({
        "nombre_asistente": cfg.nombre_asistente,
        "mensaje_bienvenida": cfg.mensaje_bienvenida,
        "aviso_privacidad": cfg.aviso_privacidad,
        "proveedor_llm": cfg.proveedor_llm,
        "streaming": cfg.streaming,
        "embeddings": emb_disp,
    })
