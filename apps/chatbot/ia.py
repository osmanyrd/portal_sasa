"""
Chatbot RAG — Orquestador IA.

Flujo de una consulta:

  1. Normalizar y validar la pregunta.
  2. Moderar (palabras prohibidas, jailbreak, datos sensibles).
  3. Rate limiting por IP.
  4. Caché de respuestas idénticas (si está activa).
  5. Recuperar fragmentos relevantes (búsqueda vectorial).
  6. Generar la respuesta (LLM configurado o componedor local).
  7. Persistir la conversación (usuario + bot) y los registros legacy.
  8. Detectar escalado a humano.

El módulo no depende de paquetes externos obligatorios.
"""
from __future__ import annotations

import hashlib
import logging
import unicodedata

from django.utils import timezone

from apps.chatbot.constantes import CACHE_RESPUESTA_HORAS
from apps.chatbot.llm_cliente import generar as generar_llm
from apps.chatbot.seguridad import (
    hash_sesion,
    limitar,
    moderar,
    normalizar,
    sugerir_contacto_humano,
)
from apps.chatbot.vectorstore import buscar_fragmentos

logger = logging.getLogger(__name__)

# Stop words para detección ligera de idioma
_ES = {
    "hola", "gracias", "servicios", "automotores", "agendar", "cita",
    "resolver", "ayuda", "contacto", "horarios", "ubicación", "precio",
    "cómo", "que", "para", "usted", "tienen", "está", "su", "nos",
}
_EN = {
    "hello", "thanks", "help", "schedule", "booking", "services",
    "hours", "location", "price", "how", "what", "for", "you", "your",
}


def detectar_idioma(texto: str) -> str:
    """Detección ligera es/en mediante stop words."""
    t = unicodedata.normalize("NFD", texto or "").lower()
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    palabras = {p.rstrip(".,;:!?") for p in t.split()}
    n_es = len(palabras & _ES)
    n_en = len(palabras & _EN)
    return "es" if n_es >= n_en else ("en" if n_en else "es")


def _respuesta_cachear(pregunta: str, cfg):
    from apps.chatbot.models import RespuestaCache

    h = hashlib.sha256(normalizar(pregunta).encode("utf-8")).hexdigest()
    try:
        resp = RespuestaCache.objects.filter(
            hash_pregunta=h, expira_en__gt=timezone.now()
        ).first()
        if resp:
            return resp
    except Exception:
        return None
    return None


def _guardar_cache(pregunta: str, cfg, datos: dict):
    from django.utils import timezone as tz

    from apps.chatbot.models import RespuestaCache

    # No cachear respuestas vacías / sin fuentes / sin éxito real
    if not datos.get("fuentes") and not datos.get("respondido"):
        return
    if datos.get("backend") in ("ninguno", ""):
        return
    try:
        h = hashlib.sha256(normalizar(pregunta).encode("utf-8")).hexdigest()
        RespuestaCache.objects.update_or_create(
            hash_pregunta=h,
            defaults={
                "respuesta": datos.get("respuesta", ""),
                "fuentes": datos.get("fuentes", []),
                "puntuacion": datos.get("puntuacion", 0.0),
                "sugerencias": datos.get("sugerencias", []),
                "expira_en": tz.now() + tz.timedelta(hours=CACHE_RESPUESTA_HORAS),
            },
        )
    except Exception:
        logger.warning("No se pudo guardar la caché de respuesta", exc_info=True)


# ── Flujo principal ────────────────────────────────────────────────────────── #


