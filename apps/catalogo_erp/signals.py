"""Señales: invalida la caché de categorías al guardar o eliminar."""

from django.core.cache import cache
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from apps.catalogo_erp.models import CACHE_CATEGORIAS, CategoriaProductoERP


@receiver([post_save, post_delete], sender=CategoriaProductoERP)
def invalidar_categorias(sender, **kwargs):
    cache.delete(CACHE_CATEGORIAS)