from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from django.views.generic import TemplateView
from wagtail import urls as wagtail_urls
from wagtail.admin import urls as wagtailadmin_urls
from wagtail.contrib.sitemaps.views import sitemap
from wagtail.documents import urls as wagtaildocs_urls

from apps.core.views import api_buscar, buscar, contact_submit
from apps.catalogo_erp.views import catalogo_buscar
from apps.usuarios.oauth_views import users_me
from apps.pwa.views import manifest, offline, service_worker

urlpatterns = [
    path("django-admin/", admin.site.urls),
    path("cms/", include(wagtailadmin_urls)),
    path("documentos/", include(wagtaildocs_urls)),
    # OAuth2 provider (Portal del Cliente): /o/authorize/ /o/token/ /o/introspect/
    path("o/", include("oauth2_provider.urls")),
    # Perfil del usuario autenticado vía OAuth2 (consumido por el portal)
    path("api/v2/users/me/", users_me, name="oauth_users_me"),
    path("contacto/enviar/", contact_submit, name="contact-submit"),
    path("buscar/", buscar, name="buscar"),
    path("api/buscar/", api_buscar, name="api_buscar"),
    path("encuestas/", include("apps.surveys.urls")),
    path("api/chatbot/", include("apps.chatbot.urls")),
    path("api/mapa/", include("apps.mapa.urls")),
    path("api/informaciones/", include("apps.informaciones.urls")),
    path("api/catalogo/buscar/", catalogo_buscar, name="catalogo_erp_buscar"),
    path("cuenta/", include("apps.usuarios.urls")),
    path("sitemap.xml", sitemap, name="wagtail_sitemap"),
    path(
        "robots.txt",
        TemplateView.as_view(
            template_name="robots.txt", content_type="text/plain"
        ),
        name="robots_txt",
    ),
    # ── PWA: manifest, service worker y página offline (antes del catch-all) ──
    path("manifest.webmanifest", manifest, name="pwa_manifest"),
    path("sw.js", service_worker, name="pwa_sw"),
    path("offline.html", offline, name="pwa_offline"),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(
        settings.STATIC_URL, document_root=settings.STATIC_ROOT
    )

urlpatterns += [
    path("", include(wagtail_urls)),
]
