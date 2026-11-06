import re

from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

from apps.usuarios.models import PerfilUsuario


class RegistroPersonaNaturalForm(UserCreationForm):
    """Formulario de registro solo para persona natural."""

    email = forms.EmailField(
        required=True, label="Correo electrónico",
        help_text="Usado para activar tu cuenta.",
    )
    first_name = forms.CharField(
        max_length=150, required=True, label="Nombre",
    )
    last_name = forms.CharField(
        max_length=150, required=True, label="Apellido",
    )
    telefono = forms.CharField(
        max_length=30, required=True, label="Teléfono",
    )
    numero_identidad = forms.CharField(
        max_length=30, required=True, label="Número de identidad",
        help_text="Cédula de identidad o pasaporte.",
    )
    acepta_terminos = forms.BooleanField(
        required=True,
        label="Acepto los términos y condiciones",
        error_messages={"required": "Debes aceptar los términos para registrarte."},
    )

    class Meta:
        model = User
        fields = [
            "username", "email", "first_name", "last_name",
            "password1", "password2",
        ]

    def clean_email(self):
        email = self.cleaned_data.get("email", "").strip().lower()
        if User.objects.filter(email=email).exists():
            raise ValidationError("Este correo ya está registrado.")
        return email

    def clean_numero_identidad(self):
        num = self.cleaned_data.get("numero_identidad", "").strip()
        if not re.match(r"^\d{11}$|^[A-Z0-9]{8,15}$", num, re.IGNORECASE):
            raise ValidationError(
                "Formato no válido (ej.: 12345678901 o P123456789)."
            )
        if PerfilUsuario.objects.filter(numero_identidad=num).exists():
            raise ValidationError("Este número de identidad ya está registrado.")
        return num

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        user.first_name = self.cleaned_data["first_name"]
        user.last_name = self.cleaned_data["last_name"]
        if commit:
            user.save()
            perfil = user.perfil
            perfil.tipo_usuario = "natural"
            perfil.origen = "sitio"
            perfil.telefono = self.cleaned_data["telefono"]
            perfil.numero_identidad = self.cleaned_data["numero_identidad"]
            perfil.acepta_terminos = self.cleaned_data["acepta_terminos"]
            perfil.activo = False  # Se activa con el enlace del correo
            perfil.save()
        return user


class RegistroJuridicoForm(forms.Form):
    """Formulario simplificado: solo número de cliente SASA."""

    cliente_id_sasa = forms.CharField(
        max_length=50,
        label="Número de cliente SASA",
        widget=forms.TextInput(
            attrs={
                "placeholder": "Ej.: SASA001",
                "autofocus": True,
                "class": "form-control form-control-lg",
                "id": "id_cliente_id_sasa",
            }
        ),
        help_text="Ingresá el número de cliente asignado por SASA.",
    )

    def clean_cliente_id_sasa(self):
        num = self.cleaned_data.get("cliente_id_sasa", "").strip()
        if not num:
            raise ValidationError("Este campo es obligatorio.")
        return num


class LoginForm(forms.Form):
    """Formulario de inicio de sesión."""

    username = forms.CharField(
        label="Usuario",
        max_length=150,
        widget=forms.TextInput(attrs={"autofocus": True, "placeholder": "Tu usuario"}),
    )
    password = forms.CharField(
        label="Contraseña",
        widget=forms.PasswordInput(attrs={"placeholder": "Tu contraseña"}),
    )


class PerfilForm(forms.ModelForm):
    """Formulario de edición de perfil."""

    class Meta:
        model = PerfilUsuario
        fields = [
            "telefono", "direccion", "ciudad", "provincia", "avatar",
        ]
        widgets = {
            "direccion": forms.Textarea(attrs={"rows": 3}),
        }


class PerfilJuridicoForm(forms.ModelForm):
    """Formulario adicional para datos de empresa (persona jurídica)."""

    class Meta:
        model = PerfilUsuario
        fields = ["nombre_empresa", "cif_nit", "representante_legal"]
