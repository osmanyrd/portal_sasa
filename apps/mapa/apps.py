from django.apps import AppConfig


class MapaConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.mapa"
    verbose_name = "Mapa de Dependencias"

    def ready(self):
        from django.db.models.signals import post_save

        from apps.mapa import signals

        post_save.connect(
            signals.invalidar_cache_mapa,
            dispatch_uid="mapa_invalidar_cache",
        )