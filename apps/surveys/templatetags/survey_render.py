"""
Templatetags para renderizar los 16 tipos de preguntas en el formulario.

La mayoria de tipos usan componentes visuales (estrellas, slider, emojis,
ranking, etc.) alimentados por un input oculto ``pregunta_<id>`` que el JS
de ``survey_interactive.js`` rellena. Los tipos de texto/fecha/hora usan los
widgets nativos de Django (desplegados con ``{{ field }}``).
"""
import json

from django import template

register = template.Library()


@register.filter
def formfield(form, name):
    """Devuelve el campo ``name`` de un Form, o ``None`` si no existe."""
    try:
        return form[name]
    except KeyError:
        return None


@register.filter
def tojson(value):
    try:
        return json.dumps(value, ensure_ascii=False)
    except (TypeError, ValueError):
        return "[]"


@register.inclusion_tag("surveys/includes/pregunta_component.html", takes_context=True)
def render_pregunta_form(context, pregunta, form):
    """Renderiza el componente visual segun el tipo de pregunta."""
    request = context.get("request")
    field_name = f"pregunta_{pregunta.pk}"
    campo = form[field_name]

    valor_inicial = context.get("autosave", {}).get(field_name)
    if valor_inicial is None:
        valor_inicial = form.initial.get(field_name) or []

    opciones = list(pregunta.opciones.all())

    extras = {
        "campo": campo,
        "tipo": pregunta.tipo,
        "nombre": field_name,
        "pregunta": pregunta,
        "opciones": opciones,
        "valor_inicial": valor_inicial,
        "min": pregunta.min_valor if pregunta.min_valor is not None else 0,
        "max": pregunta.max_valor if pregunta.max_valor is not None else 100,
        "paso": pregunta.paso or 1,
        "etiqueta_min": pregunta.etiqueta_min,
        "etiqueta_max": pregunta.etiqueta_max,
        "etiqueta_izq": pregunta.etiqueta_izq,
        "etiqueta_der": pregunta.etiqueta_der,
        "filas": pregunta.filas or [],
        "emojis": [1, 2, 3, 4, 5],
    }
    return extras