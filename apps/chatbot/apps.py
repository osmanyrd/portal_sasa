from django.apps import AppConfig
from django.db.models.signals import post_delete, post_save


class ChatbotConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.chatbot"
    verbose_name = "Chatbot IA"

    def ready(self):
        from apps.chatbot.models import DocumentoConocimiento, LeadChatbot

        def _invalidar_cache_documento(sender, instance, **kwargs):
            """Al cambiar un documento, refrescar índices en proceso."""
            from apps.chatbot import vectorstore

            vectorstore._INDICE_CACHE = None
            vectorstore._INDICE_CLAVE = None
            from apps.chatbot import clasico

            clasico._docs_cache = None
            clasico._docs_cache_key = None

        post_save.connect(_invalidar_cache_documento, sender=DocumentoConocimiento)
        post_delete.connect(_invalidar_cache_documento, sender=DocumentoConocimiento)