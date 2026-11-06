"""
Chatbot RAG — Modelos.

Incluye:

- DocumentoConocimiento : fuente de conocimiento (archivo, URL o texto manual)
                           que se puede ingestar (chunking + embeddings).
- FragmentoDocumento    : fragmentos (chunks) de un documento con su vector.
- ConversacionChat      : sesión de conversación de un visitante.
- MensajeChat           : turno (usuario / bot / sistema) dentro de una sesión.
- LeadChatbot           : solicitud de contacto/escalado a un humano.
- RespuestaCache        : cache de preguntas idénticas (1 h).
- ConfiguracionChatbot  : ajustes globales (ajustes de sitio Wagtail).

El módulo funciona SIN dependencias externas obligatorias:
  - pypdf / pdfplumber / python-docx  → mejores extracciones (opcionales).
  - sentence-transformers / ollama     → embeddings y LLM (opcionales).
  - Si faltan, se usan fallbacks locales deterministas.
"""
import uuid

from django.conf import settings
from django.db import models
from wagtail.admin.panels import FieldPanel
from wagtail.contrib.settings.models import BaseSiteSetting, register_setting

from apps.chatbot.constantes import (
    CARACTERES_POR_TOKEN,
    LIMITE_FRAGMENTOS,
    MAX_CARACTERES_PREGUNTA,
    MAX_MENSAJES_SESION,
    MAX_TOKENS_DEFECTO,
    MODELO_EMBEDDINGS_DEFECTO,
    PROVEEDOR_EMBEDDINGS_DEFECTO,
    PROVEEDOR_LLM_DEFECTO,
    TEMPERATURA_DEFECTO,
    UMBRAL_SIMILITUD,
)

# --------------------------------------------------------------------------- #
# DOCUMENTO DE CONOCIMIENTO (fuente)
# --------------------------------------------------------------------------- #
TIPOS_DOCUMENTO = [
    ("pdf", "PDF"),
    ("docx", "Word (DOCX)"),
    ("txt", "Texto (TXT)"),
    ("md", "Markdown (MD)"),
    ("url", "URL / página web"),
    ("manual", "Texto manual"),
]

CATEGORIAS_DOCUMENTO = [
    ("general", "General"),
    ("servicios", "Servicios"),
    ("productos", "Productos"),
    ("politicas", "Políticas"),
    ("faq", "Preguntas frecuentes"),
]


