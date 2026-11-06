from django import template

register = template.Library()


@register.inclusion_tag(
    "mapa/includes/mapa_modal.html",
    takes_context=True,
)
def mapa_modal_flotante(context):
    """Render the floating button + modal for the interactive map."""
    return {}


@register.inclusion_tag("mapa/includes/mapa_svg.html")
def render_mapa_cuba():
    """Renderiza el mapa SVG de Cuba por provincias (100% local, sin CDN)."""
    return {}
