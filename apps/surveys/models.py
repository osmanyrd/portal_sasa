"""
Modelos del sistema de encuestas avanzado (Servicios Automotores S.A).

- Encuesta: encuesta con control de fechas, modal, mensajes configurables,
  comportamiento de wizard (una pregunta por pantalla) y notificaciones.
- Pregunta: 16 tipos de pregunta interactiva (radio, multiple, estrellas,
  NPS, slider, emojis, si/no, ranking, texto, imagenes, fecha, hora, numero,
  pares, matriz, etc.).
- Opcion: opcion de respuesta (con imagen/emoji/color opcionales).
- Participacion: registro de aceptacion y finalizacion por sesion.
- RespuestaEncuesta: respuesta individual (flexible) por pregunta.
- Voto: modelo legacy conservado para no perder datos historicos; las
  respuestas nuevas se guardan siempre en RespuestaEncuesta.
"""
from datetime import timedelta

from django.db import models
from django.utils import timezone
from django.utils.html import format_html
from modelcluster.fields import ParentalKey
from modelcluster.models import ClusterableModel
from django.urls import reverse
from wagtail.admin.panels import FieldPanel, InlinePanel, MultiFieldPanel


# ── Tipos de pregunta ─────────────────────────────────────────
TIPOS_ESTRELLA = "estrellas"
TIPOS_NPS = "nps"
TIPOS_SLIDER = "slider"
TIPOS_EMOJIS = "emojis"
TIPOS_SINO = "sino"
TIPOS_RANKING = "ranking"
TIPOS_IMAGENES = "imagenes"
TIPOS_PARES = "pares"
TIPOS_MATRIZ = "matriz"

TIPOS_OPCIONES = {"simple", "multiple", "imagenes", "par"}
TIPOS_ESCALA = {TIPOS_ESTRELLA, TIPOS_NPS, TIPOS_EMOJIS}
TIPOS_CON_RANGO = {TIPOS_ESTRELLA, TIPOS_NPS, TIPOS_SLIDER, TIPOS_EMOJIS}
TIPOS_CON_OPCIONES = {"simple", "multiple", TIPOS_RANKING, TIPOS_IMAGENES, TIPOS_PARES}
TIPOS_TEXTO = {"texto_corto", "texto_largo"}


