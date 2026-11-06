from django.apps import AppConfig


class InformacionesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.informaciones"
    verbose_name = "Informaciones"

    def ready(self):
        from apps.informaciones import signals

        signals.connect()
