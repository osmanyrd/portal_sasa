from django.core.cache import cache

from apps.mapa.models import ConfiguracionMapa, Dependencia, Provincia


def invalidar_cache_mapa(sender, **kwargs):
    """Invalida el cache del mapa cuando cambian las tablas del dominio."""
    if sender in (Provincia, Dependencia, ConfiguracionMapa):
        cache.delete("mapa_datos_json")
        cache.delete("mapa_provincias_json")