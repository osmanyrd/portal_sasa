"""Validadores reutilizables para coordenadas geográficas.

Centralizan las reglas de rango para que el modelo, los formularios y
cualquier API futura apliquen las mismas reglas.
"""
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _


def validar_rango_latitud(valor):
    """Latitud válida: entre -90 y 90 grados.
    Acepta None (coordenada no cargada todavía).
    """
    if valor is None:
        return
    if not -90 <= valor <= 90:
        raise ValidationError(_("La latitud debe estar entre -90 y 90."))


def validar_rango_longitud(valor):
    """Longitud válida: entre -180 y 180 grados.
    Acepta None (coordenada no cargada todavía).
    """
    if valor is None:
        return
    if not -180 <= valor <= 180:
        raise ValidationError(_("La longitud debe estar entre -180 y 180."))


def formatear_coordenada(valor):
    """Devuelve la coordenada con 8 decimales siempre (estándar del sistema).

    Usado para normalizar la salida en APIs, plantillas y enlaces a Google Maps,
    evitando notación científica o truncamiento del valor almacenado.
    """
    if valor is None:
        return ""
    return "{:.8f}".format(valor)