def generar_respuesta(request=None, pregunta: str = "", session_id: str = "",
                      ip: str = "") -> dict:
    """Procesa una consulta completa y devuelve la respuesta del bot."""
    from apps.chatbot.models import (
        ConfiguracionChatbot,
        ConversacionChat,
        FragmentoDocumento,
        MensajeChat,
        RegistroConversacion,
    )

    cfg = ConfiguracionChatbot.obtener(request)
    pregunta = (pregunta or "").strip()
    ip = ip or (getattr(request, "META", {}).get("REMOTE_ADDR", "") if request else "")

    # 1) Validación básica de longitud
    max_car = cfg.max_caracteres_pregunta or 500
    if not pregunta:
        return _respuesta_basica("Por favor escribe tu pregunta.", "ok", session_id)
    if len(pregunta) > max_car:
        return _respuesta_basica(
            f"Tu pregunta es muy larga (máximo {max_car} caracteres). "
            "Resúmela un poco y vuelve a intentarlo.",
            "ok",
            session_id,
        )

    # 2) Rate limiting por IP
    if ip:
        permitido, espera = limitar(ip, limite=_limite_por_minuto(cfg))
        if not permitido:
            return _respuesta_basica(
                f"Has alcanzado el límite de preguntas por minuto. "
                f"Espera unos {max(1, int(espera))} segundos.",
                "ok",
                session_id,
            )

    # 3) Moderación
    mod = moderar(pregunta) if cfg.moderacion_activa else {"bloqueado": False}
    if mod.get("bloqueado"):
        return _respuesta_basica(
            cfg.mensaje_bloqueado or
            "No puedo responder a esa consulta. Si necesitas información de "
            "nuestros servicios estaré encantado de ayudarte.",
            mod.get("categoria", "bloqueado"),
            session_id,
            alerta=mod.get("detalle", ""),
        )

    # 4) Sesión / historial
    sesion_key = session_id or hash_sesion(ip) or "anonimo"
    conversacion = (
        ConversacionChat.objects.filter(session_key=sesion_key, sesion_cerrada=False)
        .order_by("-iniciada_en")
        .first()
    )
    if conversacion is None:
        conversacion = ConversacionChat.objects.create(
            session_key=sesion_key, idioma=detectar_idioma(pregunta)
        )

    historial = [
        {"rol": m.rol, "contenido": m.contenido}
        for m in conversacion.mensajes.order_by("timestamp")[: cfg.max_mensajes_sesion]
    ]
    if len(historial) >= (cfg.max_mensajes_sesion or 50):
        return _respuesta_basica(
            "Has usado el máximo de mensajes en esta sesión. "
            "Puedes recargar la página o contactar a un asesor.",
            "ok",
            sesion_key,
            sesion_agotada=True,
        )

    # 5) Caché de respuestas (solo hits con contenido real)
    if cfg.cache_respuestas:
        cache_hit = _respuesta_cachear(pregunta, cfg)
        if cache_hit and (cache_hit.fuentes or cache_hit.puntuacion >= 0.05):
            respuesta_datos = {
                "respuesta": cache_hit.respuesta,
                "respondido": bool(cache_hit.respuesta),
                "backend": "cache",
                "puntuacion": cache_hit.puntuacion,
                "fuentes": cache_hit.fuentes,
                "escalable": not bool(cache_hit.respuesta),
                "alerta": "",
            }
            _persistir(conversacion, pregunta, respuesta_datos, ip, sesion_key)
            return _enriquecer(respuesta_datos, sesion_key)

    # 6) Recuperación de fragmentos
    fragmentos = buscar_fragmentos(pregunta, cfg)

    # 6b) Fallback clásico: si no se recuperó nada, probar el motor
    #     lexical de sinónimos (rápido y sin vecinos).
    if not fragmentos:
        respuesta_clasica = _buscar_clasico(pregunta)
        if respuesta_clasica:
            _persistir(conversacion, pregunta, respuesta_clasica, ip, sesion_key)
            _guardar_cache(pregunta, cfg, respuesta_clasica)
            return _enriquecer(respuesta_clasica, sesion_key)

    # 7) Generación
    texto, respondido, backend = generar_llm(cfg, fragmentos, historial, pregunta)

    mejor_sim = fragmentos[0]["puntuacion"] if fragmentos else 0.0
    escalable = sugerir_contacto_humano(
        fragmentos, mejor_sim, umbral=cfg.umbral_similitud
    )

    fuentes = _fuentes(fragmentos)
    respuesta_datos = {
        "respuesta": texto,
        "respondido": respondido,
        "backend": backend,
        "puntuacion": round(mejor_sim, 4),
        "fuentes": fuentes,
        "escalable": escalable,
        "alerta": "",
    }

    _persistir(conversacion, pregunta, respuesta_datos, ip, sesion_key)
    _guardar_cache(pregunta, cfg, respuesta_datos)
    return _enriquecer(respuesta_datos, sesion_key)


