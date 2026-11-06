from datetime import date

from django import template

register = template.Library()


def _tema_vigente():
    """Devuelve el tema visual vigente (activo y con fecha actual dentro del
    rango). Si hay varios, el más reciente por fecha de inicio."""
    from apps.core.models import Tema

    hoy = date.today()
    return (
        Tema.objects.filter(
            activo=True,
            fecha_inicio__lte=hoy,
            fecha_fin__gte=hoy,
        )
        .order_by("-fecha_inicio")
        .first()
    )


def _logo_imagen():
    """Imagen a usar como logo: el del tema vigente si lo tiene, si no el
    de la página de inicio (bloque 'logo'). Devuelve None si no hay ninguno."""
    tema = _tema_vigente()
    if tema and tema.logo:
        return tema.logo

    try:
        from apps.automotive.models import AutomotivePage

        home = AutomotivePage.objects.live().order_by('path').first()
        if home is None or not home.logo:
            return None

        for block in home.logo:
            if block.block_type == 'logo':
                return block.value
    except Exception:
        return None
    return None


@register.simple_tag(takes_context=True)
def nav_anchor(context, anchor):
    """Devuelve el href de una ancla de la portada.

    Si estamos en la portada (URL raíz) usa la ancla local para
    mantener el scroll suave; si no, apunta a la portada para
    'enlazar con el nav principal' (la home).
    """
    page = context.get('page')
    is_home = page is not None and page.url == '/'
    return anchor if is_home else ('/' + anchor)


@register.simple_tag(takes_context=True)
def navbar_logo(context):
    """Devuelve la URL del logo que se muestra en el navbar.

    Prioriza el logo del tema vigente (si el tema lo define); en caso
    contrario usa el logo de la página de inicio. Si no hay, devuelve
    ``None`` para que la plantilla muestre el fallback.
    """
    return _logo_url(None, spec='fill-40x40')


@register.simple_tag(takes_context=True)
def navbar_logo_large(context):
    """URL del logo en alta resolución (para el preloader).

    Usa la misma lógica que el navbar: tema vigente o logo de la home.
    Devuelve ``None`` si no hay logo, para que la plantilla muestre el
    fallback (marca de texto).
    """
    return _logo_url(None, spec='max-320x320')


def _logo_url(context, spec):
    from wagtail.images.shortcuts import get_rendition_or_not_found
    from wagtail.images.models import SourceImageIOError

    try:
        imagen = _logo_imagen()
        if imagen is None:
            return None
        try:
            rendicion = get_rendition_or_not_found(imagen, spec)
            return rendicion.url
        except (SourceImageIOError, Exception):
            return imagen.file.url
    except Exception:
        return None
