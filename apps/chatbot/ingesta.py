"""
Chatbot RAG — Ingesta de documentos.

Extracción de texto (PDF/DOCX/TXT/MD/URL/manual), limpieza, chunking con
solapamiento y persistencia de fragmentos + embeddings.

Dependencias opcionales (se degradan con gracia):
  - pdfplumber / pypdf  : PDF.
  - python-docx         : DOCX.
  - requests + bs4      : URLs.
  - sentence-transformers / ollama / openai: embeddings (si no, hash local).

Uso normal (desde el panel o por comando):
    from apps.chatbot.ingesta import procesar_documento
    procesar_documento(documento)
"""
from __future__ import annotations

import hashlib
import logging
import re

from django.utils import timezone

from apps.chatbot.constantes import (
    CARACTERES_POR_TOKEN,
    SOLAPAMIENTO_CHUNK,
    TAMANIO_CHUNK,
)

logger = logging.getLogger(__name__)

# IDs de documentos en proceso (evita recursión save() -> procesar_documento()).
_EN_PROCESO: set = set()

# ── Extracción ────────────────────────────────────────────────────────────── #


def _leer_archivo_bytes(doc) -> bytes:
    """Devuelve el contenido binario del archivo subido."""
    if not doc.archivo:
        return b""
    try:
        doc.archivo.open("rb")
        data = doc.archivo.read()
        doc.archivo.close()
        return data
    except Exception as exc:  # pragma: no cover
        logger.warning("No se pudo leer el archivo de %s: %s", doc.titulo, exc)
        return b""


def _decodificar(data: bytes) -> str:
    """Prueba varias codificaciones para decodificar bytes a texto."""
    for cod in ("utf-8", "utf-16", "latin-1", "cp1252"):
        try:
            return data.decode(cod)
        except (UnicodeDecodeError, ValueError):
            continue
    return data.decode("utf-8", errors="replace")


def _extraer_pdf(data: bytes) -> str:
    try:
        import pdfplumber  # type: ignore

        with pdfplumber.open_data(data) as pdf:
            return "\n".join((pag.extract_text() or "") for pag in pdf.pages)
    except ImportError:
        pass
    try:
        from pypdf import PdfReader  # type: ignore

        lector = PdfReader(data)
        return "\n".join((pag.extract_text() or "") for pag in lector.pages)
    except ImportError:
        return ""
    except Exception as exc:
        logger.warning("Error extrayendo PDF: %s", exc)
        return ""


def _extraer_docx(data: bytes) -> str:
    try:
        import io

        import docx  # type: ignore

        documento = docx.Document(io.BytesIO(data))
        partes = [p.text for p in documento.paragraphs]
        for tabla in documento.tables:
            for fila in tabla.rows:
                partes.append(" | ".join(celda.text for celda in fila.cells))
        return "\n".join(partes)
    except ImportError:
        return ""
    except Exception as exc:
        logger.warning("Error extrayendo DOCX: %s", exc)
        return ""


def _extraer_url(url: str) -> str:
    import requests
    from bs4 import BeautifulSoup

    try:
        resp = requests.get(url, timeout=15, headers={"User-Agent": "SASA-Chatbot/1.0"})
        resp.raise_for_status()
    except Exception as exc:
        logger.warning("Error obteniendo %s: %s", url, exc)
        return ""
    try:
        soup = BeautifulSoup(resp.text, "html.parser")
        for tag in soup(["script", "style", "noscript", "nav", "footer", "header"]):
            tag.decompose()
        titulo = (soup.title.string or "").strip() if soup.title else ""
        parrafos = [p.get_text(" ", strip=True) for p in soup.find_all("p")]
        cuerpo = "\n".join(p for p in parrafos if len(p) > 30)
        return f"{titulo}\n\n{cuerpo}" if titulo else cuerpo
    except Exception as exc:
        logger.warning("Error parseando %s: %s", url, exc)
        return ""


