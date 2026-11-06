"""
Chatbot RAG — Vistas de administración (dashboard y exportación CSV).

Se registran bajo /admin/chatbot/ usando `register_admin_urls`.
"""
from __future__ import annotations

import csv
import io

from django.db.models import Count
from django.http import HttpResponse
from django.utils import timezone
from django.shortcuts import render
from wagtail.admin.auth import require_admin_access

from apps.chatbot.models import (
    ConfiguracionChatbot,
    ConversacionChat,
    DocumentoConocimiento,
    FragmentoDocumento,
    LeadChatbot,
    MensajeChat,
    RegistroConversacion,
)


@require_admin_access
def dashboard(request):
    """Resumen de métricas del chatbot para el panel de Wagtail."""
    hoy = timezone.now().date()
    ayer = hoy - timezone.timedelta(days=1)

    cfg = ConfiguracionChatbot.obtener()

    total_consultas = RegistroConversacion.objects.count()
    consultas_hoy = RegistroConversacion.objects.filter(creado__date=hoy).count()
    consultas_ayer = RegistroConversacion.objects.filter(creado__date=ayer).count()
    respondidas = RegistroConversacion.objects.filter(respondido=True).count()
    no_respondidas = RegistroConversacion.objects.filter(respondido=False).count()
    feedback_up = RegistroConversacion.objects.filter(feedback="up").count()
    feedback_down = RegistroConversacion.objects.filter(feedback="down").count()

    mensajes_hoy = MensajeChat.objects.filter(timestamp__date=hoy).count()
    palabras_hoy = (
        MensajeChat.objects.filter(timestamp__date=hoy)
        .aggregate(tokens=Count("id"))
    )["tokens"] or 0

    conversaciones_ult = (
        ConversacionChat.objects.order_by("-iniciada_en")[:15]
        .annotate(n_mensajes=Count("mensajes"))
    )
    leads_pendientes = LeadChatbot.objects.filter(atendido=False).count()

    try:
        from apps.chatbot.embeddings import disponibilidad

        emb = disponibilidad(cfg)
    except Exception:
        emb = {"proveedor": cfg.proveedor_embeddings, "modelo": "?"}

    context = {
        "titulo": "Dashboard del chatbot IA",
        "cfg": cfg,
        "embeddings": emb,
        "stats": {
            "documentos": DocumentoConocimiento.objects.count(),
            "fragmentos": FragmentoDocumento.objects.count(),
            "conversaciones": ConversacionChat.objects.count(),
            "mensajes": MensajeChat.objects.count(),
            "leads": LeadChatbot.objects.count(),
            "leads_pendientes": leads_pendientes,
            "consultas": total_consultas,
            "hoy": consultas_hoy,
            "ayer": consultas_ayer,
            "respondidas": respondidas,
            "no_respondidas": no_respondidas,
            "feedback_up": feedback_up,
            "feedback_down": feedback_down,
            "conversion": round(respondidas / total_consultas * 100, 1) if total_consultas else 0.0,
            "tasa_util": round(feedback_up / (feedback_up + feedback_down) * 100, 1)
            if (feedback_up + feedback_down) else 0.0,
        },
        "conversaciones_ult": conversaciones_ult,
    }
    return render(request, "chatbot/dashboard.html", context)


@require_admin_access
def exportar_csv(request):
    """Exporta los últimos N registros de conversación a CSV."""
    limite = int(request.GET.get("n", 1000))
    respuesta = HttpResponse(content_type="text/csv; charset=utf-8")
    respuesta["Content-Disposition"] = 'attachment; filename="conversaciones_chatbot.csv"'
    respuesta.write("\ufeff")  # BOM UTF-8 para Excel

    campos = ["fecha", "nivel", "pregunta", "respuesta", "respondido", "puntuacion", "feedback"]
    escritor = csv.writer(respuesta)
    escritor.writerow(campos)
    escritor.writerow([
        "Fecha", "Nivel(1-5)", "Pregunta", "Respuesta",
        "Respondido", "Similitud", "Feedback",
    ])

    for reg in RegistroConversacion.objects.order_by("-creado")[:limite]:
        existe = (
            MensajeChat.objects.filter(
                conversacion__session_key=reg.session_key or "", rol="bot"
            ).exclude(calificacion__isnull=True).order_by("-timestamp").first()
        )
        nivel = existe.calificacion if existe else ""
        escritor.writerow([
            reg.creado.strftime("%Y-%m-%d %H:%M"),
            nivel,
            reg.pregunta,
            reg.respuesta.replace("\n", " "),
            "Sí" if reg.respondido else "No",
            reg.puntuacion_similitud,
            reg.feedback,
        ])
    return respuesta


@require_admin_access
def reingestar(request):
    """Acción rápida del panel: re-ingesta todos los documentos activos."""
    from apps.chatbot.ingesta import reingestar_todo

    resumen = reingestar_todo()
    return HttpResponse(
        f"Ingesta completada: {resumen['ok']} ingeridos, "
        f"{resumen['sin_contenido']} sin contenido util. "
        '<a href="../dashboard/">Volver al dashboard</a>'
    )