class Encuesta(ClusterableModel):
    """Encuesta con publicacion programada, modal de invitacion, wizard por
    pantalla y mensajes configurables."""

    TIPO_ENCUESTA_CHOICES = [
        ("campana", "De campana (temporal)"),
        ("fija", "Fija (permanente)"),
    ]

    tipo_encuesta = models.CharField(
        max_length=10,
        choices=TIPO_ENCUESTA_CHOICES,
        default="campana",
        verbose_name="Tipo de encuesta",
        help_text=(
            "De campana: temporal, se responde una sola vez y caduca en el "
            "rango de fechas. Fija: permanente, puede responderse varias "
            "veces y nunca caduca (mientras este activa)."
        ),
        db_index=True,
    )
    nombre = models.CharField(
        max_length=200,
        help_text="Nombre interno de la encuesta (no se muestra al publico).",
    )
    titulo_publico = models.CharField(
        max_length=200,
        help_text="Titulo que veran los visitantes.",
    )
    descripcion = models.TextField(
        blank=True,
        default="",
        help_text="Descripcion breve de la encuesta (opcional).",
    )
    fecha_inicio = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Si se establece, la encuesta solo estara vigente a partir de esta fecha.",
        db_index=True,
    )
    fecha_fin = models.DateTimeField(
        null=True,
        blank=True,
        help_text=(
            "Si se establece, la encuesta cerrara automaticamente en esta "
            "fecha. Solo aplica a encuestas de campana (las fijas no caducan)."
        ),
    )
    activa = models.BooleanField(
        default=False,
        help_text="Activa para mostrar la encuesta a los visitantes.",
        db_index=True,
    )
    dias_espera_respuesta = models.PositiveIntegerField(
        default=0,
        verbose_name="Espera entre respuestas (dias)",
        help_text=(
            "Solo aplica a encuestas fijas. Numero de dias que el usuario "
            "debe esperar desde su ultima participacion para poder responder "
            "de nuevo. 0 = puede responder inmediatamente."
        ),
    )
    mostrar_modal = models.BooleanField(
        default=True,
        help_text="Si esta activo, se muestra un modal de invitacion al cargar la pagina.",
        db_index=True,
    )
    mostrar_modal_primera_visita = models.BooleanField(
        default=True,
        help_text=(
            "Si esta activo, el modal de invitacion aparecera automaticamente "
            "al cargar la pagina. Solo aplica a encuestas de campana."
        ),
        verbose_name="Mostrar modal en la primera visita",
        db_index=True,
    )
    mensaje_agradecimiento = models.TextField(
        default="!Gracias por participar!",
        help_text="Mensaje que se muestra al completar la encuesta.",
    )
    dias_supresion_modal = models.PositiveIntegerField(
        default=30,
        help_text="Dias que el modal no volvera a aparecer despues de que el usuario lo cierre.",
    )

    # ── Comportamiento del formulario ─────────────────────────
    una_pregunta_por_pantalla = models.BooleanField(
        default=True,
        verbose_name="Una pregunta por pantalla",
        help_text="Si esta desactivado, todas las preguntas se muestran juntas en la misma pagina.",
    )
    permitir_volver_atras = models.BooleanField(
        default=True,
        verbose_name="Permitir volver atras",
        help_text="Permite al participante volver a preguntas anteriores y editar sus respuestas.",
    )
    autoguardar = models.BooleanField(
        default=True,
        verbose_name="Autoguardado parcial",
        help_text="Guarda las respuestas parciales en la sesion para no perder progreso.",
    )

    # ── Notificaciones ─────────────────────────────────────────
    notificar_admin = models.BooleanField(
        default=False,
        verbose_name="Notificar por correo al registrar respuestas",
        help_text="Envia un correo a los destinatarios indicados abajo al completarse una respuesta.",
    )
    correo_admin = models.CharField(
        max_length=500,
        blank=True,
        default="",
        verbose_name="Correos de notificacion",
        help_text="Direcciones separadas por comas. Vacío usa el DEFAULT_FROM_EMAIL.",
    )
    preguntar_correo = models.BooleanField(
        default=False,
        verbose_name="Preguntar correo del participante",
        help_text="Anade un campo opcional de correo electronico al formulario.",
    )
    notificar_participante = models.BooleanField(
        default=False,
        verbose_name="Confirmar participacion por correo",
        help_text="Envia una confirmacion al participante que dejó su correo (si activaste 'Preguntar correo').",
    )

    panels = [
        MultiFieldPanel(
            [
                FieldPanel("tipo_encuesta"),
                FieldPanel("nombre"),
                FieldPanel("titulo_publico"),
                FieldPanel("descripcion"),
            ],
            heading="Informacion",
        ),
        MultiFieldPanel(
            [
                FieldPanel("activa"),
                FieldPanel("fecha_inicio"),
                FieldPanel("fecha_fin"),
                FieldPanel("dias_espera_respuesta"),
            ],
            heading="Publicacion y vigencia",
        ),
        MultiFieldPanel(
            [
                FieldPanel("mostrar_modal"),
                FieldPanel("mostrar_modal_primera_visita"),
                FieldPanel("dias_supresion_modal"),
                FieldPanel("mensaje_agradecimiento"),
            ],
            heading="Modal y mensajes",
        ),
        MultiFieldPanel(
            [
                FieldPanel("una_pregunta_por_pantalla"),
                FieldPanel("permitir_volver_atras"),
                FieldPanel("autoguardar"),
            ],
            heading="Experiencia de respuesta",
        ),
        MultiFieldPanel(
            [
                FieldPanel("notificar_admin"),
                FieldPanel("correo_admin"),
                FieldPanel("preguntar_correo"),
                FieldPanel("notificar_participante"),
            ],
            heading="Notificaciones",
        ),
        InlinePanel("preguntas", label="Preguntas"),
    ]

    class Meta:
        ordering = ["-fecha_inicio"]
        verbose_name = "Encuesta"
        verbose_name_plural = "Encuestas"

    def __str__(self):
        return self.nombre

    def tipo_display(self):
        """Etiqueta legible del tipo de encuesta (fija / campana)."""
        return self.get_tipo_encuesta_display()

    tipo_display.short_description = "Tipo"

    def exportar_csv_link(self):
        """Enlace del botón 'CSV' para exportar las respuestas."""
        url = reverse("surveys:exportar_csv", args=[self.pk])
        return format_html(
            '<a class="button button-secondary button-small" href="{}" title="Exportar respuestas en CSV">'
            '<i class="icon icon-download" aria-hidden="true"></i> CSV</a>',
            url,
        )

    exportar_csv_link.short_description = "Exportar"

    def es_campana(self):
        """True si la encuesta es de campana (temporal)."""
        return self.tipo_encuesta == "campana"

    def es_fija(self):
        """True si la encuesta es fija (permanente)."""
        return self.tipo_encuesta == "fija"

    def esta_vigente(self):
        """Verifica si la encuesta esta vigente segun activa y fechas."""
        if not self.activa:
            return False
        ahora = timezone.now()
        if self.fecha_inicio and ahora < self.fecha_inicio:
            return False
        if self.es_campana() and self.fecha_fin and ahora > self.fecha_fin:
            return False
        return True

    def puede_volver_a_responder(self, session_key):
        """¿Esta sesion puede responder de nuevo una encuesta fija?"""
        if not session_key:
            return True
        ultima = (
            Participacion.objects.filter(
                encuesta=self,
                session_key=session_key,
                completada=True,
            )
            .order_by("-fecha_completada")
            .first()
        )
        if ultima is None:
            return True
        if self.dias_espera_respuesta <= 0:
            return True
        limite = ultima.fecha_completada + timedelta(days=self.dias_espera_respuesta)
        return timezone.now() >= limite

    def ultima_participacion_completada(self, session_key):
        """Ultima participacion completada de esta sesion (o ``None``)."""
        if not session_key:
            return None
        return (
            Participacion.objects.filter(
                encuesta=self,
                session_key=session_key,
                completada=True,
            )
            .order_by("-fecha_completada")
            .first()
        )

    def es_pendiente_para(self, session_key):
        """¿Esta encuesta esta pendiente de respuesta para esta sesion?"""
        if not self.esta_vigente():
            return False
        if not session_key:
            return True
        if self.es_fija():
            return self.puede_volver_a_responder(session_key)
        return not Participacion.objects.filter(
            encuesta=self,
            session_key=session_key,
            completada=True,
        ).exists()

    def url_votar(self):
        """URL del formulario de votacion de esta encuesta."""
        return reverse("surveys:vote", args=[self.pk])

    def preguntas_ordenadas(self):
        """Preguntas ordenadas para renderizar el formulario."""
        return self.preguntas.all().order_by("orden", "pk")

    def total_participaciones(self):
        """Retorna el total de participaciones completadas."""
        return self.participaciones.filter(completada=True).count()

    @staticmethod
    def _opciones_por_pregunta():
        """Mapa de opciones agrupadas por pregunta (ayuda a evitar N+1)."""
        opciones = {}
        for opc in Opcion.objects.select_related("imagen").order_by("orden", "pk"):
            opciones.setdefault(opc.pregunta_id, []).append(opc)
        return opciones

    def estadisticas(self):
        """Calcula estadisticas por pregunta leyendo RespuestaEncuesta.

        Retorna lista de dicts:
            {
              "pregunta": obj, "tipo": str, "texto": str,
              "total": int,            # respuestas completadas
              "promedio": float|None, "mediana": float|None,
              "distribucion": [ {label, valor, emoji?, pct} ... ],
              "filas": [ {fila, promedio} ... ]  # matriz
            }
        """
        from django.db.models import Avg, Count
        from apps.surveys.models import Opcion, RespuestaEncuesta

        opciones_map = Encuesta._opciones_por_pregunta()
        filas = []
        for pregunta in self.preguntas_ordenadas():
            respuestas = RespuestaEncuesta.objects.filter(
                participacion__encuesta=self,
                participacion__completada=True,
                pregunta=pregunta,
            )
            total = respuestas.count()
            item = {
                "pregunta": pregunta,
                "tipo": pregunta.tipo,
                "texto": pregunta.texto,
                "total": total,
                "promedio": None,
                "mediana": None,
                "distribucion": [],
                "filas": [],
            }

            if pregunta.tipo in TIPOS_ESCALA | {TIPOS_SLIDER, "numero"}:
                numeros = [
                    r.valor_numero
                    for r in respuestas.filter(valor_numero__isnull=False)
                    if r.valor_numero is not None
                ]
                item["promedio"] = (
                    round(sum(numeros) / len(numeros), 2) if numeros else None
                )
                cant = len(numeros)
                if cant:
                    ordenados = sorted(numeros)
                    mid = cant // 2
                    item["mediana"] = (
                        ordenados[mid]
                        if cant % 2
                        else (ordenados[mid - 1] + ordenados[mid]) / 2
                    )
                distribucion = {}
                for num in numeros:
                    distribucion[float(num)] = distribucion.get(float(num), 0) + 1
                for valor in sorted(distribucion):
                    pct = (distribucion[valor] / cant * 100) if cant else 0
                    emoji = Pregunta.EMOJIS_VALORES.get(int(valor), "") if pregunta.tipo == TIPOS_EMOJIS else ""
                    item["distribucion"].append(
                        {"label": str(valor), "valor": int(valor), "votos": distribucion[valor],
                         "porcentaje": round(pct, 1), "emoji": emoji}
                    )

            elif pregunta.tipo == TIPOS_SINO:
                conteo = {True: 0, False: 0}
                for r in respuestas.filter(valor_booleano__isnull=False):
                    conteo[bool(r.valor_booleano)] = conteo.get(bool(r.valor_booleano), 0) + 1
                total_bool = conteo[True] + conteo[False]
                item["distribucion"] = [
                    {"label": "Si", "valor": conteo[True],
                     "porcentaje": round(conteo[True] / total_bool * 100, 1) if total_bool else 0, "emoji": ""},
                    {"label": "No", "valor": conteo[False],
                     "porcentaje": round(conteo[False] / total_bool * 100, 1) if total_bool else 0, "emoji": ""},
                ]

            elif pregunta.tipo == "fecha":
                fechas = [r.valor_fecha.date() for r in respuestas.filter(valor_fecha__isnull=False)]
                item["fechas"] = fechas

            elif pregunta.tipo == "hora":
                horas = [r.valor_fecha.time() for r in respuestas.filter(valor_fecha__isnull=False)]
                item["horas"] = horas

            elif pregunta.tipo in TIPOS_TEXTO:
                item["textos"] = [r.valor_texto for r in respuestas.filter(valor_texto__gt="")]

            elif pregunta.tipo in TIPOS_OPCIONES:
                opciones = opciones_map.get(pregunta.pk, [])
                conteo_ops = {}
                for r in respuestas:
                    for oid in (r.valor_json if isinstance(r.valor_json, list) else []):
                        conteo_ops[int(oid)] = conteo_ops.get(int(oid), 0) + 1
                for opc in opciones:
                    cant = conteo_ops.get(opc.pk, 0)
                    pct = (cant / total * 100) if total else 0
                    item["distribucion"].append({
                        "label": opc.texto, "opcion_id": opc.pk,
                        "imagen": opc.imagen, "emoji": opc.emoji,
                        "color": opc.color, "votos": cant,
                        "porcentaje": round(pct, 1),
                    })

            elif pregunta.tipo == TIPOS_RANKING:
                opciones = opciones_map.get(pregunta.pk, [])
                posiciones = {o.pk: {"suma": 0, "n": 0} for o in opciones}
                for r in respuestas:
                    orden = r.valor_json if isinstance(r.valor_json, list) else []
                    for pos, oid in enumerate(orden):
                        if int(oid) in posiciones:
                            posiciones[int(oid)]["suma"] += pos + 1
                            posiciones[int(oid)]["n"] += 1
                item["distribucion"] = []
                for opc in opciones:
                    d = posiciones.get(opc.pk, {"suma": 0, "n": 0})
                    promedio_pos = (d["suma"] / d["n"]) if d["n"] else None
                    item["distribucion"].append({
                        "label": opc.texto, "opcion_id": opc.pk, "emoji": opc.emoji,
                        "votos": d["n"], "promedio_posicion": promedio_pos,
                        "porcentaje": round(d["n"] / total * 100, 1) if total else 0,
                    })

            elif pregunta.tipo == TIPOS_MATRIZ:
                filas_labels = pregunta.filas or []
                sums = {row: 0 for row in filas_labels}
                counts = {row: 0 for row in filas_labels}
                for r in respuestas:
                    data = r.valor_json if isinstance(r.valor_json, dict) else {}
                    for row, val in data.items():
                        if row in sums and val is not None:
                            try:
                                val = float(val)
                            except (TypeError, ValueError):
                                continue
                            sums[row] += val
                            counts[row] += 1
                item["filas"] = [
                    {"fila": row, "promedio": round(sums[row] / counts[row], 2) if counts[row] else None}
                    for row in filas_labels
                ]

            filas.append(item)

        return filas

    def resultados(self):
        """Compatibilidad: delegacion en estadisticas() para plantillas viejas."""
        return self.estadisticas()


