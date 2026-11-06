from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.usuarios.models import PerfilUsuario


@receiver(post_save, sender=User)
def crear_perfil(sender, instance, created, **kwargs):
    """Crea un PerfilUsuario automáticamente al crear un User."""
    if created:
        PerfilUsuario.objects.get_or_create(user=instance)
