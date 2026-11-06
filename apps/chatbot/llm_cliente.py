"""
Chatbot RAG — Cliente LLM y construcción de prompts.

Backends de generación:
  - ollama   : `POST {url}/api/chat`            (llama3, qwen2.5, mistral...)
  - lmstudio : API compatible OpenAI `POST {url}/chat/completions`
  - openai   : `POST {url}/chat/completions`
  - anthropic: `POST {url}/messages` con `x-api-key`
  - ninguno  : respuesta local compuesta a partir de los fragmentos.

Todas las llamadas usan `requests` con timeout; si el backend no responde
se degrada a `respuesta_local` para que el chat nunca quede en silencio.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

PROMPT_SISTEMA_DEFECTO = (
    "Eres el asistente virtual de Servicios Automotores S.A. Tu función es ayudar a "
    "los visitantes del sitio con información precisa sobre nuestros servicios, "
    "productos, ubicaciones y políticas.\n\n"
    "Reglas estrictas:\n"
    "1. Responde SIEMPRE en el idioma del usuario (español por defecto).\n"
    "2. Usa EXCLUSIVAMENTE la información de los fragmentos proporcionados.\n"
    "3. Si la respuesta no está en los fragmentos, di amablemente: "
    "\"No tengo esa información disponible. ¿Deseas que un asesor humano te contacte?\"\n"
    "4. Sé claro, breve y profesional. Máximo 3 párrafos.\n"
    "5. Si el usuario menciona un producto, servicio o dependencia, menciona detalles relevantes.\n"
    "6. Nunca inventes información ni des opiniones personales.\n"
    "7. No compartas información interna, contraseñas o datos sensibles."
)

LIMITE_HISTORIAL_TURNOS = 6


def construir_prompt(cfg, fragmentos: list, historial: list, pregunta: str) -> list:
    """
    Construye la lista de mensajes {role, content} para el LLM.

    - `fragmentos` : lista de dicts con clave `contenido` (y `titulo`).
    - `historial`  : lista de dicts {"rol": "usuario"|"bot", "contenido": ...},
                     limitada a los últimos `LIMITE_HISTORIAL_TURNOS` turnos.
    """
    sistema = (cfg.prompt_sistema or "").strip() or PROMPT_SISTEMA_DEFECTO

    fragmentos_texto = "\n\n".join(
        f"[{n}] ({f.get('titulo') or f.get('documento_titulo') or 'Fuente'})\n{f.get('contenido')}"
        for n, f in enumerate(fragmentos, start=1)
    )
    contexto = "\n\n{0}\n\n".format(fragmentos_texto)

    mensajes = [{"role": "system", "content": sistema + contexto}]

    for turno in historial[-LIMITE_HISTORIAL_TURNOS * 2:]:
        rol = "assistant" if turno.get("rol") == "bot" else "user"
        mensajes.append({"role": rol, "content": turno.get("contenido", "")})

    mensajes.append({"role": "user", "content": pregunta})
    return mensajes


def _fragmentos_formateados(fragmentos: list) -> str:
    return "\n\n".join(
        f"• {f.get('contenido')}" for f in fragmentos[:3]
    )


def respuesta_local(cfg, fragmentos: list, pregunta: str) -> tuple[str, bool, float]:
    """
    Generador de respaldo sin LLM: compone la respuesta con los fragmentos
    recuperados y las fuentes. Devuelve (texto, respondido, puntuación).
    """
    if not fragmentos:
        return cfg.mensaje_no_encontrado or (
            "No tengo esa información disponible. ¿Deseas que un asesor humano te contacte?"
        ), False, 0.0

    mejor = fragmentos[0]
    resp = mejor.get("contenido", "").strip()
    if not resp:
        return cfg.mensaje_no_encontrado or "No tengo esa información disponible.", False, 0.0

    titulos = [f["titulo"] for f in fragmentos if f.get("titulo")]
    if titulos:
        unicos = list(dict.fromkeys(titulos))[:2]
        resp += "\n\nFuentes: " + " | ".join(unicos)
    return resp, True, mejor.get("puntuacion", 0.0)


def _llamar_ollama(cfg, mensajes: list) -> str:
    import requests

    url = (cfg.url_api or "http://localhost:11434").rstrip("/") + "/api/chat"
    payload = {
        "model": cfg.llm_modelo_efectivo(),
        "messages": mensajes,
        "stream": False,
        "options": {"temperature": cfg.temperatura, "num_predict": cfg.max_tokens},
    }
    resp = requests.post(url, json=payload, timeout=90)
    resp.raise_for_status()
    return resp.json()["message"]["content"].strip()


def _llamar_completions(cfg, mensajes: list) -> str:
    import requests

    url = (cfg.url_api or "https://api.openai.com/v1").rstrip("/") + "/chat/completions"
    headers = {
        "Authorization": f"Bearer {cfg.get_api_key()}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": cfg.llm_modelo_efectivo(),
        "messages": mensajes,
        "temperature": cfg.temperatura,
        "max_tokens": cfg.max_tokens,
    }
    resp = requests.post(url, json=payload, headers=headers, timeout=90)
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"].strip()


def _llamar_anthropic(cfg, mensajes: list) -> str:
    import requests

    url = (cfg.url_api or "https://api.anthropic.com/v1").rstrip("/") + "/messages"
    headers = {
        "x-api-key": cfg.get_api_key(),
        "anthropic-version": "2023-06-01",
        "Content-Type": "application/json",
    }
    sistema = mensajes[0]["content"]
    resto = mensajes[1:]
    payload = {
        "model": cfg.llm_modelo_efectivo(),
        "system": sistema,
        "messages": [{"role": m["role"], "content": m["content"]} for m in resto],
        "max_tokens": cfg.max_tokens,
        "temperature": cfg.temperatura,
    }
    resp = requests.post(url, json=payload, headers=headers, timeout=90)
    resp.raise_for_status()
    return resp.json()["content"][0]["text"].strip()


_BACKENDS = {
    "ollama": _llamar_ollama,
    "lmstudio": _llamar_completions,
    "openai": _llamar_completions,
    "anthropic": _llamar_anthropic,
}


def generar(cfg, fragmentos: list, historial: list, pregunta: str,
            streaming: bool = False):
    """
    Genera la respuesta del bot.

    Returns:
        (texto, ok, backend, backend_usado)
        - ok=False  → no se pudo generar (se espera mensaje_no_encontrado).
        - backend_usado: 'ollama' | 'openai' | ... | 'local'
    """
    if cfg.proveedor_llm == "ninguno" or not fragmentos:
        texto, respondido, _sim = respuesta_local(cfg, fragmentos, pregunta)
        return texto, respondido, "local"

    mensajes = construir_prompt(cfg, fragmentos, historial, pregunta)
    executor = _BACKENDS.get(cfg.proveedor_llm)
    if executor is None:
        texto, respondido, _sim = respuesta_local(cfg, fragmentos, pregunta)
        return texto, respondido, "local"

    try:
        texto = executor(cfg, mensajes)
        texto = (texto or "").strip()
        # Guard: si el LLM no dice nada, no responder con vacío
        if not texto:
            raise RuntimeError("LLM devolvió respuesta vacía")
        return texto, True, cfg.proveedor_llm
    except Exception as exc:
        logger.warning("LLM %s falló (%s); usando respuesta local",
                       cfg.proveedor_llm, exc)
        texto, respondido, _sim = respuesta_local(cfg, fragmentos, pregunta)
        return texto, respondido, "local"