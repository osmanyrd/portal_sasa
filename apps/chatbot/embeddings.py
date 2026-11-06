"""
Chatbot RAG — Motor de embeddings.

Backends configurables (sin dependencias obligatorias):

  - hash                : vector determinista local (hashing de tokens).
                          Funciona SIEMPRE, sin instalar nada.
  - sentence_transformers: modelos locales tipo
                          `paraphrase-multilingual-MiniLM-L12-v2`.
  - ollama              : `POST {url}/api/embeddings` con `nomic-embed-text`, etc.
  - openai              : `POST {url}/embeddings` (text-embedding-3-small, ...).

Si un backend no está disponible (paquete faltante o servidor caído) se
usa el `HashEmbedder` para que el sistema nunca se rompa y siga
degradando con búsqueda lexical vectorial.
"""
from __future__ import annotations

import hashlib
import logging
import re
import unicodedata

logger = logging.getLogger(__name__)

from apps.chatbot.constantes import HASH_EMBEDDINGS_DIMENSION

# caché por (proveedor, modelo)
_EMBEDDERS: dict = {}

# Mapa token -> "familia léxica" (raíz de sinónimos) del motor clásico.
# Permite que el vector hash comparta *bucket* entre variantes
# (parqueo <-> estacionamiento, telefono <-> llamar, etc.).
_FAMILIA: dict = {}
_STOP_ES: set = set()
try:
    from apps.chatbot.clasico import PALABRAS_VACIAS as _VACIAS
    from apps.chatbot.clasico import SINONIMOS as _SINONIMOS

    _STOP_ES = set(_VACIAS) | {
        "cual", "cuales", "cualquier", "tiempo", "forma", "manera",
        "tipo", "cosa", "mismo", "gran", "buena", "bien", "mal",
    }
    for _raiz, _variantes in _SINONIMOS.items():
        _FAMILIA[_raiz] = _raiz
        for _v in _variantes:
            _FAMILIA.setdefault(_v, _raiz)
except Exception:  # pragma: no cover
    _FAMILIA = {}


# ── Base ──────────────────────────────────────────────────────────────────── #


class Embedder:
    """Contrato mínimo de un embedder."""

    proveedor = ""
    modelo = ""
    dimension = 0
    disponible = True

    def embed(self, texto: str) -> list:
        """Devuelve el vector normalizado L2 del texto."""
        raise NotImplementedError


# ── Local determinista (fallback universal) ───────────────────────────────── #

class HashEmbedder(Embedder):
    """Vector TF con hashing de palabras y bigramas (sin dependencias)."""

    proveedor = "hash"
    dimension = HASH_EMBEDDINGS_DIMENSION

    def __init__(self, modelo="hash-v2", dimension=HASH_EMBEDDINGS_DIMENSION):
        self.modelo = modelo
        self.dimension = dimension

    def _normalizar(self, texto):
        texto = texto.lower().strip()
        texto = unicodedata.normalize("NFD", texto)
        texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
        return re.sub(r"[^a-z0-9áéíóúñü\u00c0-\u00ff ]", " ", texto)

    def _bucket(self, token: str) -> int:
        return int(hashlib.md5(token.encode("utf-8")).hexdigest(), 16) % self.dimension

    def embed(self, texto: str) -> list:
        vec = [0.0] * self.dimension
        norm = self._normalizar(texto)
        palabras = norm.split()
        if not palabras:
            return vec

        # Pesos por palabra (stopwords muy ligeras, términos reales a tope)
        pesos = [0.15 if t in _STOP_ES else 1.0 for t in palabras]

        tokens: list[tuple] = list(zip(palabras, pesos))
        # bigramas de palabras para capturar contexto (frases de 2 palabras)
        if len(palabras) > 1:
            for i in range(len(palabras) - 1):
                a, b = palabras[i], palabras[i + 1]
                if a in _STOP_ES or b in _STOP_ES:
                    continue
                tokens.append((f"{a} {b}", 1.0))
        # trigramas de caracteres para robustez léxica (ligero)
        ngrams: set[str] = set()
        for t in palabras:
            if t in _STOP_ES or len(t) < 5:
                continue
            for i in range(len(t) - 2):
                ngrams.add(t[i:i + 3])
        tokens += [(n, 0.7) for n in ngrams][:256]

        for token, peso in tokens:
            idx = self._bucket(token)
            vec[idx] += peso
            vec[(idx + 1) % self.dimension] += peso * 0.25  # suavizado
            # Bucket de la familia léxica (sinónimos del motor clásico)
            if len(token) > 0 and token not in _STOP_ES:
                familia = _FAMILIA.get(token)
                if familia and familia != token:
                    fidx = self._bucket(familia)
                    vec[fidx] += peso * 0.7
                    vec[(fidx + 1) % self.dimension] += peso * 0.18
        # normalización L2
        norma = sum(v * v for v in vec) ** 0.5
        if norma > 0:
            vec = [v / norma for v in vec]
        return vec


