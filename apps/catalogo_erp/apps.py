from django.apps import AppConfig


class CatalogoErpConfig(AppConfig):
    """Configuración de la app ``catalogo_erp``."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.catalogo_erp"
    verbose_name = "Catálogo ERP"

    def ready(self):
        # Conecta las señales que invalidan la caché de categorías al
        # guardar/eliminar una categoría desde el admin.
        from apps.catalogo_erp import signals  # noqa: F401