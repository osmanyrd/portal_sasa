from django.urls import path

from apps.surveys import views

app_name = "surveys"

urlpatterns = [
    path("", views.encuesta_list_view, name="list"),
    path("modal-data/", views.encuesta_modal_data, name="modal_data"),
    path("<int:encuesta_id>/votar/", views.vote_view, name="vote"),
    path("<int:encuesta_id>/autoguardar/", views.autosave_view, name="autosave"),
    path("<int:encuesta_id>/aceptar/", views.aceptar_encuesta, name="aceptar"),
    path("<int:encuesta_id>/estadisticas/", views.estadisticas_view, name="estadisticas"),
    path("<int:encuesta_id>/exportar-csv/", views.exportar_csv, name="exportar_csv"),
]
