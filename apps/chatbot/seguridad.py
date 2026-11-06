"""
Chatbot RAG — Seguridad y moderación.

  - Moderación de contenido (palabras prohibidas, delitos, drogas, etc.)
  - Detección de datos sensibles personales en el chat (RFC, teléfono, email)
  - Protección contra fuga del prompt del sistema / jailbreak
  - Rate limiting ligero por IP usando la caché de Django
"""
from __future__ import annotations

import hashlib
import logging
import re

from django.core.cache import cache

from apps.chatbot.constantes import (
    DATOS_SENSIBLES_ACCIONES,
    DATOS_SENSIBLES_PALABRAS,
    REVELAR_DATOS,
    RUTAS_A_PROMOVER,
    TIPICOS_JAILBREAK,
    WORDS_NO_ENCONTRADO,
)

logger = logging.getLogger(__name__)


def normalizar(texto: str) -> str:
    """Normaliza una cadena para comparaciones (minúsculas, sin acentos)."""
    import unicodedata

    texto = (texto or "").strip().lower()
    texto = unicodedata.normalize("NFD", texto)
    return "".join(c for c in texto if unicodedata.category(c) != "Mn")


def moderar(texto: str) -> dict:
    """
    Analiza el texto y devuelve:
        {"bloqueado": bool, "categoria": str, "detalle": str, "niveles": {...}}
    """
    t = normalizar(texto)
    niveles = {
        "palabras_prohibidas": 0.0,
        "datos_sensibles": 0.0,
        "jailbreak": 0.0,
        "sin_informacion": 0.0,
    }

    marcadas = [p for p in DATOS_SENSIBLES_PALABRAS if p in t]
    if marcadas:
        niveles["palabras_prohibidas"] = min(1.0, len(marcadas) * 0.34)
        niveles["datos_sensibles"] = min(1.0, len(marcadas) * 0.22)

    acciones = [a for a in DATOS_SENSIBLES_ACCIONES if a in t]
    if acciones:
        niveles["datos_sensibles"] = 1.0

    # Intención de revelar datos personales (palabra sensible + frase reveladora)
    marcadas = [p for p in DATOS_SENSIBLES_PALABRAS if p in t]
    revelar = [r for r in REVELAR_DATOS if r in t]
    if marcadas and revelar:
        niveles["datos_sensibles"] = 1.0

    jailbreak = [j for j in TIPICOS_JAILBREAK if j in t]
    if jailbreak:
        niveles["jailbreak"] = 1.0

    palabras_noenc = [p for p in WORDS_NO_ENCONTRADO if p in t]
    if palabras_noenc:
        niveles["sin_informacion"] = 0.35

    # Datos personales protegidos (RFC, correo, teléfono, cuentas)
    patrones = [
        r"[A-Z]{3,4}\d{6}[A-Z0-9]{2,3}",        # RFC
        r"\b[\w.+-]+@[\w-]+\.[\w.]+\b",          # email
        r"\+\d{1,3}[\s-]?\(?\d{2,4}\)?[\s-]?\d{3,4}[\s-]?\d{3,4}",  # teléfono
        r"\d{15,16}",                            # tarjeta
    ]
    for patron in patrones:
        if re.search(patron, texto or ""):
            niveles["datos_sensibles"] = max(niveles["datos_sensibles"], 1.0)

    nivel_total = max(niveles.values())
    if nivel_total < 1.0 and not (niveles["jailbreak"] or niveles["datos_sensibles"] == 1.0):
        nivel_total = 0.0

    bloqueado = nivel_total >= 1.0
    if bloqueado:
        principales = [c for c, v in niveles.items() if v >= 1.0]
        categoria = "jailbreak" if "jailbreak" in principales else "datos_sensibles"
        detalle = {
            "jailbreak": "El mensaje intenta violar las instrucciones del asistente.",
            "datos_sensibles": "El mensaje parece pedir o revelar datos sensibles.",
        }.get(categoria, "Contenido no permitido.")
    else:
        categoria = "ok"
        detalle = ""

    return {
        "bloqueado": bloqueado,
        "categoria": categoria,
        "detalle": detalle,
        "niveles": niveles,
    }


def sugerir_contacto_humano(fragmentos: list, puntuacion: float, umbral: float) -> bool:
    """Sugiere escalar a humano cuando la búsqueda fue débil."""
    if puntuacion >= umbral and fragmentos:
        return False
    return True


def preparar_escalado(pregunta: str, respuesta: str, session_id: str,
                      ip: str = "") -> dict:
    """Datos normalizados para el LeadChatbot (escalado a humano)."""
    return {
        "nombre": "",
        "email": "",
        "telefono": "",
        "pregunta": pregunta[:1500],
        "respuesta": respuesta[:2000],
        "session_id": session_id,
        "ip": ip or "",
        "observaciones": "Generado automáticamente por el chatbot.",
        "estado": "pendiente",
    }


# ── Rate limiting ─────────────────────────────────────────────────────────── #

LIMITE_POR_VENTANA = 10      # preguntas permitidas por ventana
VENTANA_SEGUNDOS = 60


def limitar(ip: str, limite: int = LIMITE_POR_VENTANA,
            ventana: int = VENTANA_SEGUNDOS) -> tuple[bool, float]:
    """
    Control de flujo por IP. Devuelve (permitido, segundos_a_esperar).
    """
    clave = f"chatbot_ratelimit:{ip}"
    ahora = 0.0
    pasado, contador = _leer_contador(clave)
    if pasado and (ahora := _ahora()) < pasado + ventana:
        contador += 1
        if contador > limite:
            return False, max(0.0, pasado + ventana - _ahora())
    else:
        contador = 1
    _guardar_contador(clave, contador, ventana)
    return True, 0.0


def _ahora() -> float:
    import time

    return time.monotonic()


def _leer_contador(clave) -> tuple:
    valor = cache.get(clave)
    return (valor.get("inicio"), valor.get("n")) if isinstance(valor, dict) else (None, 0)


def _guardar_contador(clave, n, ventana) -> None:
    cache.set(clave, {"inicio": _ahora(), "n": n}, timeout=int(ventana) + 5)


def hash_sesion(ip: str) -> str:
    """Hash anónimo de la IP para etiquetar sesiones sin guardar la IP cruda."""
    return hashlib.sha256(f"chatbot:{ip}".encode("utf-8")).hexdigest()[:16]