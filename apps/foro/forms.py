"""Formularios públicos del foro.

- ``NuevoTemaForm``     : usado por ``ForoIndexPage`` para crear temas.
- ``NuevaRespuestaForm``: usado por ``TemaForo`` para responder.

Ambos permiten participación anónima con nombre opcional. El texto se
convierte a HTML seguro en el servidor (escapado, sanitizado).

"""

from django import forms

from apps.foro.models import CategoriaForo


def html_seguro(texto):
    """Escapa caracteres HTML y convierte los saltos de línea en <br>.

    Garantiza que el contenido introducido por un visitante jamás pueda
    inyectar marcado/scripts: todo se escapa antes de guardarse.
    """
    from django.utils.html import escape

    texto = (texto or "").strip()
    if not texto:
        return ""
    return escape(texto).replace("\r\n", "\n").replace("\n", "<br>")


class NuevoTemaForm(forms.Form):
    """Formulario para crear un nuevo tema de discusión."""

    categoria = forms.ModelChoiceField(
        queryset=CategoriaForo.objects.filter(activo=True),
        empty_label="Selecciona una categoría",
        label="Categoría",
        widget=forms.Select(attrs={"class": "form-select", "required": True}),
    )
    titulo = forms.CharField(
        max_length=250,
        label="Título del tema",
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "Ej.: Cambio de aceite sintético", "required": True}
        ),
    )
    cuerpo = forms.CharField(
        label="Contenido",
        widget=forms.Textarea(
            attrs={
                "class": "form-control",
                "rows": 6,
                "placeholder": "Describe tu duda o comentario…",
                "required": True,
            }
        ),
    )
    nombre_anonimo = forms.CharField(
        max_length=150,
        required=False,
        label="Tu nombre",
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "Tu nombre de pila (opcional)"}
        ),
    )

    def __init__(self, *args, requiere_nombre=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["nombre_anonimo"].required = requiere_nombre
        if requiere_nombre:
            self.fields["nombre_anonimo"].label = "Tu nombre"

    def clean_cuerpo(self):
        return self.cleaned_data["cuerpo"].strip()

    def clean_titulo(self):
        return self.cleaned_data["titulo"].strip()


class NuevaRespuestaForm(forms.Form):
    """Formulario para responder a un tema."""

    cuerpo = forms.CharField(
        label="Tu respuesta",
        widget=forms.Textarea(
            attrs={"class": "form-control", "rows": 4, "placeholder": "Escribe tu respuesta…", "required": True}
        ),
    )
    nombre_anonimo = forms.CharField(
        max_length=150,
        required=False,
        label="Tu nombre",
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "Tu nombre de pila (opcional)"}
        ),
    )

    def __init__(self, *args, requiere_nombre=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["nombre_anonimo"].required = requiere_nombre
        if requiere_nombre:
            self.fields["nombre_anonimo"].label = "Tu nombre"

    def clean_cuerpo(self):
        return self.cleaned_data["cuerpo"].strip()