class Pregunta(ClusterableModel):
    """Una pregunta dentro de una encuesta (16 tipos interactivos)."""

    TIPO_CHOICES = [
        ("simple", "Seleccion unica (radio)"),
        ("multiple", "Seleccion multiple (checkbox)"),
        (TIPOS_ESTRELLA, "Escala de estrellas (1 a 5)"),
        (TIPOS_NPS, "Escala numerica NPS (0 a 10)"),
        (TIPOS_SLIDER, "Slider (rango configurable)"),
        (TIPOS_EMOJIS, "Emojis (1 a 5)"),
        (TIPOS_SINO, "Si / No"),
        (TIPOS_RANKING, "Ranking (arrastrar y ordenar)"),
        ("texto_corto", "Texto corto (max 200 caracteres)"),
        ("texto_largo", "Texto largo (párrafo, max 2000)"),
        (TIPOS_IMAGENES, "Seleccion con imagenes"),
        ("fecha", "Fecha"),
        ("hora", "Hora"),
        ("numero", "Numero / Codigo de cliente"),
        ("par", "Clasificacion de pares (elegir uno)"),
        (TIPOS_MATRIZ, "Matriz de escala (filas x escala)"),
    ]

    # Emoji por valor numerico (para la escala de emojis 1..5)
    EMOJIS_VALORES = {
        1: "😡",
        2: "😕",
        3: "😐",
        4: "🙂",
        5: "😍",
    }
    VALORES_EMOJIS = {v: k for k, v in EMOJIS_VALORES.items()}

    encuesta = ParentalKey(
        Encuesta,
        on_delete=models.CASCADE,
        related_name="preguntas",
    )
    texto = models.CharField(max_length=500, verbose_name="Pregunta")
    tipo = models.CharField(
        max_length=20,
        choices=TIPO_CHOICES,
        default="simple",
        verbose_name="Tipo de pregunta",
    )
    ayuda = models.CharField(
        max_length=500,
        blank=True,
        default="",
        verbose_name="Ayuda / texto de apoyo",
        help_text="Texto pequeno que se muestra bajo la pregunta (opcional).",
    )
    requerida = models.BooleanField(
        default=True,
        verbose_name="Obligatoria",
        help_text="Si esta desactivada, el participante puede avanzar sin responder.",
    )
    orden = models.IntegerField(default=0)

    # Rango de escalas / slider
    min_valor = models.IntegerField(
        null=True, blank=True, verbose_name="Valor minimo",
        help_text="Usado por slider y numero. Ej: 0",
    )
    max_valor = models.IntegerField(
        null=True, blank=True, verbose_name="Valor maximo",
        help_text="Usado por slider y numero. Ej: 100",
    )
    paso = models.IntegerField(
        default=1, verbose_name="Paso",
        help_text="Incremento del slider o del numero. Ej: 5",
    )
    etiqueta_min = models.CharField(
        max_length=120, blank=True, default="",
        verbose_name="Etiqueta del valor minimo",
        help_text="Texto del extremo izquierdo. Ej: 'Nada satisfecho'.",
    )
    etiqueta_max = models.CharField(
        max_length=120, blank=True, default="",
        verbose_name="Etiqueta del valor maximo",
        help_text="Texto del extremo derecho. Ej: 'Muy satisfecho'.",
    )
    etiqueta_izq = models.CharField(
        max_length=120, blank=True, default="",
        verbose_name="Etiqueta izquierda (pares)",
        help_text="Para 'Clasificacion de pares': etiqueta de la tarjeta izquierda.",
    )
    etiqueta_der = models.CharField(
        max_length=120, blank=True, default="",
        verbose_name="Etiqueta derecha (pares)",
        help_text="Para 'Clasificacion de pares': etiqueta de la tarjeta derecha.",
    )
    filas = models.JSONField(
        default=list, blank=True, verbose_name="Filas de la matriz",
        help_text="Lista JSON con los nombres de las filas. Ej: ['Atencion', 'Precio', 'Rapidez']",
    )

    panels = [
        FieldPanel("texto"),
        FieldPanel("tipo"),
        FieldPanel("ayuda"),
        FieldPanel("requerida"),
        FieldPanel("orden"),
        MultiFieldPanel(
            [
                FieldPanel("min_valor"),
                FieldPanel("max_valor"),
                FieldPanel("paso"),
                FieldPanel("etiqueta_min"),
                FieldPanel("etiqueta_max"),
            ],
            heading="Escala / Slider",
            classname="pregunta-params pregunta-params-escala",
        ),
        MultiFieldPanel(
            [
                FieldPanel("etiqueta_izq"),
                FieldPanel("etiqueta_der"),
            ],
            heading="Pares (tarjetas izquierda / derecha)",
            classname="pregunta-params pregunta-params-pares",
        ),
        MultiFieldPanel(
            [
                FieldPanel("filas"),
            ],
            heading="Matriz",
            classname="pregunta-params pregunta-params-matriz",
        ),
        MultiFieldPanel(
            [InlinePanel("opciones", label="Opciones")],
            heading="Opciones",
            classname="pregunta-params pregunta-params-opciones",
        ),
    ]

    class Meta:
        ordering = ["orden", "pk"]
        verbose_name = "Pregunta"
        verbose_name_plural = "Preguntas"

    def __str__(self):
        return f"{self.encuesta.nombre} - {self.texto[:60]}"

    def necesita_opciones(self):
        """True si el tipo requiere opciones definidas en el panel."""
        return self.tipo in TIPOS_CON_OPCIONES

    def necesita_escala(self):
        """True si el tipo muestra los campos de escala/slider."""
        return self.tipo in TIPOS_CON_RANGO or self.tipo == TIPOS_SLIDER

    def necesita_pares(self):
        return self.tipo == "par"

    def necesita_matriz(self):
        return self.tipo == TIPOS_MATRIZ

    def tipo_display(self):
        return self.get_tipo_display()

    tipo_display.short_description = "Tipo"


