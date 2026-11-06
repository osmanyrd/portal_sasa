from django.urls import path

from apps.informaciones import views

app_name = "informaciones"

urlpatterns = [
    path("recientes/", views.informaciones_recientes_api, name="recientes"),
]
