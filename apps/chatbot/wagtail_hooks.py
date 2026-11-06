"""
Chatbot RAG — Panel de administración.

Registra en el menú "Chatbot IA" de Wagtail:

  - Configuración del chatbot (ajustes del sitio, keys cifradas).
  - Documentos de conocimiento (snippets, con ingesta desde el panel).
  - Fragmentos de documento.
  - Conversaciones de chat y mensajes.
  - Leads de escalado a humano.
  - Registro legacy (buscador clásico).
  - Vista de dashboard / estadísticas + exportación CSV.
"""

from django.urls import path
from wagtail import hooks
from wagtail.snippets.views.snippets import SnippetViewSet

from apps.chatbot.models import (
    ConversacionChat,
    DocumentoConocimiento,
    FragmentoDocumento,
    LeadChatbot,
    MensajeChat,
    RegistroConversacion,
)
from apps.chatbot import views_admin


class DocumentoConocimientoViewSet(SnippetViewSet):
    model = DocumentoConocimiento
    icon = "doc-full"
    menu_label = "Documentos de conocimiento"
    menu_name = "chatbot_documentos"
    add_to_admin_menu = True
    list_display = (
        "titulo", "tipo", "categoria", "contenido_visible",
        "fragmentos_count", "activo", "fecha_ingesta",
    )
    list_filter = ("tipo", "categoria", "activo")
    search_fields = ("titulo", "contenido", "contenido_texto", "fuente_titulo")
    ordering = ["-creado"]

    def fragmentos_count(self, obj):
        return obj.fragmentos.count()

    fragmentos_count.short_description = "Fragmentos"


class FragmentoDocumentoViewSet(SnippetViewSet):
    model = FragmentoDocumento
    icon = "pilcrow"
    menu_label = "Fragmentos (chunks)"
    menu_name = "chatbot_fragmentos"
    add_to_admin_menu = True
    list_display = ("documento", "orden", "tokens", "modelo", "dimension", "creado")
    list_filter = ("modelo", "documento__categoria")
    search_fields = ("contenido", "documento__titulo")
    ordering = ["-creado"]
    form_fields_exclude = ("embedding_texto",)


class ConversacionChatViewSet(SnippetViewSet):
    model = ConversacionChat
    icon = "comment"
    menu_label = "Conversaciones"
    menu_name = "chatbot_conversaciones"
    add_to_admin_menu = True
    list_display = (
        "__str__", "idioma", "cantidad_mensajes", "ultimo_mensaje",
        "calificacion", "entrenamiento", "iniciada_en",
    )
    list_filter = ("idioma", "entrenamiento", "calificacion", "iniciada_en")
    search_fields = ("session_key", "usuario__username")
    ordering = ["-iniciada_en"]
    form_fields_exclude = ("session_key",)


class MensajeChatViewSet(SnippetViewSet):
    model = MensajeChat
    icon = "comment"
    menu_label = "Mensajes"
    menu_name = "chatbot_mensajes"
    add_to_admin_menu = True
    list_display = ("conversacion", "rol", "tokens_usados", "calificacion", "timestamp")
    list_filter = ("rol", "calificacion")
    search_fields = ("contenido",)
    ordering = ["-timestamp"]


class LeadChatbotViewSet(SnippetViewSet):
    model = LeadChatbot
    icon = "group"
    menu_label = "Leads (escalados)"
    menu_name = "chatbot_leads"
    add_to_admin_menu = True
    list_display = ("__str__", "motivo", "atendido", "creado")
    list_filter = ("atendido", "creado")
    search_fields = ("nombre", "telefono", "motivo")
    ordering = ["-creado"]


class RegistroConversacionViewSet(SnippetViewSet):
    """Vista legacy (motor clásico) en solo lectura."""
    model = RegistroConversacion
    icon = "comment"
    menu_label = "Registros (clásico)"
    menu_name = "chatbot_registros"
    add_to_admin_menu = True
    list_display = (
        "pregunta_corta", "puntuacion_similitud", "respondido",
        "session_key", "feedback", "creado",
    )
    list_filter = ("respondido", "feedback", "creado")
    search_fields = ("pregunta", "respuesta", "session_key")
    ordering = ["-creado"]
    form_fields_exclude = ("pregunta", "respuesta", "documentos_utilizados")


@hooks.register("register_admin_urls")
def registrar_urls_admin():
    return [
        path("chatbot/dashboard/", views_admin.dashboard, name="chatbot_dashboard"),
        path("chatbot/exportar/", views_admin.exportar_csv, name="chatbot_exportar"),
        path("chatbot/reingestar/", views_admin.reingestar, name="chatbot_reingestar"),
    ]


@hooks.register("register_admin_menu_item")
def menu_chatbot():
    from wagtail.admin.menu import MenuItem

    return MenuItem(
        "Chatbot IA",
        "/cms/chatbot/dashboard/",
        icon_name="snippet",
        order=800,
    )