class Opcion(models.Model):
    """Una opcion de respuesta dentro de una pregunta interactiva."""

    pregunta = ParentalKey(
        Pregunta,
        on_delete=models.CASCADE,
        related_name="opciones",
    )
    texto = models.CharField(max_length=300, verbose_name="Texto")
    imagen = models.ForeignKey(
        "wagtailimages.Image",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        verbose_name="Imagen (opcional)",
        help_text="Usado por 'Seleccion con imagenes'.",
    )
    emoji = models.CharField(
        max_length=16,
        blank=True,
        default="",
        verbose_name="Emoji (opcional)",
    )
    color = models.CharField(
        max_length=9,
        blank=True,
        default="",
        verbose_name="Color (opcional)",
        help_text="Color hex (ej: #E63946) para personalizar la opcion.",
    )
    orden = models.PositiveIntegerField(default=0)

    panels = [
        FieldPanel("texto"),
        FieldPanel("imagen"),
        FieldPanel("emoji"),
        FieldPanel("color"),
        FieldPanel("orden"),
    ]

    class Meta:
        ordering = ["orden", "pk"]
        verbose_name = "Opcion"
        verbose_name_plural = "Opciones"

    def __str__(self):
        return f"{self.pregunta.texto[:40]} - {self.texto}"


class Participacion(models.Model):
    """Registra la aceptacion y finalizacion de un usuario en una encuesta."""

    encuesta = models.ForeignKey(
        Encuesta,
        on_delete=models.CASCADE,
        related_name="participaciones",
    )
    session_key = models.CharField(max_length=64, db_index=True)
    correo_participante = models.EmailField(
        blank=True, null=True,
        verbose_name="Correo del participante",
        help_text="Correo opcional dejado por el participante (si se configuro 'Preguntar correo').",
    )
    fecha_aceptacion = models.DateTimeField(auto_now_add=True)
    completada = models.BooleanField(default=False)
    fecha_completada = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-fecha_aceptacion"]
        verbose_name = "Participacion"
        verbose_name_plural = "Participaciones"

    def __str__(self):
        estado = "completada" if self.completada else "pendiente"
        return f"Participacion {estado} - {self.encuesta.nombre}"


