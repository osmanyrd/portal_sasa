import logging

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.signing import BadSignature, Signer
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.usuarios.forms import (
    LoginForm,
    PerfilForm,
    PerfilJuridicoForm,
    RegistroPersonaNaturalForm,
)
from apps.usuarios.models import ConfiguracionSistemaExterno, PerfilUsuario
from apps.usuarios.services import verificar_cliente_sasa

logger = logging.getLogger(__name__)

LOGIN_URL = getattr(settings, "LOGIN_URL", "/cuenta/login/")


# ---------------------------------------------------------------------------
# Registro (solo persona natural)
# ---------------------------------------------------------------------------
def registro_view(request):
    if request.user.is_authenticated:
        return redirect("perfil")

    if request.method == "POST":
        form = RegistroPersonaNaturalForm(request.POST)
        if form.is_valid():
            user = form.save()
            _enviar_correo_activacion(request, user)
            messages.success(
                request,
                "¡Registro exitoso! Revisá tu correo para activar tu cuenta.",
            )
            return redirect("login")
    else:
        form = RegistroPersonaNaturalForm()

    return render(request, "usuarios/registro.html", {"form": form})


# ---------------------------------------------------------------------------
# Registro persona jurídica (verificación SASA)
# ---------------------------------------------------------------------------
@require_POST
def verificar_cliente_view(request):
    """
    AJAX: recibe cliente_id_sasa, consulta el servicio externo
    y retorna los datos del cliente en JSON.
    """
    numero = request.POST.get("cliente_id_sasa", "").strip()

    if not numero:
        return JsonResponse(
            {"ok": False, "error": "Debes ingresar un número de cliente."},
            status=400,
        )

    resultado = verificar_cliente_sasa(numero)

    if not resultado["valido"]:
        return JsonResponse(
            {"ok": False, "error": resultado.get("error", "Número no válido.")},
            status=404,
        )

    return JsonResponse({
        "ok": True,
        "razon_social": resultado["razon_social"],
        "cif_nit": resultado["cif_nit"],
        "representante_legal": resultado["representante_legal"],
        "email": resultado["email"],
        "telefono": resultado["telefono"],
        "direccion": resultado["direccion"],
    })


def registro_juridico_view(request):
    """
    Registro de persona jurídica: ingresa ID SASA → verifica (AJAX) → crea usuario.
    """
    if request.user.is_authenticated:
        return redirect("perfil")

    if request.method == "POST":
        action = request.POST.get("action")

        if action == "registrar":
            cliente_id = request.POST.get("cliente_id_sasa", "").strip()
            razon_social = request.POST.get("razon_social", "").strip()
            cif_nit = request.POST.get("cif_nit", "").strip()
            representante = request.POST.get("representante_legal", "").strip()
            email = request.POST.get("email", "").strip()
            telefono = request.POST.get("telefono", "").strip()
            direccion = request.POST.get("direccion", "").strip()

            if not cliente_id or not razon_social:
                messages.error(request, "Datos incompletos. Verificá el cliente de nuevo.")
                return redirect("registro_juridico")

            if PerfilUsuario.objects.filter(cliente_id_sasa=cliente_id).exists():
                messages.error(
                    request,
                    "Este número de cliente ya está registrado.",
                )
                return redirect("registro_juridico")

            # Generar username y password
            import secrets

            username = f"empresa_{cliente_id.lower()}"
            raw_password = secrets.token_urlsafe(12)

            user = User.objects.create_user(
                username=username,
                email=email,
                password=raw_password,
                first_name=razon_social[:150],
            )

            perfil = user.perfil
            perfil.tipo_usuario = "juridica"
            perfil.cliente_id_sasa = cliente_id
            perfil.nombre_empresa = razon_social
            perfil.cif_nit = cif_nit
            perfil.representante_legal = representante
            perfil.telefono = telefono
            perfil.direccion = direccion
            perfil.acepta_terminos = True
            perfil.activo = True
            perfil.save()

            messages.success(
                request,
                f"¡Registro exitoso! Usuario: {username} | Contraseña: {raw_password}",
            )
            return redirect("login")

    return render(request, "usuarios/registro_juridico.html")


def activar_cuenta(request, token):
    """Activa la cuenta del usuario a partir del token del correo."""
    try:
        signer = Signer()
        payload = signer.unsign(token)
        user_id = int(payload.split(":")[0])
        user = User.objects.get(pk=user_id)
    except (BadSignature, ValueError, User.DoesNotExist):
        messages.error(request, "El enlace de activación no es válido o expiró.")
        return redirect("login")

    perfil = getattr(user, "perfil", None)
    if perfil and perfil.activo:
        messages.info(request, "Tu cuenta ya está activada. Iniciá sesión.")
        return redirect("login")

    if perfil:
        perfil.activo = True
        perfil.save(update_fields=["activo"])
    user.is_active = True
    user.save(update_fields=["is_active"])

    messages.success(request, "¡Cuenta activada! Ya podés iniciar sesión.")
    return redirect("login")