class DocumentoConocimiento(models.Model):
    """
    Documento fuente de conocimiento para el chatbot RAG.

    Puede ser un archivo subido (PDF/DOCX/TXT/MD), una URL a scrapear o
    texto pegado manualmente. Al guardarse se calcula su hash y si el
    contenido cambió se re-ingesta (se regeneran fragmentos y vectores).
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    titulo = models.CharField(max_length=255, help_text="Título descriptivo del documento.")
    tipo = models.CharField(max_length=10, choices=TIPOS_DOCUMENTO, default="manual")
    archivo = models.FileField(
        upload_to="chatbot/documentos/",
        blank=True,
        null=True,
        help_text="Archivo PDF, DOCX, TXT o MD (opcional).",
    )
    url_fuente = models.URLField(
        blank=True,
        default="",
        help_text="URL web para extraer contenido (tipo 'url').",
    )
    contenido_texto = models.TextField(
        blank=True,
        default="",
        help_text="Contenido pegado manualmente (tipo 'manual').",
    )
    # -- Compatibilidad con el buscador clásico (sin embeddings) ------------
    contenido = models.TextField(
        blank=True,
        default="",
        help_text="Texto plano extraído/normalizado del documento (campo de búsqueda clásica).",
    )
    fuente_url = models.CharField(
        max_length=500,
        blank=True,
        default="",
        help_text="URL relativa o de referencia de la fuente (ej: /servicios/).",
    )
    fuente_titulo = models.CharField(
        max_length=255,
        blank=True,
        default="",
        help_text="Título de la fuente original.",
    )
    categoria = models.CharField(
        max_length=50,
        choices=CATEGORIAS_DOCUMENTO,
        default="general",
        db_index=True,
        help_text="Categoría para búsquedas dirigidas.",
    )
    activo = models.BooleanField(default=True, db_index=True)
    hash_contenido = models.CharField(
        max_length=64,
        blank=True,
        default="",
        help_text="Hash del contenido extraído (para detectar cambios y re-ingestar).",
    )
    fecha_ingesta = models.DateTimeField(null=True, blank=True)
    ultima_actualizacion = models.DateTimeField(auto_now=True)
    creado = models.DateTimeField(auto_now_add=True)

    panels = [
        FieldPanel("titulo"),
        FieldPanel("tipo"),
        FieldPanel("archivo"),
        FieldPanel("url_fuente"),
        FieldPanel("contenido_texto"),
        FieldPanel("fuente_url"),
        FieldPanel("fuente_titulo"),
        FieldPanel("categoria"),
        FieldPanel("activo"),
    ]

    class Meta:
        verbose_name = "Documento de conocimiento (RAG)"
        verbose_name_plural = "Documentos de conocimiento (RAG)"
        ordering = ["-creado"]

    def __str__(self):
        return self.titulo

    def contenido_visible(self):
        """Representación corta del contenido para el panel."""
        return (self.contenido_texto or self.contenido or "")[:180] + (
            "..." if len(self.contenido or self.contenido_texto or "") > 180 else ""
        )

    contenido_visible.short_description = "Contenido"

    def save(self, *args, **kwargs):
        """Envía a ingesta si cambió el contenido y está activo."""
        from apps.chatbot.ingesta import procesar_documento  # import diferido

        super().save(*args, **kwargs)
        if self.activo:
            try:
                procesar_documento(self)
            except Exception:  # pragma: no cover - la ingesta nunca debe romper el admin
                import logging

                logging.getLogger(__name__).exception("Error ingiriendo documento %s", self.id)


# --------------------------------------------------------------------------- #
# FRAGMENTO (chunk + embedding)
# --------------------------------------------------------------------------- #
class FragmentoDocumento(models.Model):
    """
    Chunk de un documento con su vector (embedding).

    El embedding se guarda serializado (JSON) para funcionar en SQLite;
    si se usa PostgreSQL con pgvector, se puede migrar a una columna vector
    ejecutando el helper `apps.chatbot.vectorstore.migrar_pgvector()`.
    """

    documento = models.ForeignKey(
        DocumentoConocimiento,
        on_delete=models.CASCADE,
        related_name="fragmentos",
    )
    contenido = models.TextField()
    orden = models.PositiveIntegerField(default=0, db_index=True)
    tokens = models.IntegerField(default=0)
    dimension = models.IntegerField(default=0)
    modelo = models.CharField(max_length=128, blank=True, default="")
    embedding_texto = models.TextField(blank=True, default="")  # JSON list[float]
    creado = models.DateTimeField(auto_now_add=True)

    panels = [
        FieldPanel("documento"),
        FieldPanel("orden"),
        FieldPanel("contenido"),
        FieldPanel("tokens"),
        FieldPanel("modelo"),
    ]

    class Meta:
        verbose_name = "Fragmento de documento"
        verbose_name_plural = "Fragmentos de documento"
        ordering = ["documento", "orden"]
        unique_together = ("documento", "orden")

    def __str__(self):
        return f"{self.documento.titulo} #{self.orden}"

    def tokens_reales(self):
        return self.tokens or max(1, round(len(self.contenido) / CARACTERES_POR_TOKEN))

    def guardar_embedding(self, vector):
        """Serializa el vector y lo persiste."""
        import json

        self.dimension = len(vector)
        self.embedding_texto = json.dumps([round(float(v), 6) for v in vector])

    def obtener_embedding(self):
        """Devuelve el vector deserializado (o [] si no hay)."""
        import json

        if not self.embedding_texto:
            return []
        try:
            return json.loads(self.embedding_texto)
        except (ValueError, TypeError):
            return []


# --------------------------------------------------------------------------- #
# CONVERSACIONES
# --------------------------------------------------------------------------- #
ROLES_MENSAJE = [
    ("usuario", "Usuario"),
    ("bot", "Asistente"),
    ("sistema", "Sistema"),
]


class ConversacionChat(models.Model):
    """Sesión de conversación de un visitante."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session_key = models.CharField(max_length=64, db_index=True)
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="conversaciones_chat",
    )
    idioma = models.CharField(max_length=8, default="es", blank=True)
    iniciada_en = models.DateTimeField(auto_now_add=True, db_index=True)
    cerrada_en = models.DateTimeField(null=True, blank=True)
    calificacion = models.PositiveSmallIntegerField(
        null=True, blank=True, help_text="Calificación 1-5 (opcional)."
    )
    entrenamiento = models.BooleanField(
        default=False,
        help_text="Marca la conversación para revisión/entrenamiento del bot.",
    )
    sesion_cerrada = models.BooleanField(default=False)

    panels = [
        FieldPanel("session_key"),
        FieldPanel("usuario"),
        FieldPanel("idioma"),
        FieldPanel("calificacion"),
        FieldPanel("entrenamiento"),
        FieldPanel("iniciada_en"),
        FieldPanel("cerrada_en"),
    ]

    class Meta:
        verbose_name = "Conversación de chat"
        verbose_name_plural = "Conversaciones de chat"
        ordering = ["-iniciada_en"]

    def __str__(self):
        usuario = self.usuario_id or self.session_key or "anónimo"
        return f"{usuario} — {self.iniciada_en:%d/%m/%Y %H:%M}"

    def cantidad_mensajes(self):
        return self.mensajes.count()

    def ultimo_mensaje(self):
        msg = self.mensajes.order_by("-timestamp").first()
        return msg.contenido[:120] if msg else ""


