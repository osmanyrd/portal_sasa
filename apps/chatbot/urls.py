from django.urls import path

from apps.chatbot.views import (
    consulta_chatbot,
    escalar_chatbot,
    feedback_chatbot,
    historial_chatbot,
    info_chatbot,
    limpiar_chatbot,
)

app_name = "chatbot"

urlpatterns = [
    path("consulta/", consulta_chatbot, name="consulta"),
    path("feedback/", feedback_chatbot, name="feedback"),
    path("escalar/", escalar_chatbot, name="escalar"),
    path("historial/", historial_chatbot, name="historial"),
    path("limpiar/", limpiar_chatbot, name="limpiar"),
    path("info/", info_chatbot, name="info"),
]