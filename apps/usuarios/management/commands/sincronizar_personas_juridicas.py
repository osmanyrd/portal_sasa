"""Sincroniza personas jurídicas desde un sistema externo (ERP).

Uso:
  python manage.py sincronizar_personas_juridicas --datos '[...]'
  python manage.py sincronizar_personas_juridicas --archivo datos.json
  python manage.py sincronizar_personas_juridicas --ejemplo

Cada registro debe tener:
  - cif_nit (obligatorio, usado como identificador único)
  - nombre_empresa (obligatorio)
  - email (obligatorio)
  - representante_legal (opcional)
  - activo (opcional, default True)
  - telefono (opcional)
  - direccion (opcional)
  - ciudad (opcional)
  - provincia (opcional)
"""

import json
import secrets
import string

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils.text import slugify

from apps.usuarios.models import PerfilUsuario


def _generar_password(longitud=12):
    """Genera una contraseña aleatoria segura."""
    chars = string.ascii_letters + string.digits + "!@#$%&*"
    return "".join(secrets.choice(chars) for _ in range(longitud))


def _username_desde_cif(cif_nit):
    """Genera un username a partir del CIF/NIT."""
    base = slugify(cif_nit)[:20].strip("-")
    if not base:
        base = "empresa"
    username = base
    i = 1
    while User.objects.filter(username=username).exists():
        username = f"{base}{i}"
        i += 1
    return username


class Command(BaseCommand):
    help = "Sincroniza personas jurídicas desde un sistema externo (ERP/Odoo)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--datos", type=str,
            help="JSON string con la lista de personas jurídicas.",
        )
        parser.add_argument(
            "--archivo", type=str,
            help="Ruta a un archivo JSON con los datos.",
        )
        parser.add_argument(
            "--ejemplo", action="store_true",
            help="Crea 3 personas jurídicas de ejemplo.",
        )
        parser.add_argument(
            "--dry-run", action="store_true",
            help="Simula sin guardar cambios.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]

        if options["ejemplo"]:
            datos = [
                {
                    "cif_nit": "CUP20123456",
                    "nombre_empresa": "Autopartes del Caribe S.A.",
                    "email": "contacto@autopartes.cu",
                    "representante_legal": "María López García",
                    "telefono": "+53 5555 1234",
                    "ciudad": "La Habana",
                    "provincia": "La Habana",
                    "activo": True,
                },
                {
                    "cif_nit": "CUP98765432",
                    "nombre_empresa": "Talleres Mecánicos Unidos S.R.L.",
                    "email": "admin@talleres-unidos.cu",
                    "representante_legal": "Carlos Rodríguez Pérez",
                    "telefono": "+53 5555 5678",
                    "ciudad": "Santiago de Cuba",
                    "provincia": "Santiago de Cuba",
                    "activo": True,
                },
                {
                    "cif_nit": "CUP55555555",
                    "nombre_empresa": "Distribuidora de Neumáticos S.A.",
                    "email": "ventas@neumaticos.cu",
                    "representante_legal": "Ana Martínez Díaz",
                    "activo": False,
                },
            ]
        elif options["datos"]:
            datos = json.loads(options["datos"])
        elif options["archivo"]:
            with open(options["archivo"], "r", encoding="utf-8") as f:
                datos = json.load(f)
        else:
            self.stderr.write(
                "Usá --ejemplo, --datos o --archivo para proporcionar los datos."
            )
            return

        if not isinstance(datos, list):
            self.stderr.write("Los datos deben ser una lista de registros.")
            return

        with transaction.atomic():
            creados, actualizados, errores = 0, 0, 0

            for registro in datos:
                cif = (registro.get("cif_nit") or "").strip()
                nombre_emp = (registro.get("nombre_empresa") or "").strip()
                email = (registro.get("email") or "").strip().lower()

                if not cif or not nombre_emp or not email:
                    self.stderr.write(
                        f"Registro inválido (falta cif/nombre/email): {registro}"
                    )
                    errores += 1
                    continue

                # Buscar perfil existente por CIF
                perfil = PerfilUsuario.objects.filter(cif_nit=cif).first()

                if perfil:
                    # Actualizar
                    user = perfil.user
                    user.email = email
                    user.first_name = nombre_emp[:150]
                    if not dry_run:
                        user.save()
                    perfil.nombre_empresa = nombre_emp
                    perfil.representante_legal = registro.get("representante_legal", "")
                    perfil.telefono = registro.get("telefono", "")
                    perfil.direccion = registro.get("direccion", "")
                    perfil.ciudad = registro.get("ciudad", "")
                    perfil.provincia = registro.get("provincia", "")
                    perfil.activo = registro.get("activo", True)
                    if not dry_run:
                        perfil.save()
                    actualizados += 1
                    self.stdout.write(f"  Actualizado: {nombre_emp} ({cif})")
                else:
                    # Crear
                    username = _username_desde_cif(cif)
                    password = _generar_password()

                    if dry_run:
                        self.stdout.write(
                            f"  [DRY-RUN] Crearía: {nombre_emp} ({cif}) "
                            f"user={username}"
                        )
                    else:
                        user = User.objects.create_user(
                            username=username,
                            email=email,
                            password=password,
                            first_name=nombre_emp[:150],
                            is_active=True,
                        )
                        perfil = user.perfil
                        perfil.tipo_usuario = "juridica"
                        perfil.origen = "externo"
                        perfil.nombre_empresa = nombre_emp
                        perfil.cif_nit = cif
                        perfil.representante_legal = registro.get(
                            "representante_legal", ""
                        )
                        perfil.telefono = registro.get("telefono", "")
                        perfil.direccion = registro.get("direccion", "")
                        perfil.ciudad = registro.get("ciudad", "")
                        perfil.provincia = registro.get("provincia", "")
                        perfil.activo = registro.get("activo", True)
                        perfil.save()

                        self.stdout.write(
                            f"  Creado: {nombre_emp} ({cif}) "
                            f"user={username} pass={password}"
                        )
                    creados += 1

            if dry_run:
                self.stdout.write(
                    self.style.WARNING(
                        f"\n[DRY-RUN] Creados: {creados}, "
                        f"Actualizados: {actualizados}, Errores: {errores}"
                    )
                )
            else:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"\nListo: {creados} creados, "
                        f"{actualizados} actualizados, {errores} errores"
                    )
                )
