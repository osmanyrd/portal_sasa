"""
Chatbot RAG — Constantes por defecto.

Valores centrales del pipeline (ingesta, embeddings, búsqueda, LLM y
seguridad). Se pueden sobrescribir desde `ConfiguracionChatbot` en el
panel de administración (Wagtail).
"""
from __future__ import annotations

# ── Chunking (ingesta) ─────────────────────────────────────────
TAMANIO_CHUNK = 800          # caracteres objetivo por fragmento (~200 tokens)
SOLAPAMIENTO_CHUNK = 100     # caracteres de solapamiento entre fragmentos
CARACTERES_POR_TOKEN = 4     # aproximación token ~ 4 caracteres

# ── Búsqueda semántica ─────────────────────────────────────────
LIMITE_FRAGMENTOS = 5        # k en la búsqueda por similitud
UMBRAL_SIMILITUD = 0.30      # similitud coseno mínima para aceptar un fragmento
UMBRAL_SIN_LLM = 0.35        # umbral para responder con el componedor local

# ── Prompt / generación ────────────────────────────────────────
TEMPERATURA_DEFECTO = 0.3
MAX_TOKENS_DEFECTO = 500
MAX_FRAGMENTOS_PROMPT = 5
MAX_MENSAJES_HISTORIAL = 6   # últimos N mensajes enviados al LLM

# ── Conversación / seguridad ────────────────────────────────────
MAX_CARACTERES_PREGUNTA = 500
MAX_MENSAJES_SESION = 50
RATE_LIMIT_POR_MINUTO = 12   # preguntas por minuto por IP
CACHE_RESPUESTA_HORAS = 1    # respuestas idénticas cacheadas 1h

# ── Idiomas ────────────────────────────────────────────────────
IDIOMA_DEFECTO = "es"
SIGNALS_PESO = {"es": 1.0, "en": 1.0}  # placeholder para futura ponderación

# ── Proveedor LLM (valores por defecto) ────────────────────────
PROVEEDOR_LLM_DEFECTO = "ollama"
MODELOS_LLM_SUGERIDOS = {
    "ollama": "llama3.2",
    "openai": "gpt-4o-mini",
    "lmstudio": "local-model",
    "anthropic": "claude-3-5-haiku-latest",
}
URL_API_POR_PROVEEDOR = {
    "ollama": "http://localhost:11434",
    "lmstudio": "http://localhost:1234/v1",
    "openai": "https://api.openai.com/v1",
    "anthropic": "https://api.anthropic.com/v1",
}

# ── Embeddings ─────────────────────────────────────────────────
PROVEEDOR_EMBEDDINGS_DEFECTO = "hash"          # sin dependencias externas
MODELO_EMBEDDINGS_DEFECTO = "paraphrase-multilingual-MiniLM-L12-v2"
HASH_EMBEDDINGS_DIMENSION = 384                # dimensión del vector local
HASH_EMBEDDINGS_HASHES = 6                     # nº de hashes (caracteres ≥4)

# ── Palabras prohibidas (moderación) ───────────────────────────
# Lista mínima de arranque; ampliable desde el panel o este archivo.
PALABRAS_PROHIBIDAS = [
    "hijo de puta", "hijueputa", "conchatumare", "puta", "mierda",
    "pendejo", "culiao", "weon", "güey", "estúpido", "estupido",
    "idiota", "imbecil", "imbécil", "tarado", "malparido", "maricón",
    "maricon", "cabron", "cabrón", "perra", "zorra", "chupa",
    "vete a la mierda", "analfabeto", "muerto de hambre",
]

CONFIANZA_MINIMA = 0.55  # confianza global mínima (puntuación del bot)

# ── Moderación / datos sensibles ─────────────────────────────
# Palabras cuya mención dispara la moderación (nivel por incidencia).
DATOS_SENSIBLES_PALABRAS = [
    "tarjeta", "crédito", "credito", "cuenta", "clave", "contraseña",
    "password", "iban", "clabe", "cuenta bancaria", "nss", "curp",
    "rfc", "ine", "pasaporte", "información personal", "datos personales",
    "número de cuenta", "numero de cuenta", "deuda", "aviso de privacidad",
]

# Acciones claramente prohibidas en el chat (bloquean de inmediato).
DATOS_SENSIBLES_ACCIONES = [
    "proporciona tu", "proporciona mi", "dame tu", "dame mi",
    "comparte tu", "comparte mi", "cuál es mi", "cual es mi",
    "envíame", "envia mi", "quien soy",
]

# Frases de intención de revelar datos (combinadas con una palabra sensible
# disparan la moderación: "haras una pregunta peligrosa" -> bloqueado).
REVELAR_DATOS = [
    "numero secreto", "numero de tarjeta", "no de tarjeta", "n de credito",
    "mi tarjeta", "mis datos", "mi cuenta", "mi clave", "mi contrasena",
    "mi contraseña", "sacar dinero", "cual es mi", "dame mi", "cual es tu",
    "dime mi", "dame tus", "movi mi", "mi nss", "mi curp", "mi rfc",
    "mi ine", "numero de cuenta",
]

# Intentos comunes de fuga del prompt del sistema.
TIPICOS_JAILBREAK = [
    "ignora tus instrucciones", "ignora las instrucciones",
    "actúa como", "actua como", "déjame de lado tus reglas",
    "obvia tus reglas", "eres libre", "sin restricciones",
    "system prompt", "instrucciones anteriores", "prompt inicial",
    "repítete tu", "repetite tu", "release your instructions",
]

# Frases típicas cuando el usuario no encontró lo que busca.
WORDS_NO_ENCONTRADO = [
    "no encuentro", "no aparece", "no existe", "no está",
    "buscando", "cómo contacto", "como contacto", "a quién llamo",
    "no me sirvió", "no me sirvio", "inútil",
]

# Rutas/secciones que el bot promoverá al no hallar una respuesta contundente.
RUTAS_A_PROMOVER = [
    "asesor virtual", "escalar", "agendar", "agenda", "cita",
    "success", "laurel", "colaboradores", "contacto", "becas",
]