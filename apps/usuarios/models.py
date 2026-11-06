import secrets

from django.conf import settings
from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone


class PerfilUsuario(models.Model):
    """Perfil extendido vinculado al User de Django."""

    TIPO_CHOICES = [("natural", "Persona Natural"), ("juridica", "Persona Jurídica")]
    ORIGEN_CHOICES = [("sitio", "Registro público"), ("externo", "Integrado desde ERP")]

    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="perfil", verbose_name="Usuario"
    )
    tipo_usuario = models.CharField(
        max_length=10, choices=TIPO_CHOICES, default="natural", verbose_name="Tipo",
        db_index=True,
    )
    avatar = models.ForeignKey(
        "wagtailimages.Image",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        verbose_name="Avatar",
    )
    telefono = models.CharField(max_length=30, blank=True, verbose_name="Teléfono")
    direccion = models.TextField(blank=True, verbose_name="Dirección")
    ciudad = models.CharField(max_length=100, blank=True, verbose_name="Ciudad")
    provincia = models.CharField(max_length=100, blank=True, verbose_name="Provincia")

    activo = models.BooleanField(default=True, verbose_name="Activa")
    fecha_registro = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de registro")
    ultimo_acceso = models.DateTimeField(null=True, blank=True, verbose_name="Último acceso")
    acepta_terminos = models.BooleanField(default=False, verbose_name="Acepta términos")

    # Campos de persona natural
    numero_identidad = models.CharField(
        max_length=30, blank=True, verbose_name="Número de identidad"
    )

    # Campos de persona jurídica
    cliente_id_sasa = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        unique=True,
        verbose_name="ID Cliente SASA",
        help_text="Número de cliente o ID en el sistema SASA.",
    )
    nombre_empresa = models.CharField(
        max_length=200, blank=True, verbose_name="Nombre de empresa"
    )
    cif_nit = models.CharField(max_length=30, blank=True, verbose_name="CIF / NIT")
    representante_legal = models.CharField(
        max_length=150, blank=True, verbose_name="Representante legal"
    )

    class Meta:
        verbose_name = "Perfil de usuario"
        verbose_name_plural = "Perfiles de usuarios"
        ordering = ["-fecha_registro"]

    def __str__(self):
        return f"{self.user.username} ({self.get_tipo_usuario_display()})"

    @property
    def es_natural(self):
        return self.tipo_usuario == "natural"

    @property
    def es_juridica(self):
        return self.tipo_usuario == "juridica"

    @property
    def display_name(self):
        full = self.user.get_full_name()
        return full or self.user.username

    def inicial(self):
        return self.display_name[:1].upper()

    @property
    def avatar_url(self):
        if self.avatar:
            return self.avatar.get_rendition("fill-60x60").url
        return None


class ConfiguracionSistemaExterno(models.Model):
    """Configuración del sistema complementario (ERP, etc.)."""

    nombre = models.CharField(max_length=100, verbose_name="Nombre")
    url = models.URLField(verbose_name="URL del sistema")
    clave_api = models.CharField(
        max_length=200, blank=True, verbose_name="Clave API (cifrada)"
    )
    activo = models.BooleanField(default=False, verbose_name="Activo")

    class Meta:
        verbose_name = "Sistema externo"
        verbose_name_plural = "Sistemas externos"

    def __str__(self):
        return f"{self.nombre} ({'activo' if self.activo else 'inactivo'})"

    @classmethod
    def activo_config(cls):
        return cls.objects.filter(activo=True).first()

    @property
    def clave_api_plana(self):
        """Clave API descifrada (se usa solo al conectar al sistema externo)."""
        from apps.catalogo_erp.crypto import descifrar

        return descifrar(self.clave_api) if self.clave_api else ""

    def save(self, *args, **kwargs):
        """Cifra la clave API solo si es nueva o está en texto plano."""
        from apps.catalogo_erp import crypto

        if self.clave_api and not self.clave_api.startswith(crypto._PREFIJOS_CIFRADOS):  # noqa: SLF001
            self.clave_api = crypto.cifrar(self.clave_api)
        super().save(*args, **kwargs)

    def generar_token(self, user):
        """Genera un token seguro con expiración para el usuario."""
        from django.core.signing import Signer

        signer = Signer()
        payload = f"{user.pk}:{user.username}:{timezone.now().timestamp()}"
        return signer.sign(payload)
