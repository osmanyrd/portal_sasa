from django.conf import settings
from django.contrib.auth import logout
from django.shortcuts import redirect

from apps.usuarios.models import PerfilUsuario


class SessionTimeoutMiddleware:
    """Cierra sesión si el usuario está inactivo o su perfil fue desactivado."""

    EXEMPT_URLS = [
        settings.LOGIN_URL if hasattr(settings, "LOGIN_URL") else "/cuenta/login/",
        "/cuenta/registro/",
        "/cuenta/activar/",
        "/django-admin/",
        "/cms/",
        "/api/",
    ]

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            # Verificar si el perfil fue desactivado
            try:
                perfil = request.user.perfil
                if not perfil.activo:
                    logout(request)
                    return redirect("login")
            except PerfilUsuario.DoesNotExist:
                pass

            # Verificar tiempo de sesión (30 min)
            last_login = request.session.get("last_login")
            if last_login:
                from datetime import datetime, timedelta

                try:
                    last = datetime.fromisoformat(last_login)
                    if datetime.now() - last > timedelta(minutes=30):
                        logout(request)
                        return redirect("login")
                except (ValueError, TypeError):
                    pass

            # Actualizar timestamp de sesión
            from datetime import datetime

            request.session["last_login"] = datetime.now().isoformat()

        response = self.get_response(request)
        return response