# ── Sentence Transformers ─────────────────────────────────────────────────── #


class SentenceTransformerEmbedder(Embedder):
    proveedor = "sentence_transformers"

    def __init__(self, modelo="paraphrase-multilingual-MiniLM-L12-v2"):
        self.modelo = modelo
        try:
            from sentence_transformers import SentenceTransformer  # type: ignore
            self._modelo_st = SentenceTransformer(modelo)
            self.dimension = self._modelo_st.get_sentence_embedding_dimension()
            self.disponible = True
        except Exception:
            self._modelo_st = None
            self.disponible = False

    def embed(self, texto: str) -> list:
        if not self._modelo_st:
            raise RuntimeError("sentence-transformers no disponible")
        vec = self._modelo_st.encode([texto], normalize_embeddings=True)[0]
        return [float(v) for v in vec]


# ── Ollama (local) ────────────────────────────────────────────────────────── #


class OllamaEmbedder(Embedder):
    proveedor = "ollama"

    def __init__(self, modelo, url_api):
        self.modelo = modelo
        self.url_api = (url_api or "http://localhost:11434").rstrip("/")
        self.disponible = True  # se valida en cada llamada

    def embed(self, texto: str) -> list:
        import requests

        resp = requests.post(
            f"{self.url_api}/api/embeddings",
            json={"model": self.modelo, "prompt": texto[:3000]},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        vec = data.get("embedding") or data.get("data", [{}])[0].get("embedding")
        if not vec:
            raise RuntimeError("respuesta de embeddings inválida")
        return [float(v) for v in vec]


# ── OpenAI / compatible (LM Studio) ───────────────────────────────────────── #


class OpenAIEmbedder(Embedder):
    proveedor = "openai"

    def __init__(self, modelo, url_api, api_key):
        self.modelo = modelo
        self.url_api = (url_api or "https://api.openai.com/v1").rstrip("/")
        self.api_key = api_key
        self.disponible = True

    def embed(self, texto: str) -> list:
        import requests

        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        resp = requests.post(
            f"{self.url_api}/embeddings",
            json={"model": self.modelo, "input": texto[:3000]},
            headers=headers,
            timeout=15,
        )
        resp.raise_for_status()
        vec = resp.json()["data"][0]["embedding"]
        return [float(v) for v in vec]


# ── Factory ───────────────────────────────────────────────────────────────── #

def _crear_embedder(proveedor: str, modelo: str, cfg) -> Embedder:
    if proveedor == "sentence_transformers":
        return SentenceTransformerEmbedder(modelo)
    if proveedor == "ollama":
        return OllamaEmbedder(modelo, cfg.url_api)
    if proveedor == "openai":
        return OpenAIEmbedder(modelo, cfg.url_api, cfg.get_api_key())
    return HashEmbedder()  # proveedor 'hash' (o desconocido) -> local v2


def obtener_embedder(cfg) -> Embedder:
    """Devuelve el embedder configurado (con caché) o el fallback hash."""
    clave = (cfg.proveedor_embeddings, cfg.modelo_embeddings)
    emb = _EMBEDDERS.get(clave)
    if emb is None:
        emb = _crear_embedder(cfg.proveedor_embeddings, cfg.modelo_embeddings, cfg)
        _EMBEDDERS[clave] = emb
    if not getattr(emb, "disponible", True):
        # Backend declarado pero no disponible: degradar a hash local.
        return HashEmbedder(modelo="hash-fallback")
    return emb


def embed_seguro(embedder: Embedder, texto: str) -> list:
    """
    Llama a `embed` y si falla (servidor caído / paquete ausente) degrada
    al HashEmbedder para que la consulta nunca rompa la búsqueda.
    """
    try:
        return embedder.embed(texto)
    except Exception as exc:
        logger.warning("Embeddings %s fallaron (%s); usando hash local", embedder.proveedor, exc)
        return HashEmbedder().embed(texto)


def disponibilidad(cfg) -> dict:
    """Resumen de disponibilidad para mostrar en el panel."""
    emb = obtener_embedder(cfg)
    return {
        "proveedor": cfg.proveedor_embeddings,
        "modelo": getattr(emb, "modelo", "?"),
        "dimension": cfg.modelo_embeddings and getattr(emb, "dimension", 0) or emb.dimension,
        "degradado": not getattr(emb, "disponible", True),
    }