# ── Helpers ────────────────────────────────────────────────────────────────── #


def _limite_por_minuto(cfg) -> int:
    try:
        from apps.chatbot.constantes import RATE_LIMIT_POR_MINUTO

        return RATE_LIMIT_POR_MINUTO
    except Exception:
        return 12


def _respuesta_basica(mensaje: str, estado: str, session_id: str,
                      alerta: str = "", sesion_agotada: bool = False) -> dict:
    return {
        "respuesta": mensaje,
        "respondido": False,
        "puntuacion": 0.0,
        "fuentes": [],
        "escalable": estado in ("ok", "sin_informacion"),
        "alerta": alerta,
        "backend": "ninguno",
        "session_id": session_id,
        "sesion_agotada": sesion_agotada,
        "aviso_privacidad": "",
    }


def _buscar_clasico(pregunta: str):
    """Respuesta del motor clásico si encuentra algo (excluye intenciones)."""
    try:
        from apps.chatbot.clasico import buscar_respuesta

        resultado = buscar_respuesta(pregunta)
        if (
            resultado.get("intencion")
            or not resultado.get("respondido")
            or resultado.get("puntuacion", 0) < 0.2
        ):
            return None
        return {
            "respuesta": resultado.get("respuesta", ""),
            "respondido": True,
            "backend": "clasico",
            "puntuacion": round(resultado.get("puntuacion", 0.0), 4),
            "fuentes": [],
            "escalable": False,
            "alerta": "",
        }
    except Exception:
        return None


def _fuentes(fragmentos: list) -> list:
    vistos = set()
    fuentes = []
    for f in fragmentos:
        clave = (f.get("titulo"), f.get("fuente") or f.get("documento_id"))
        if clave in vistos:
            continue
        vistos.add(clave)
        fuentes.append({
            "titulo": f.get("titulo", ""),
            "fuente": f.get("fuente", "") or "",
            "fragmento_id": f.get("fragmento_id"),
            "puntuacion": f.get("puntuacion", 0.0),
        })
    return fuentes


def _persistir(conversacion, pregunta, datos: dict, ip: str, sesion_key: str) -> str:
    """Guarda los mensajes y el registro legacy. Devuelve el id del registro."""
    from apps.chatbot.models import MensajeChat, RegistroConversacion

    texto = datos.get("respuesta", "")

    MensajeChat.objects.create(
        conversacion=conversacion, rol="usuario", contenido=pregunta,
        tokens_usados=max(1, round(len(pregunta) / 4)),
    )
    MensajeChat.objects.create(
        conversacion=conversacion, rol="bot", contenido=texto,
        fragmentos_usados=[f.get("fragmento_id") for f in datos.get("fuentes", [])],
        tokens_usados=max(1, round(len(texto) / 4)),
    )
    conv_id = ""
    try:
        registro = RegistroConversacion.objects.create(
            pregunta=pregunta,
            respuesta=texto,
            puntuacion_similitud=datos.get("puntuacion", 0.0),
            respondido=datos.get("respondido", True),
            session_key=sesion_key,
            ip_address=ip or None,
        )
        conv_id = str(registro.id)
        datos["conversacion_id"] = conv_id
    except Exception:
        logger.warning("No se pudo registrar la conversación legacy", exc_info=True)
    return conv_id


def _enriquecer(datos: dict, session_id: str) -> dict:
    datos["session_id"] = session_id
    datos.setdefault("alerta", "")
    datos.setdefault("sesion_agotada", False)
    from apps.chatbot.models import ConfiguracionChatbot

    cfg = ConfiguracionChatbot.obtener()
    datos.setdefault("aviso_privacidad", cfg.aviso_privacidad or "")
    return datos