"""Context processor de la app de encuestas.

``encuestas_contexto`` inyecta en **todas** las plantillas del sitio las
variables que necesitan la campanita del navbar y el botón flotante cuando hay
encuestas pendientes por responder:

  * ``encuesta_pendiente``            : objeto Encuesta o None (la más reciente).
  * ``contador_encuestas_pendientes`` : int, cuántas encuestas hay pendientes.

Se apoya en ``apps.surveys.logica``, que a su vez cachea el cálculo por sesión
para no ir a la BD en cada petición.
"""
from apps.surveys.logica import contexto_encuestas


def encuestas_contexto(request):
    return contexto_encuestas(request)
