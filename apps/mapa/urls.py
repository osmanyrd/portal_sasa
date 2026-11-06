from django.urls import path

from apps.mapa import views

app_name = "mapa"

urlpatterns = [
    path("datos/", views.mapa_datos, name="datos"),
]