class RespuestaEncuesta(models.Model):
    """Respuesta flexible para una pregunta de la encuesta.

    Segun el tipo de pregunta se completa uno o mas campos:
      - Seleccion unica / imagenes / pares: opcion + valor_json=[opcion_id].
      - Seleccion multiple: valor_json=[opcion_id, ...].
      - Estrellas / NPS / slider / emojis / numero: valor_numero.
      - Si / No: valor_booleano.
      - Texto corto / largo: valor_texto.
      - Fecha / hora: valor_fecha.
      - Ranking: valor_json=[opcion_id, ...] en orden elegido.
      - Matriz: valor_json={"fila": valor_numero, ...}.
    """

    participacion = models.ForeignKey(
        Participacion,
        on_delete=models.CASCADE,
        related_name="respuestas",
    )
    pregunta = models.ForeignKey(
        Pregunta,
        on_delete=models.CASCADE,
        related_name="respuestas",
    )
    opcion = models.ForeignKey(
        Opcion,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="respuestas",
    )
    valor_texto = models.TextField(
        blank=True, default="",
        verbose_name="Valor de texto",
    )
    valor_numero = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Valor numerico",
    )
    valor_booleano = models.BooleanField(
        null=True, blank=True,
        verbose_name="Valor si/no",
    )
    valor_fecha = models.DateTimeField(
        null=True, blank=True,
        verbose_name="Valor fecha/hora",
    )
    valor_json = models.JSONField(
        default=list, blank=True,
        verbose_name="Valor JSON",
    )
    fecha_respuesta = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["pregunta__orden", "id"]
        verbose_name = "Respuesta"
        verbose_name_plural = "Respuestas"

    @property
    def valor_mostrable(self):
        """Valor legible para CSV / estadisticas segun el tipo de pregunta."""
        pregunta = self.pregunta
        if pregunta.tipo in TIPOS_ESCALA | {TIPOS_SLIDER, "numero"}:
            return self.valor_numero
        if pregunta.tipo == TIPOS_SINO:
            return "Si" if self.valor_booleano else "No"
        if pregunta.tipo == "fecha":
            return self.valor_fecha.date().isoformat() if self.valor_fecha else ""
        if pregunta.tipo == "hora":
            return self.valor_fecha.strftime("%H:%M") if self.valor_fecha else ""
        if pregunta.tipo in TIPOS_TEXTO:
            return self.valor_texto
        if pregunta.tipo == TIPOS_MATRIZ:
            if isinstance(self.valor_json, dict):
                return "; ".join(f"{k}: {v}" for k, v in self.valor_json.items())
            return ""
        if pregunta.tipo == TIPOS_RANKING:
            if isinstance(self.valor_json, list):
                textos = Opcion.objects.filter(id__in=self.valor_json).values_list("texto", flat=True)
                return ", ".join(str(t) for t in textos)
            return ""
        # tipado por opciones
        if self.opcion_id:
            return self.opcion.texto if self.opcion else f"Opcion {self.opcion_id}"
        if isinstance(self.valor_json, list):
            textos = Opcion.objects.filter(id__in=self.valor_json).values_list("texto", flat=True)
            return ", ".join(str(t) for t in textos)
        return ""

    def __str__(self):
        return f"{self.participacion_id} - {self.pregunta.texto[:40]}: {self.valor_mostrable}"


class Voto(models.Model):
    """Modelo legacy (histórico). Las respuestas nuevas usan RespuestaEncuesta.

    Se conserva la tabla para no perder el historico; el flujo nuevo no escribe aqui.
    """

    participacion = models.ForeignKey(
        Participacion,
        on_delete=models.CASCADE,
        related_name="votos",
    )
    pregunta = models.ForeignKey(
        Pregunta,
        on_delete=models.CASCADE,
    )
    opcion = models.ForeignKey(
        Opcion,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )
    fecha_voto = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-fecha_voto"]
        verbose_name = "Voto"
        verbose_name_plural = "Votos"

    def __str__(self):
        return f"Voto: {self.pregunta.texto[:30]} - {self.opcion.texto if self.opcion else 'N/A'}"