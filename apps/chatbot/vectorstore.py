"""
Chatbot RAG — Base vectorial y búsqueda por similitud coseno.

Implementación portable (SQLite + cualquier DB):
  - Los embeddings se guardan serializados en `FragmentoDocumento`.
  - `buscar_fragmentos()` calcula coseno en la capa de aplicación.

Opcional pgvector (PostgreSQL):
  - Si `config.vendor()` es postgres y `CHATBOT_VECTOR_DB=pgvector`,
    se usa una consulta SQL con el operador `<=>` de pgvector.
  - `migrar_pgvector()` crea la columna `embedding vector(...)` y el índice.
"""
from __future__ import annotations

import logging
import os

from django.conf import settings

logger = logging.getLogger(__name__)

# caché en proceso del índice de fragmentos
_INDICE_CACHE = None
_INDICE_CLAVE = None


def _coseno(a, b) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    suma = sum(x * y for x, y in zip(a, b))
    na = sum(x * x for x in a) ** 0.5
    nb = sum(y * y for y in b) ** 0.5
    if na == 0 or nb == 0:
        return 0.0
    return suma / (na * nb)


def vector_db_activo(cfg) -> bool:
    """¿Usamos pgvector? Solo si está habilitado por entorno y hay Postgres."""
    if os.environ.get("CHATBOT_VECTOR_DB", "").lower() != "pgvector":
        return False
    from django.db import connection

    return connection.vendor.startswith("postgres")


def _obtener_indice():
    """Devuelve cache [(fragmento, vector), ...] invalidado por cambios."""
    global _INDICE_CACHE, _INDICE_CLAVE
    from apps.chatbot.models import FragmentoDocumento

    ultimo = FragmentoDocumento.objects.order_by("-creado").first()
    clave = (FragmentoDocumento.objects.count(), ultimo.id if ultimo else None)
    if _INDICE_CACHE is None or clave != _INDICE_CLAVE:
        _INDICE_CACHE = []
        for frag in FragmentoDocumento.objects.prefetch_related("documento").all():
            vec = frag.obtener_embedding()
            if vec:
                _INDICE_CACHE.append((frag, vec))
        _INDICE_CLAVE = clave
    return _INDICE_CACHE


def _buscar_pgvector(pregunta_vec: list, cfg) -> list:
    """Búsqueda directa en pgvector (requiere migración previa)."""
    from django.db import connection

    qid = str(cfg.limite_fragmentos)
    with connection.cursor() as cur:
        cur.execute(
            """
            SELECT f.id, f.orden, f.contenido, f.documento_id,
                   1 - (f.embedding <=> %s::vector) AS sim,
                   d.titulo, d.fuente_titulo, d.fuente_url
            FROM chatbot_fragmentodocumento f
            JOIN chatbot_documentoconocimiento d ON d.id = f.documento_id
            WHERE d.activo = TRUE AND f.embedding IS NOT NULL
            ORDER BY f.embedding <=> %s::vector
            LIMIT %s
            """,
            [str(pregunta_vec), str(pregunta_vec), qid],
        )
        filas = cur.fetchall()
    from apps.chatbot.models import FragmentoDocumento

    resultados = []
    for fid, orden, contenido, doc_id, sim, titulo, fuente_titulo, fuente_url in filas:
        resultados.append({
            "fragmento_id": fid,
            "orden": orden,
            "contenido": contenido,
            "documento_id": doc_id,
            "puntuacion": round(float(sim or 0.0), 4),
            "titulo": titulo or fuente_titulo or "",
            "fuente": fuente_url or "",
        })
    return resultados


def buscar_fragmentos(pregunta: str, cfg, limite: int | None = None) -> list:
    """
    Recupera los fragmentos más similares a la pregunta.

    Devuelve lista de dicts:
        {fragmento_id, orden, contenido, documento_id, puntuacion, titulo, fuente}
    ordenada por similitud descendente.
    """
    from apps.chatbot.embeddings import embed_seguro, obtener_embedder

    limite = limite or getattr(cfg, "limite_fragmentos", 5)
    embedder = obtener_embedder(cfg)
    qvec = embed_seguro(embedder, pregunta)

    if vector_db_activo(cfg):
        try:
            return _buscar_pgvector(qvec, cfg)
        except Exception as exc:
            logger.warning("pgvector falló (%s); usando coseno en Python", exc)

    umbral = getattr(cfg, "umbral_similitud", 0.30)
    candidatos = []
    for frag, vec in _obtener_indice():
        sim = _coseno(qvec, vec)
        if sim >= umbral:
            candidatos.append((sim, frag))

    candidatos.sort(key=lambda x: x[0], reverse=True)
    seleccionados = candidatos[:limite]

    resultado = []
    for sim, frag in seleccionados:
        doc = frag.documento
        resultado.append({
            "fragmento_id": frag.id,
            "orden": frag.orden,
            "contenido": frag.contenido,
            "documento_id": doc_id if (doc_id := getattr(doc, "id", None)) else "",
            "puntuacion": round(sim, 4),
            "titulo": doc.titulo if doc else "",
            "fuente": (doc.fuente_url if doc else "") or "",
            "tokens": frag.tokens_reales(),
        })
    return resultado


def migrar_pgvector(dimension: int = 384) -> bool:
    """
    Habilita pgvector (requiere extensión instalada en PostgreSQL).

    Crea la columna `embedding vector(dimension)` y un índice ANN. Es una
    mejora opcional; sin ella el sistema usa búsqueda por coseno en Python.
    """
    from django.db import connection

    try:
        with connection.cursor() as cur:
            cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
            cur.execute(
                "ALTER TABLE chatbot_fragmentodocumento "
                "ADD COLUMN IF NOT EXISTS embedding vector(%s)" % int(dimension)
            )
            cur.execute(
                "CREATE INDEX IF NOT EXISTS frag_embedding_hnsw ON "
                "chatbot_fragmentodocumento USING hnsw (embedding vector_cosine_ops)"
            )
        return True
    except Exception as exc:  # pragma: no cover
        logger.warning("No se pudo habilitar pgvector: %s", exc)
        return False