"""
Endpoints OAuth2 del Portal del Cliente.

`users_me` devuelve el perfil del usuario autenticado con un token
de acceso emitido por este sitio (Wagtail). Es consumido por la API
del portal (FastAPI) para sincronizar el PerfilUsuario local.
"""
from django.http import JsonResponse
from oauth2_provider.decorators import protected_resource


@protected_resource(scopes=["read"])
def users_me(request):
    """Perfil del usuario propietario del token Bearer."""
    user = request.resource_owner
    perfil = getattr(user, "perfil", None)

    def _get(dct, key):
        return dct.get(key, "") if dct else ""

    data = {
        "id": user.pk,
        "username": user.username,
        "email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "full_name": user.get_full_name(),
        "is_active": user.is_active,
        "email_verified": True,
        # Datos del perfil extendido (persona natural / jurídica)
        "tipo_persona": perfil.tipo_usuario if perfil else "natural",
        "telefono": perfil.telefono if perfil else "",
        "direccion": perfil.direccion if perfil else "",
        "ciudad": perfil.ciudad if perfil else "",
        "provincia": perfil.provincia if perfil else "",
        "numero_identidad": perfil.numero_identidad if perfil else "",
        "razon_social": perfil.nombre_empresa if perfil else "",
        "cliente_id_sasa": perfil.cliente_id_sasa if perfil else "",
        "cif_nit": perfil.cif_nit if perfil else "",
        "representante_legal": perfil.representante_legal if perfil else "",
    }
    return JsonResponse(data)