def _enviar_correo_activacion(request, user):
    """Genera token y simula envío de correo (log en consola)."""
    signer = Signer()
    token = signer.sign(f"{user.pk}:{user.username}")
    activation_url = f"{request.build_absolute_uri('/cuenta/activar/')}{token}"
    logger.info("=== CORREO DE ACTIVACIÓN ===")
    logger.info("Para: %s", user.email)
    logger.info("Enlace: %s", activation_url)
    logger.info("============================")


# ---------------------------------------------------------------------------
# Login / Logout
# ---------------------------------------------------------------------------
def login_view(request):
    if request.user.is_authenticated:
        return redirect("perfil")

    if request.method == "POST":
        form = LoginForm(request.POST)
        if form.is_valid():
            user = authenticate(
                request,
                username=form.cleaned_data["username"],
                password=form.cleaned_data["password"],
            )
            if user is None:
                messages.error(request, "Usuario o contraseña incorrectos.")
            elif not user.is_active:
                messages.error(
                    request,
                    "Cuenta desactivada. Verificá tu correo o contactá al administrador.",
                )
            else:
                perfil = getattr(user, "perfil", None)
                if perfil and not perfil.activo:
                    messages.error(
                        request,
                        "Cuenta desactivada. Verificá tu correo para activarla.",
                    )
                else:
                    login(request, user)
                    if perfil:
                        perfil.ultimo_acceso = timezone.now()
                        perfil.save(update_fields=["ultimo_acceso"])
                    next_url = request.GET.get("next", "/")
                    return redirect(next_url)
    else:
        form = LoginForm()

    return render(request, "usuarios/login.html", {"form": form})


@login_required
def logout_view(request):
    logout(request)
    messages.success(request, "Sesión cerrada correctamente.")
    return redirect("login")


# ---------------------------------------------------------------------------
# Perfil
# ---------------------------------------------------------------------------
def _get_or_create_perfil(user):
    """Devuelve el PerfilUsuario del usuario, creándolo si no existe."""
    perfil, created = PerfilUsuario.objects.get_or_create(user=user)
    return perfil


def _datos_perfil(perfil):
    """Datos básicos del perfil para el encabezado del modal."""
    return {
        "display_name": perfil.display_name,
        "email": perfil.user.email,
        "tipo": perfil.get_tipo_usuario_display(),
        "es_juridica": perfil.es_juridica,
        "avatar_url": perfil.avatar_url or "",
    }


@login_required
def perfil_view(request):
    """
    Perfil del usuario como modal completo (datos personales + empresa).

    - Petición normal: renderiza la página que muestra el modal abierto.
    - Petición AJAX/XHR: devuelve solo el fragmento HTML del modal.
    - POST AJAX: guarda formularios y devuelve JSON.
    """
    perfil = _get_or_create_perfil(request.user)
    sistema_externo = ConfiguracionSistemaExterno.activo_config()

    if request.method == "POST":
        # Guardado AJAX: tabla de formulario (perfil | empresa)
        tabla = request.POST.get("tabla", "perfil")
        if tabla == "empresa":
            form = PerfilJuridicoForm(request.POST, instance=perfil)
        else:
            form = PerfilForm(request.POST, request.FILES, instance=perfil)

        if form.is_valid():
            form.save()
            return JsonResponse(
                {"ok": True, "mensaje": "Perfil actualizado correctamente."}
            )
        errors = form.errors.get_json_data()
        return JsonResponse(
            {"ok": False, "error": "Corrige los campos marcados.", "campos": errors},
            status=400,
        )

    ctx = {
        "perfil": perfil,
        "perfil_form": PerfilForm(instance=perfil),
        "perfil_juridico_form": PerfilJuridicoForm(instance=perfil)
        if perfil.es_juridica
        else None,
        "sistema_externo": sistema_externo,
    }
    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return render(request, "usuarios/includes/perfil_modal_body.html", ctx)
    return render(request, "usuarios/perfil.html", ctx)


@login_required
def perfil_juridico_view(request):
    """Redirige al perfil (modal) manteniendo la ruta por compatibilidad."""
    return redirect("perfil")


# ---------------------------------------------------------------------------
# Token para sistema externo
# ---------------------------------------------------------------------------
@login_required
def token_sistema_externo(request):
    """Genera un token seguro para acceder al sistema complementario."""
    config = ConfiguracionSistemaExterno.activo_config()
    if not config:
        return JsonResponse({"error": "Sistema externo no configurado."}, status=404)

    token = config.generar_token(request.user)
    return JsonResponse({
        "token": token,
        "url": config.url,
        "usuario": request.user.username,
        "tipo": _get_or_create_perfil(request.user).tipo_usuario,
    })


# ---------------------------------------------------------------------------
# API: avatar del usuario (para el menú)
# ---------------------------------------------------------------------------
@login_required
def user_avatar_api(request):
    perfil = _get_or_create_perfil(request.user)
    return JsonResponse({
        "username": request.user.username,
        "display_name": perfil.display_name,
        "avatar_url": perfil.avatar_url or "",
        "tipo": perfil.tipo_usuario,
    })
