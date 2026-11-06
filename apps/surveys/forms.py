"""
Formulario dinamico para votar en encuestas (16 tipos de pregunta).

Cada pregunta se convierte en un campo 'pregunta_{id}' con el widget y la
validacion apropiada segun su tipo:

- simple / imagenes / par     : ChoiceField (radio) u oculto con componente visual.
- multiple                    : MultipleChoiceField (checkbox).
- estrellas / nps / slider    : campo numerico guardado en un hidden (JS visual).
- emojis                      : campo numerico 1..5 (hidden, JS visual).
- sino                        : campo con valores si/no (hidden, JS toggle).
- ranking                     : campo oculto con JSON de ids ordenados (JS Sortable).
- matriz                      : campo oculto con JSON {fila: valor} (JS).
- texto_corto / texto_largo   : CharField con max_length y contador.
- fecha / hora                : DateField / TimeField nativos.
- numero                      : campo numerico con rango configurable.
"""
import json

from django import forms

from apps.surveys.models import TIPOS_ESTRELLA, TIPOS_EMOJIS, TIPOS_MATRIZ, \
    TIPOS_NPS, TIPOS_RANKING, TIPOS_SINO, TIPOS_SLIDER


class EncuestaForm(forms.Form):
    """Formulario generado dinamicamente a partir de las preguntas de una encuesta."""

    def __init__(self, encuesta, *args, **kwargs):
        initial = kwargs.pop("initial", None)
        super().__init__(*args, initial=initial)
        self.encuesta = encuesta

        for pregunta in encuesta.preguntas_ordenadas():
            field_name = f"pregunta_{pregunta.pk}"
            opciones = [(o.pk, o.texto) for o in pregunta.opciones.all()]
            self._agregar_campo(pregunta, field_name, opciones)

    # ── Despacho por tipo ─────────────────────────────────────
    def _agregar_campo(self, pregunta, field_name, opciones):
        tipo = pregunta.tipo
        requerida = pregunta.requerida
        common = {"label": pregunta.texto, "required": requerida, "help_text": pregunta.ayuda}

        if tipo == "simple":
            self.fields[field_name] = forms.ChoiceField(
                choices=opciones, widget=forms.RadioSelect(),
                **common,
                error_messages={"required": "Debes seleccionar una opcion."},
            )
        elif tipo == "multiple":
            self.fields[field_name] = forms.MultipleChoiceField(
                choices=opciones, widget=forms.CheckboxSelectMultiple(),
                **common,
                error_messages={"required": "Debes seleccionar al menos una opcion."},
            )
        elif tipo in ("texto_corto", "texto_largo"):
            maximo = 200 if tipo == "texto_corto" else 2000
            widget = forms.TextInput if tipo == "texto_corto" else forms.Textarea
            self.fields[field_name] = forms.CharField(
                widget=widget(),
                max_length=maximo, required=requerida,
                error_messages={"required": "Por favor escribe una respuesta."},
            )
        elif tipo == "fecha":
            self.fields[field_name] = forms.DateField(
                widget=forms.DateInput(attrs={"type": "date"}),
                required=requerida,
                error_messages={"required": "Por favor elige una fecha."},
            )
        elif tipo == "hora":
            self.fields[field_name] = forms.TimeField(
                widget=forms.TimeInput(attrs={"type": "time"}),
                required=requerida,
                error_messages={"required": "Por favor elige una hora."},
            )
        elif tipo == TIPOS_NPS:
            self.fields[field_name] = forms.IntegerField(
                widget=forms.HiddenInput(),
                min_value=0, max_value=10, required=requerida,
                error_messages={"required": "Selecciona un valor del 0 al 10."},
            )
        elif tipo in (TIPOS_ESTRELLA, TIPOS_EMOJIS):
            self.fields[field_name] = forms.IntegerField(
                widget=forms.HiddenInput(),
                min_value=1, max_value=5, required=requerida,
                error_messages={"required": "Por favor responde."},
            )
        elif tipo == TIPOS_SINO:
            self.fields[field_name] = forms.ChoiceField(
                choices=[("si", "Si"), ("no", "No")],
                widget=forms.HiddenInput(),
                required=requerida,
                error_messages={"required": "Por favor responde Si o No."},
            )
        elif tipo in ("numero", TIPOS_SLIDER):
            minimo = pregunta.min_valor if pregunta.min_valor is not None else 0
            maximo = pregunta.max_valor if pregunta.max_valor is not None else 100
            self.fields[field_name] = forms.FloatField(
                widget=forms.HiddenInput(),
                min_value=minimo, max_value=maximo, required=requerida,
                error_messages={
                    "required": "Por favor mueve el control / escribe un valor.",
                    "min_value": f"El valor minimo es {minimo}.",
                    "max_value": f"El valor maximo es {maximo}.",
                },
            )
        elif tipo == TIPOS_RANKING:
            self.fields[field_name] = forms.CharField(
                widget=forms.HiddenInput(), required=requerida,
                error_messages={"required": "Ordena las opciones (arrastra para ordenar)."},
            )
        elif tipo == TIPOS_MATRIZ:
            self.fields[field_name] = forms.CharField(
                widget=forms.HiddenInput(), required=requerida,
                error_messages={"required": "Completa todas las filas de la matriz."},
            )
        elif tipo in ("imagenes", "par"):
            self.fields[field_name] = forms.CharField(
                widget=forms.HiddenInput(), required=requerida,
                error_messages={"required": "Debes elegir una opcion."},
            )
        else:
            # Fallback conservador: radio
            self.fields[field_name] = forms.ChoiceField(
                choices=opciones, widget=forms.RadioSelect(),
                required=requerida,
                error_messages={"required": "Debes seleccionar una opcion."},
            )

    # ── Limpieza extra por tipo ───────────────────────────────
    def clean(self):
        cleaned = super().clean()
        if not cleaned:
            return cleaned
        for pregunta in self.encuesta.preguntas_ordenadas():
            field_name = f"pregunta_{pregunta.pk}"
            valor = cleaned.get(field_name)
            if valor in (None, ""):
                continue
            if pregunta.tipo == TIPOS_RANKING:
                try:
                    valor = json.loads(valor)
                    ids = [int(x) for x in valor]
                    opc_ids = set(pregunta.opciones.values_list("id", flat=True))
                    if not set(ids).issubset(opc_ids):
                        self.add_error(field_name, "Se incluyó una opcion invalida.")
                        continue
                    cleaned[field_name] = ids
                except (ValueError, TypeError):
                    self.add_error(field_name, "El orden no es valido.")
            elif pregunta.tipo == TIPOS_MATRIZ:
                try:
                    data = json.loads(valor)
                    if isinstance(data, dict) and all(k in (pregunta.filas or []) for k in data):
                        cleaned[field_name] = data
                    else:
                        self.add_error(field_name, "La matriz no es valida.")
                except (ValueError, TypeError):
                    self.add_error(field_name, "La matriz no es valida.")
            elif pregunta.tipo in ("imagenes", "par"):
                try:
                    cleaned[field_name] = int(valor)
                except (TypeError, ValueError):
                    self.add_error(field_name, "Opcion invalida.")
        return cleaned