def extraer_texto(doc) -> str:
    """
    Extrae el texto plano de un DocumentoConocimiento según su tipo.
    Devuelve "" si no pudo extraer nada.
    """
    tipo = doc.tipo
    if tipo == "pdf":
        return _extraer_pdf(_leer_archivo_bytes(doc))
    if tipo == "docx":
        return _extraer_docx(_leer_archivo_bytes(doc))
    if tipo in ("txt", "md"):
        return _decodificar(_leer_archivo_bytes(doc))
    if tipo == "url":
        return _extraer_url(doc.url_fuente or "")
    if tipo == "manual":
        return doc.contenido_texto or doc.contenido or ""
    # Legacy: documentos creados por el indexador clásico
    return doc.contenido or doc.contenido_texto or ""


# ── Limpieza ──────────────────────────────────────────────────────────────── #

_PATRONES_RUIDO = [
    r"<[^>]+>",                          # HTML
    r"(?i)política de privacidad",
    r"(?i)términos y condiciones",
    r"(?i)todos los derechos reservados",
    r"(?i)ver más información",
    r"^\s*[\d.,]+\s*$",                  # solo números
    r"^\s*structvalue\s*$",              # artefactos Wagtail
    r"\s+",                              # espacios múltiples (al final del pipeline)
]


def limpiar_texto(texto: str) -> str:
    """Normaliza el texto: quita HTML, enlaces de pié, ruido y espacios extra."""
    texto = texto or ""
    for patron in _PATRONES_RUIDO[:-1]:
        texto = re.sub(patron, " ", texto)
    # Corregir espacios tras puntuación
    texto = re.sub(r"\s*([.,:;!?])\s*", r"\1 ", texto)
    texto = re.sub(r"[ \t]+", " ", texto)
    texto = "\n".join(linea.strip() for linea in texto.splitlines())
    texto = re.sub(r"\n{3,}", "\n\n", texto)
    return texto.strip()


def hash_de_texto(texto: str) -> str:
    """Sha256 del texto normalizado (para detectar cambios)."""
    return hashlib.sha256(limpiar_texto(texto).encode("utf-8")).hexdigest()


# ── Chunking ──────────────────────────────────────────────────────────────── #


def dividir_en_chunks(texto: str, tamano: int = TAMANIO_CHUNK,
                      solapamiento: int = SOLAPAMIENTO_CHUNK) -> list[str]:
    """
    Divide el texto en fragmentos de ~`tamano` caracteres (~tamano/4 tokens)
    con `solapamiento` caracteres. Respeta párrafos/sentencias cuando puede.
    """
    texto = limpiar_texto(texto)
    if not texto:
        return []
    if len(texto) <= tamano:
        return [texto]

    # Separar primera vez por párrafos
    parrafos = [p.strip() for p in re.split(r"\n{2,}", texto) if p.strip()]

    oraciones: list[str] = []
    for parrafo in parrafos:
        if len(parrafo) <= tamano:
            oraciones.append(parrafo)
        else:
            # Partition por oración si el párrafo es muy largo
            partes = re.split(r"(?<=[.!?])\s+", parrafo)
            oraciones.extend(p for p in partes if p.strip())

    if not oraciones:
        return [texto]

    chunks: list[str] = []
    actual = ""
    for oracion in oraciones:
        if len(actual) + len(oracion) + 1 <= tamano:
            actual = f"{actual} {oracion}".strip()
        else:
            if actual:
                chunks.append(actual)
                # Solapamiento: último ~solapamiento caracteres del chunk previo
                pie = actual[-solapamiento:] if len(actual) > solapamiento else ""
                actual = pie
            # Si la oración excede el tamaño, cortarla en trozos
            while len(oracion) > tamano:
                trozo = oracion[:tamano]
                chunks.append(trozo.rstrip())
                oracion = oracion[tamano - solapamiento:]
            actual = f"{actual} {oracion}".strip()

    if actual:
        chunks.append(actual)

    # Deduplicar chunks idénticos consecutivos
    resultado: list[str] = []
    for chunk in chunks:
        if resultado and chunk == resultado[-1]:
            continue
        if len(chunk.strip()) < 20:
            continue
        resultado.append(chunk.strip())
    return resultado