class MensajeChat(models.Model):
    """Tunrno de la conversación con trazabilidad de fragmentos usados."""

    conversacion = models.ForeignKey(
        ConversacionChat,
        on_delete=models.CASCADE,
        related_name="mensajes",
    )
    rol = models.CharField(max_length=8, choices=ROLES_MENSAJE, default="usuario")
    contenido = models.TextField()
    fragmentos_usados = models.JSONField(
        blank=True, default=list,
        help_text="IDs/citas de los fragmentos usados para generar la respuesta.",
    )
    tokens_usados = models.IntegerField(default=0)
    calificacion = models.PositiveSmallIntegerField(
        null=True, blank=True, help_text="Calificación 1-5 o 1/0 (feedback)."
    )
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)

    panels = [
        FieldPanel("conversacion"),
        FieldPanel("rol"),
        FieldPanel("contenido"),
        FieldPanel("fragmentos_usados"),
        FieldPanel("tokens_usados"),
    ]

    class Meta:
        verbose_name = "Mensaje de chat"
        verbose_name_plural = "Mensajes de chat"
        ordering = ["timestamp"]

    def __str__(self):
        return f"[{self.get_rol_display()}] {self.contenido[:80]}"


# --------------------------------------------------------------------------- #
# ESCALADO A HUMANO
# --------------------------------------------------------------------------- #
class LeadChatbot(models.Model):
    """Solicitud de contacto cuando el bot escala a un humano."""

    conversacion = models.ForeignKey(
        ConversacionChat,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="leads",
    )
    nombre = models.CharField(max_length=120, blank=True, default="")
    telefono = models.CharField(max_length=40, blank=True, default="")
    motivo = models.TextField(blank=True, default="")
    atendido = models.BooleanField(default=False)
    creado = models.DateTimeField(auto_now_add=True)

    panels = [
        FieldPanel("conversacion"),
        FieldPanel("nombre"),
        FieldPanel("telefono"),
        FieldPanel("motivo"),
        FieldPanel("atendido"),
    ]

    class Meta:
        verbose_name = "Lead de contacto (escalado)"
        verbose_name_plural = "Leads de contacto (escalado)"
        ordering = ["-creado"]

    def __str__(self):
        return f"{self.nombre or 'Anónimo'} — {self.telefono or 'sin teléfono'}"


# --------------------------------------------------------------------------- #
# CACHE DE RESPUESTAS
# --------------------------------------------------------------------------- #
class RespuestaCache(models.Model):
    """Cache de preguntas idénticas (1 h) para no repetir llamadas al LLM."""

    hash_pregunta = models.CharField(max_length=64, unique=True, db_index=True)
    respuesta = models.TextField()
    sugerencias = models.JSONField(default=list, blank=True)
    fuentes = models.JSONField(default=list, blank=True)
    puntuacion = models.FloatField(default=0.0)
    creado = models.DateTimeField(auto_now_add=True)
    expira_en = models.DateTimeField(db_index=True)

    class Meta:
        verbose_name = "Caché de respuesta"
        verbose_name_plural = "Caché de respuestas"
        ordering = ["-creado"]


