"""
Context processors del proyecto.

Inyecta variables globales en el contexto de todas las plantillas.
"""
from django.conf import settings
from django.core.cache import cache


def site(request):
    """Inyecta el nombre del sitio."""
    return {"SITE_NAME": settings.WAGTAIL_SITE_NAME}


def tema_activo(request):
    """
    Calcula el tema vigente segun la fecha actual y lo inyecta
    en el contexto de todas las plantillas.

    Variables disponibles en todos los templates:
    - tema_activo: instancia de Tema o None
    - logo_sitio: imagen del logo (tema o defecto)
    - banner_sitio: imagen del banner (tema o defecto)
    - color_acento: color hex (tema o defecto)
    """
    from datetime import date
    from apps.core.models import ConfiguracionTema, Tema

    # Buscar el tema vigente mas reciente (cache 5 min)
    cache_key = "tema_activo_context"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    hoy = date.today()
    tema = (
        Tema.objects.filter(
            activo=True,
            fecha_inicio__lte=hoy,
            fecha_fin__gte=hoy,
        )
        .order_by("-fecha_inicio")
        .first()
    )

    # Obtener configuracion por defecto (via Wagtail settings)
    try:
        config = ConfiguracionTema.for_site(request.site) if hasattr(request, "site") else None
    except Exception:
        config = None

    # Si no hay request.site, intentar obtener la config de otra forma
    if config is None:
        try:
            from wagtail.models import Site
            site_obj = Site.objects.filter(is_default_site=True).first()
            if site_obj:
                config = ConfiguracionTema.for_site(site_obj)
        except Exception:
            config = None

    # Determinar logo, banner y color
    if tema and tema.logo:
        logo_sitio = tema.logo
    elif config and config.logo_default:
        logo_sitio = config.logo_default
    else:
        # Fallback al SiteSettings original
        try:
            from apps.core.models import SiteSettings
            if hasattr(request, "site"):
                site_settings = SiteSettings.for_site(request.site)
            else:
                site_settings = None
            logo_sitio = site_settings.logo if site_settings else None
        except Exception:
            logo_sitio = None

    if tema and tema.banner:
        banner_sitio = tema.banner
    elif config and config.banner_default:
        banner_sitio = config.banner_default
    else:
        banner_sitio = None

    if tema:
        color_acento = tema.color_acento
    elif config:
        color_acento = config.color_acento_default
    else:
        color_acento = "#0d6efd"

    result = {
        "tema_activo": tema,
        "logo_sitio": logo_sitio,
        "banner_sitio": banner_sitio,
        "color_acento": color_acento,
    }
    cache.set(cache_key, result, 300)  # 5 minutos
    return result