# ── Procesamiento completo de un documento ────────────────────────────────── #


def procesar_documento(doc, fuerza: bool = False) -> bool:
    """
    Extrae, limpia, divide y vectoriza un documento.
    Idempotente: si el hash no cambió (y no se fuerza), no re-ingesta.

    Devuelve True si se ingirió (o ya estaba al día), False si hubo error.
    """
    if doc.id in _EN_PROCESO:
        return True
    _EN_PROCESO.add(doc.id)
    try:
        from apps.chatbot.embeddings import obtener_embedder
        from apps.chatbot.models import ConfiguracionChatbot, FragmentoDocumento

        texto_crud = extraer_texto(doc)
        texto = limpiar_texto(texto_crud)
        if len(texto) < 20:
            doc.contenido = ""
            doc.hash_contenido = ""
            doc.fecha_ingesta = None
            doc.fragmentos.all().delete()
            doc.save(update_fields=["contenido", "hash_contenido", "fecha_ingesta"])
            logger.warning("Documento %s sin contenido util", doc.titulo)
            return False

        nuevo_hash = hash_de_texto(texto)
        ya_ingirio = doc.fragmentos.exists()
        if not fuerza and nuevo_hash == doc.hash_contenido and ya_ingirio:
            return True

        cfg = ConfiguracionChatbot.obtener()
        embedder = obtener_embedder(cfg)

        chunks = dividir_en_chunks(texto)
        if not chunks:
            return False

        # Reconstrucción atómica: borrar fragmentos viejos y recrear
        doc.fragmentos.all().delete()

        modelo, dim = embedder.modelo, embedder.dimension
        prefijo = f"{doc.titulo or doc.fuente_titulo or ''}\n"
        for i, chunk in enumerate(chunks):
            # El título se incluye en el *embedding* (aportan señales fuertes:
            # "Horario de atención", "Parqueo", "Teléfonos de contacto"...)
            vector = embedder.embed(f"{prefijo}{chunk}")
            import json

            frag = FragmentoDocumento(
                documento=doc,
                contenido=chunk,
                orden=i,
                tokens=max(1, round(len(chunk) / CARACTERES_POR_TOKEN)),
                dimension=len(vector),
                modelo=modelo,
                embedding_texto=json.dumps([round(float(v), 6) for v in vector or []]),
            )
            frag.save()
            del vector

        # Denormalización para el buscador clásico (sin embeddings)
        texto_clasico = " ".join(chunks[:3]) if chunks else texto
        doc.contenido = texto_clasico if len(texto_clasico) > 30 else texto[:800]
        doc.hash_contenido = nuevo_hash
        doc.fecha_ingesta = timezone.now()
        doc.save(update_fields=["contenido", "hash_contenido", "fecha_ingesta"])
        logger.info("Documento %s ingesta: %d fragmentos (%s)", doc.titulo, len(chunks), modelo)
        return True
    except Exception as exc:  # pragma: no cover
        logger.exception("Error procesando documento %s", getattr(doc, "titulo", "?"))
        return False
    finally:
        _EN_PROCESO.discard(doc.id)


def reingestar_todo(doc_ids=None) -> dict:
    """Ingesta masiva usada por el comando `ingestar_documentos` y el panel."""
    from apps.chatbot.models import DocumentoConocimiento

    qs = DocumentoConocimiento.objects.filter(activo=True)
    if doc_ids:
        qs = qs.filter(id__in=doc_ids)

    resultado = {"ok": 0, "sin_contenido": 0, "error": 0}
    for doc in qs:
        if procesar_documento(doc, fuerza=True):
            resultado["ok"] += 1
        else:
            resultado["sin_contenido"] += 1
    return resultado