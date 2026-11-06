from django.urls import path

from apps.usuarios import views

urlpatterns = [
    path("registro/", views.registro_view, name="registro"),
    path("registro/empresa/", views.registro_juridico_view, name="registro_juridico"),
    path("api/verificar-cliente/", views.verificar_cliente_view, name="verificar_cliente"),
    path("activar/<str:token>/", views.activar_cuenta, name="activar_cuenta"),
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("perfil/", views.perfil_view, name="perfil"),
    path("perfil/empresa/", views.perfil_juridico_view, name="perfil_juridico"),
    path("api/token/", views.token_sistema_externo, name="token_sistema_externo"),
    path("api/avatar/", views.user_avatar_api, name="user_avatar_api"),
]
