"""
Templatetag para el modal de encuesta.

Uso en el template base:
    {% load survey_tags %}
    {% mostrar_modal_encuesta %}

Renderiza el modal de invitacion y el JS que controla
la visibilidad segun cookie/session.
"""
from django import template

from apps.surveys.forms import EncuestaForm
from apps.surveys.models import Encuesta

register = template.Library()


def _get_session_key(request):
    """Obtiene la clave de sesion, creandola si es necesario."""
    if not hasattr(request, "session") or not hasattr(request.session, "session_key"):
        return ""
    if not request.session.session_key:
        request.session.create()
    return request.session.session_key or ""


@register.inclusion_tag(
    "surveys/includes/survey_modal.html",
    takes_context=True,
)
def mostrar_modal_encuesta(context):
    """
    Busca la encuesta vigente con mostrar_modal=True y pasa al template:
    - encuesta_modal: la encuesta (o None)
    - session_key: clave de sesion actual
    """
    request = context.get("request")
    encuesta = None

    # Solo las encuestas de CAMPANA muestran modal; las fijas nunca.
    encuestas = Encuesta.objects.filter(
        activa=True,
        tipo_encuesta="campana",
        mostrar_modal=True,
        mostrar_modal_primera_visita=True,
    ).order_by("-fecha_inicio")

    for enc in encuestas:
        if enc.esta_vigente():
            encuesta = enc
            break

    session_key = ""
    if request:
        session_key = _get_session_key(request)

    return {
        "encuesta_modal": encuesta,
        "session_key": session_key,
        "request": request,
    }


@register.inclusion_tag(
    "surveys/includes/survey_widget.html",
    takes_context=True,
)
def mostrar_encuesta_activa(context):
    """
    Busca la encuesta vigente y pasa al widget (survey_widget.html) todo lo
    necesario para mostrar el formulario, los resultados o el aviso de "ya
    voto", segun corresponda para el usuario actual.
    """
    request = context.get("request")
    encuesta = None

    for enc in Encuesta.objects.filter(activa=True).order_by("-fecha_inicio"):
        if enc.esta_vigente():
            encuesta = enc
            break

    base = {"encuesta": encuesta}
    if not encuesta:
        return base

    session_key = _get_session_key(request) if request else ""

    # Pendiente significa que el usuario puede responderla ahora:
    #  - Campana: si no la completo.
    #  - Fija: si esta dentro del periodo de espera permitido.
    esta_pendiente = encuesta.es_pendiente_para(session_key) if session_key else True

    if encuesta.esta_vigente():
        if esta_pendiente:
            base["formulario"] = EncuestaForm(encuesta)
        else:
            base["ya_voto"] = True
            base["resultados"] = encuesta.resultados()
    else:
        base["resultados"] = encuesta.resultados()

    return base
