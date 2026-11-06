from django import forms
from django.core.validators import RegexValidator

PHONE_VALIDATOR = RegexValidator(
    regex=r"^[0-9+\-\s().]{6,25}$",
    message="Ingresá un número de teléfono válido.",
)


class ContactMessageForm(forms.Form):
    nombre = forms.CharField(
        max_length=120,
        min_length=2,
        label="Nombre y apellido",
        widget=forms.TextInput(
            attrs={"placeholder": "Tu nombre", "autocomplete": "name"}
        ),
    )
    email = forms.EmailField(
        label="Correo electrónico",
        widget=forms.EmailInput(
            attrs={"placeholder": "tu@correo.com", "autocomplete": "email"}
        ),
    )
    telefono = forms.CharField(
        max_length=25,
        required=False,
        validators=[PHONE_VALIDATOR],
        label="Teléfono (opcional)",
        widget=forms.TextInput(attrs={"placeholder": "+54 11 5555-5555"}),
    )
    mensaje = forms.CharField(
        min_length=10,
        max_length=3000,
        label="Mensaje",
        widget=forms.Textarea(
            attrs={"rows": 5, "placeholder": "Contanos en qué podemos ayudarte"}
        ),
    )
    website = forms.CharField(required=False, widget=forms.HiddenInput)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name in ("nombre", "email", "telefono", "mensaje"):
            css = self.fields[field_name].widget.attrs.setdefault("class", "")
            self.fields[field_name].widget.attrs["class"] = (
                css + " form-control"
            ).strip()

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get("website"):
            raise forms.ValidationError("Solicitud rechazada.")
        return cleaned_data