# --------------------------------------------------------------------------- #
# REGISTRO LEGACY (compatible con el buscador clásico)
# --------------------------------------------------------------------------- #
class RegistroConversacion(models.Model):
    """
    Registro de una interacción del chatbot (motor clásico).

    Se mantiene por compatibilidad: el motor RAG persiste en
    ConversacionChat / MensajeChat, y también denormaliza aquí para
    aprovechar el listado existente del panel.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    pregunta = models.TextField(help_text="Pregunta tal como la escribió el usuario.")
    respuesta = models.TextField(help_text="Respuesta que dio el bot.")
    documentos_utilizados = models.ManyToManyField(
        DocumentoConocimiento,
        blank=True,
        related_name="conversaciones",
        help_text="Documentos que se usaron para generar la respuesta.",
    )
    puntuacion_similitud = models.FloatField(
        default=0.0, help_text="Puntuación máxima de similitud (0-1)."
    )
    respondido = models.BooleanField(
        default=True, help_text="False si el bot no encontró respuesta."
    )
    feedback = models.CharField(
        max_length=8,
        choices=[("up", "Útil"), ("down", "No útil")],
        blank=True,
        default="",
    )
    session_key = models.CharField(max_length=64, blank=True, db_index=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    creado = models.DateTimeField(auto_now_add=True)

    panels = [
        FieldPanel("pregunta"),
        FieldPanel("respuesta"),
        FieldPanel("documentos_utilizados"),
        FieldPanel("puntuacion_similitud"),
        FieldPanel("respondido"),
        FieldPanel("feedback"),
        FieldPanel("session_key"),
    ]

    class Meta:
        verbose_name = "Registro de conversación (clásico)"
        verbose_name_plural = "Registros de conversación (clásico)"
        ordering = ["-creado"]

    def __str__(self):
        estado = "✓" if self.respondido else "✗"
        return f"{estado} {self.pregunta[:60]}..."

    def pregunta_corta(self):
        return self.pregunta[:80] + ("..." if len(self.pregunta) > 80 else "")

    pregunta_corta.short_description = "Pregunta"


# --------------------------------------------------------------------------- #
# CONFIGURACIÓN GLOBAL (ajustes de sitio Wagtail)
# --------------------------------------------------------------------------- #
@register_setting(icon="cog")
class ConfiguracionChatbot(BaseSiteSetting):
    """
    Ajustes del asistente RAG.

    Soporta:
      - Backends de embeddings: hash | sentence-transformers | ollama | openai.
      - Backends LLM: ollama | lmstudio | openai | anthropic | ninguno (local).
    """

    nombre_asistente = models.CharField(max_length=60, default="Asistente Virtual")
    mensaje_bienvenida = models.TextField(
        blank=True,
        default="¡Hola! Soy el asistente de Servicios Automotores S.A. "
                "Puedo ayudarte con nuestros servicios, productos, ubicaciones "
                "y políticas. ¿Qué necesitas saber?",
    )
    mensaje_no_encontrado = models.TextField(
        blank=True,
        default="No tengo esa información disponible. ¿Deseas que un asesor humano te contacte?",
    )
    mensaje_error = models.TextField(
        blank=True,
        default="Lo siento, hubo un error al procesar tu consulta. Intentá de nuevo.",
    )
    mensaje_bloqueado = models.TextField(
        blank=True,
        default="No puedo responder a esa consulta. Si necesitas información "
                "sobre nuestros servicios, estoy aquí para ayudarte.",
    )
    mensaje_escalado = models.TextField(
        blank=True,
        default="Un asesor te contactará en la brevedad. Gracias por escribirnos.",
    )

    # -- Embeddings ------------------------------------------------------
    proveedor_embeddings = models.CharField(
        max_length=24,
        choices=[
            ("hash", "Local (Hash, sin dependencias)"),
            ("sentence_transformers", "Sentence Transformers (local)"),
            ("ollama", "Ollama (local)"),
            ("openai", "OpenAI API"),
        ],
        default=PROVEEDOR_EMBEDDINGS_DEFECTO,
    )
    modelo_embeddings = models.CharField(
        max_length=128, default=MODELO_EMBEDDINGS_DEFECTO,
        help_text="Ej: paraphrase-multilingual-MiniLM-L12-v2, nomic-embed-text, text-embedding-3-small.",
    )

    # -- LLM -------------------------------------------------------------
    proveedor_llm = models.CharField(
        max_length=24,
        choices=[
            ("ninguno", "Ninguno (respuesta local de fragmentos)"),
            ("ollama", "Ollama"),
            ("lmstudio", "LM Studio"),
            ("openai", "OpenAI"),
            ("anthropic", "Anthropic"),
        ],
        default=PROVEEDOR_LLM_DEFECTO,
    )
    modelo_llm = models.CharField(
        max_length=128, default="llama3.2",
        help_text="Ej: llama3.2, qwen2.5, mistral, gpt-4o-mini, claude-3-5-haiku-latest.",
    )
    url_api = models.URLField(
        blank=True, default="http://localhost:11434",
        help_text="URL base para Ollama / LM Studio, o API correspondiente.",
    )
    api_key = models.CharField(
        max_length=512, blank=True, default="",
        help_text="Clave API (se guarda cifrada con la SECRET_KEY del sitio).",
    )
    temperatura = models.FloatField(default=TEMPERATURA_DEFECTO)
    max_tokens = models.IntegerField(default=MAX_TOKENS_DEFECTO)
    streaming = models.BooleanField(
        default=False, help_text="Usa streaming de respuesta si el backend lo soporta."
    )

    # -- Búsqueda --------------------------------------------------------
    umbral_similitud = models.FloatField(default=UMBRAL_SIMILITUD)
    limite_fragmentos = models.IntegerField(default=LIMITE_FRAGMENTOS)

    # -- Prompt del sistema (editable) ------------------------------------
    prompt_sistema = models.TextField(
        blank=True,
        help_text="Si se deja vacío se usa el prompt institucional por defecto.",
    )

    # -- Turnos/seguridad -------------------------------------------------
    max_mensajes_sesion = models.IntegerField(default=MAX_MENSAJES_SESION)
    max_caracteres_pregunta = models.IntegerField(default=MAX_CARACTERES_PREGUNTA)
    moderacion_activa = models.BooleanField(default=True)
    cache_respuestas = models.BooleanField(default=True)
    aviso_privacidad = models.TextField(
        blank=True,
        default="Tus conversaciones se guardan para mejorar el servicio. "
                "No ingreses datos sensibles o bancarios.",
    )

    panels = [
        FieldPanel("nombre_asistente"),
        FieldPanel("mensaje_bienvenida"),
        FieldPanel("mensaje_no_encontrado"),
        FieldPanel("mensaje_error"),
        FieldPanel("mensaje_bloqueado"),
        FieldPanel("mensaje_escalado"),
        FieldPanel("proveedor_embeddings"),
        FieldPanel("modelo_embeddings"),
        FieldPanel("proveedor_llm"),
        FieldPanel("modelo_llm"),
        FieldPanel("url_api"),
        FieldPanel("api_key"),
        FieldPanel("temperatura"),
        FieldPanel("max_tokens"),
        FieldPanel("streaming"),
        FieldPanel("umbral_similitud"),
        FieldPanel("limite_fragmentos"),
        FieldPanel("prompt_sistema"),
        FieldPanel("max_mensajes_sesion"),
        FieldPanel("max_caracteres_pregunta"),
        FieldPanel("moderacion_activa"),
        FieldPanel("cache_respuestas"),
        FieldPanel("aviso_privacidad"),
    ]

    class Meta:
        verbose_name = "Configuración del chatbot IA"

    def __str__(self):
        return f"Configuración Chatbot — {self.proveedor_llm} / {self.llm_modelo_efectivo()}"

    # ------------------------------------------------------------------ #
    def llm_modelo_efectivo(self):
        """Modelo LLM por defecto según proveedor si no se especificó otro."""
        if self.modelo_llm and self.modelo_llm != "llama3.2":
            return self.modelo_llm
        defaults = {
            "ollama": "llama3.2",
            "lmstudio": "local-model",
            "openai": "gpt-4o-mini",
            "anthropic": "claude-3-5-haiku-latest",
        }
        return defaults.get(self.proveedor_llm, self.modelo_llm)

    def get_api_key(self):
        """Devuelve la API key descifrada (o '')."""
        from django.core import signing

        if not self.api_key:
            return ""
        try:
            return signing.loads(self.api_key)
        except Exception:
            return ""

    def set_api_key(self, valor):
        """Cifra y guarda la API key usando la SECRET_KEY."""
        from django.core import signing

        self.api_key = signing.dumps(valor or "") if valor else ""

    @staticmethod
    def obtener(request=None):
        """Devuelve el setting del sitio (creándolo si no existe)."""
        from wagtail.models import Site

        if request is not None:
            try:
                sitio = Site.find_for_request(request)
                if sitio:
                    cfg = ConfiguracionChatbot.for_site(sitio)
                    if cfg is None:
                        cfg, _ = ConfiguracionChatbot.objects.get_or_create(site=sitio)
                    return cfg
            except Exception:
                pass
        sitio = Site.objects.filter(is_default_site=True).first() or Site.objects.first()
        if sitio is None:
            raise RuntimeError("No hay sitios Wagtail configurados para el chatbot.")
        cfg = ConfiguracionChatbot.for_site(sitio)
        if cfg is None:
            cfg, _ = ConfiguracionChatbot.objects.get_or_create(site=sitio)
        return cfg