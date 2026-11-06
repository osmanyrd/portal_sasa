"""Campos de modelo específicos del módulo de mapa."""
from django.db import models

from .widgets import MapPointWidget


class CoordenadaField(models.DecimalField):
    """DecimalField de coordenadas geográficas.

    - Precisión suficiente para Google Maps (8 decimales ≈ 1 cm).
    - En el admin de Wagtail usa automáticamente el widget MapPointWidget
      (campo de texto + selector Leaflet), manteniendo la validación de
      DecimalField intacta en formularios y APIs.
    """

    def formfield(self, **kwargs):
        field = super().formfield(**kwargs)
        field.widget = MapPointWidget(
            attrs={
                "inputmode": "decimal",
                "autocomplete": "off",
                "placeholder": "lat, lng  (ej. 23.137, -82.354)",
                "style": "font-feature-settings: 'tnum';",
            }
        )
        return field