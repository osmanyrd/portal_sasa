"""Crea usuarios de prueba para el sistema de autenticación.

  python manage.py load_usuarios_sample
"""

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

from apps.usuarios.models import PerfilUsuario


class Command(BaseCommand):
    help = "Crea usuarios de prueba (persona natural + jurídica)."

    def handle(self, *args, **options):
        # ── Persona natural ──
        user_nat, created = User.objects.get_or_create(
            username="carlos_mendez",
            defaults={
                "email": "carlos.mendez@email.cu",
                "first_name": "Carlos",
                "last_name": "Méndez López",
                "is_active": True,
            },
        )
        if created:
            user_nat.set_password("test1234")
            user_nat.save()
            perfil = user_nat.perfil
            perfil.tipo_usuario = "natural"
            perfil.origen = "manual"
            perfil.telefono = "+53 5555 1111"
            perfil.numero_identidad = "90123456789"
            perfil.direccion = "Ave. 51 #1234, La Habana"
            perfil.ciudad = "La Habana"
            perfil.provincia = "La Habana"
            perfil.save()
            self.stdout.write(
                self.style.SUCCESS(
                    f"  Natural: carlos_mendez / test1234  ({user_nat.email})"
                )
            )
        else:
            self.stdout.write("  Natural: carlos_mendez ya existe.")

        # ── Persona jurídica ──
        user_jur, created = User.objects.get_or_create(
            username="empresa_autopartes",
            defaults={
                "email": "contacto@autopartes.cu",
                "first_name": "Autopartes del Caribe S.A.",
                "is_active": True,
            },
        )
        if created:
            user_jur.set_password("empresa123")
            user_jur.save()
            perfil = user_jur.perfil
            perfil.tipo_usuario = "juridica"
            perfil.origen = "externo"
            perfil.nombre_empresa = "Autopartes del Caribe S.A."
            perfil.cif_nit = "CUP20123456"
            perfil.representante_legal = "María López García"
            perfil.telefono = "+53 5555 2222"
            perfil.direccion = "Zona Industrial, Santiago de Cuba"
            perfil.ciudad = "Santiago de Cuba"
            perfil.provincia = "Santiago de Cuba"
            perfil.save()
            self.stdout.write("  Juridica: empresa_autopartes / empresa123  (CIF %s)" % perfil.cif_nit)
        else:
            self.stdout.write("  Jurídica: empresa_autopartes ya existe.")

        self.stdout.write(self.style.SUCCESS("Listo."))