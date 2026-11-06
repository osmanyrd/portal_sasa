"""Modelos de la sección "Informaciones" (Servicios Automotores S.A).

* ``InformacionesIndexPage`` : página contenedora / listado público.
* ``Informacion``            : comunicado / noticia / aviso / alerta individual.

Las informaciones "recientes" (las que alimentan la campana del navbar y el
cartel/toast) se calculan por la lógica de :mod:`apps.informaciones.notificaciones`.
"""

from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django import forms
from django.db import models
from django.db.models import Q
from django.utils import timezone
from wagtail.admin.panels import FieldPanel, HelpPanel, MultiFieldPanel
from wagtail.fields import RichTextField
from wagtail.models import Page
from wagtail.search import index



# ---------------------------------------------------------------------------
# Página índice (contenedor / listado principal)
# ---------------------------------------------------------------------------
class InformacionesIndexPage(Page):
    """
    Contenedor principal de informaciones (solo una instancia permitida).

    Sirve el listado público de :class:`Informacion` activas, con filtros por
    tipo y paginación. También permite afinar la ventana de "recientes".
    """

    introduccion = RichTextField(blank=True, verbose_name="Introducción")

    # Ventana (en días) para considerar una información "reciente" a nivel de
    # esta página. Si se deja en 0 se usa ``settings.INFO_DIAS_RECIENTES``.
    dias_recientes = models.PositiveIntegerField(
        default=5,
        verbose_name="Días para informaciones recientes",
        help_text="Cuántos días hacia atrás se consideran 'recientes' (campana / cartel).",
    )

    content_panels = Page.content_panels + [
        FieldPanel("introduccion"),
        FieldPanel("dias_recientes"),
    ]

    subpage_types = ["informaciones.Informacion"]
    parent_page_types = [
        "home.HomePage",
        "core.GenericPage",
        "automotive.AutomotivePage",
    ]
    max_count = 1  # solo una instancia
    template = "informaciones/informaciones_index_page.html"

    INFO_POR_PAGINA = 15

    class Meta:
        verbose_name = "Informaciones"
        verbose_name_plural = "Informaciones"

    def __str__(self):
        return self.title

    # --- Ventana efectiva para "recientes" ---
    @property
    def ventana_dias(self):
        if self.dias_recientes:
            return self.dias_recientes
        from apps.informaciones import notificaciones
        return notificaciones.dias_recientes()

    def recientes(self, limit=None):
        """Informaciones recientes según la ventana de esta página."""
        from apps.informaciones import notificaciones
        return notificaciones.informaciones_recientes(
            dias=self.ventana_dias, limit=limit
        )

    # --- Página pública (listado) ---
    def get_context(self, request, *args, **kwargs):
        context = super().get_context(request, *args, **kwargs)

        slug_tipo = (request.GET.get("tipo") or "").strip()
        query = Informacion.objects.child_of(self).filter(activo=True, live=True)
        query = query.select_related("imagen").order_by("-fecha_publicacion")

        tipos_validos = {c for c, _ in Informacion.TIPO_CHOICES}
        if slug_tipo in tipos_validos:
            query = query.filter(tipo=slug_tipo)

        paginator = Paginator(query, self.INFO_POR_PAGINA)
        pagina = request.GET.get("page")
        try:
            items = paginator.page(pagina)
        except PageNotAnInteger:
            items = paginator.page(1)
        except EmptyPage:
            items = paginator.page(paginator.num_pages)

        context.update(
            {
                "informaciones": items,
                "tipo_activo": slug_tipo,
                "tipos_disponibles": Informacion.TIPO_CHOICES,
            }
        )
        return context


# ---------------------------------------------------------------------------
# ContenidoPublicable (base abstracta)
# ...
# Definición de etiquetas / filas de la portada en Producto, Novedad e Información.
# ---------------------------------------------------------------------------
class ContenidoPublicable(models.Model):
    """
    Base abstracta común para contenidos publicables (novedades e informaciones).

    Agrupa los campos y utilidades compartidas: título (largo/corto), resumen,
    contenido, imagen, tipo/subcategoría, fechas de publicación/expiración, y
    los flags de presentación (destacado, activo, orden).

    Las subclases definen ``TIPO_CHOICES`` (los tipos propios de su módulo) y
    redeclaran el campo ``tipo`` para elegir su subcategoría. La categoría
    general (``novedad`` / ``informacion``) se deriva de la clase del modelo.
    """

    # Sobrescrito por cada subclase. Requerido para declarar ``tipo``.
    TIPO_CHOICES = []

    # Identificador de columna/categoría ('novedad' | 'informacion').
    CATEGORIA = "informacion"

    CAMPANA_LIMITE = 8  # máx. de ítems recientes en la campana / cartel

    titulo = models.CharField(
        max_length=255,
        verbose_name="Título largo",
        help_text="Se muestra en la página de detalle. Si se deja vacío se usa el título de la página.",
        blank=True,
    )
    titulo_corto = models.CharField(
        max_length=160,
        blank=True,
        verbose_name="Título corto",
        help_text="Este texto aparecerá en las notificaciones del navbar.",
    )
    resumen = models.CharField(
        max_length=200,
        blank=True,
        verbose_name="Resumen",
        help_text="Texto corto para las tarjetas de la portada y el listado.",
    )
    contenido = RichTextField(verbose_name="Contenido")
    imagen = models.ForeignKey(
        "wagtailimages.Image",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        verbose_name="Imagen",
    )
    tipo = models.CharField(
        max_length=20,
        choices=TIPO_CHOICES,
        default="",
        verbose_name="Tipo / subcategoría",
        db_index=True,
    )
    fecha_publicacion = models.DateTimeField(
        default=timezone.now,
        verbose_name="Fecha de publicación",
        help_text="Usada para ordenar y para decidir si es 'reciente'.",
        db_index=True,
    )
    fecha_expiracion = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Fecha de expiración",
        help_text="Si la dejas vacía, el contenido no expira.",
        db_index=True,
    )
    destacado = models.BooleanField(
        default=False,
        verbose_name="Destacado",
        help_text="Si está marcado aparece en la sección de la portada (máx. 4 por columna).",
    )
    activo = models.BooleanField(
        default=True,
        verbose_name="Activo",
        help_text="Si lo quitas, no se mostrará en el listado ni en las notificaciones.",
        db_index=True,
    )
    orden = models.IntegerField(
        default=0,
        verbose_name="Orden",
        help_text="Menor número = aparece primero. Se aplica antes que la fecha.",
    )
    enlace_externo = models.URLField(
        null=True,
        blank=True,
        verbose_name="Enlace externo",
        help_text="Si lo completas, el botón 'Ver' apunta aquí en vez del detalle.",
    )

    # Pestañas del editor, compartidas por las subclases.
    edit_handler_tabs = [
        MultiFieldPanel(
            [
                FieldPanel("titulo"),
                FieldPanel("title"),
                FieldPanel("titulo_corto"),
                FieldPanel("resumen"),
                FieldPanel("contenido"),
                FieldPanel("enlace_externo"),
                FieldPanel("tipo"),
            ],
            heading="Contenido",
        ),
        MultiFieldPanel(
            [
                FieldPanel("fecha_publicacion"),
                FieldPanel("fecha_expiracion"),
                FieldPanel("destacado"),
                FieldPanel("activo"),
                FieldPanel("orden"),
            ],
            heading="Publicación",
        ),
        MultiFieldPanel(
            [FieldPanel("imagen")],
            heading="Imagen",
        ),
    ]

    search_fields = [
        index.SearchField("titulo"),
        index.SearchField("titulo_corto"),
        index.SearchField("resumen"),
        index.SearchField("contenido"),
        index.FilterField("tipo"),
        index.FilterField("destacado"),
        index.FilterField("activo"),
        index.FilterField("fecha_publicacion"),
    ]

    class Meta:
        abstract = True

    # --- Utilidades de presentación ---
    @property
    def nombre_tipo(self):
        return dict(self.TIPO_CHOICES).get(self.tipo, self.tipo)

    @property
    def categoria(self):
        """Columna de la portada: 'novedad' o 'informacion'."""
        return self.CATEGORIA

    @property
    def titulo_efectivo(self):
        """Título preferido: el largo, si existe, o el de la página."""
        return self.titulo or self.title

    @property
    def nombre_corto(self):
        """Texto para notificaciones: preferimos el título corto."""
        return self.titulo_corto or self.titulo_efectivo

    def etiqueta_tipo(self):
        """Clase de icono Bootstrap según el tipo (sobrescrita por subclase)."""
        return "bi-info-circle-fill"

    @property
    def es_reciente(self):
        """¿Cumple todas las reglas de contenido 'reciente'?"""
        ahora = timezone.now()
        return self._es_reciente_con(ahora)

    def _es_reciente_con(self, ahora):
        if not self.activo or not self.live:
            return False
        desde = ahora - timezone.timedelta(days=self._dias_ventana())
        if self.fecha_publicacion < desde:
            return False
        if self.fecha_expiracion and self.fecha_expiracion <= ahora:
            return False
        return True

    def _dias_ventana(self):
        """Ventana de días desde el padre (si es índice) o desde settings."""
        try:
            padre = self.get_parent().specific
            indice = getattr(self, "INDEX_CLASS", None)
            if indice and isinstance(padre, indice) and padre.dias_recientes:
                return padre.dias_recientes
        except Exception:
            pass
        from apps.informaciones import notificaciones
        return notificaciones.dias_recientes()

    @classmethod
    def publicables(cls):
        """Contenido activo y publicado, ordenado por orden y fecha."""
        return cls.objects.filter(
            activo=True, live=True
        ).order_by("orden", "-fecha_publicacion")

    @classmethod
    def destacados(cls, limite=None):
        """Contenido activo, publicado y marcado como destacado."""
        qs = cls.publicables().filter(destacado=True)
        if limite:
            qs = qs[:limite]
        return qs

    @classmethod
    def recientes_qs(cls, ahora=None, dias=None):
        """QuerySet de contenidos recientes (reutilizado por notificaciones)."""
        from apps.informaciones import notificaciones

        if dias is None:
            dias = notificaciones.dias_recientes()
        now = ahora or timezone.now()
        desde = now - timezone.timedelta(days=dias)
        return (
            cls.publicables()
            .filter(fecha_publicacion__gte=desde)
            .filter(Q(fecha_expiracion__isnull=True) | Q(fecha_expiracion__gt=now))
        )

    def save(self, *args, **kwargs):
        """Autopublica la página si es nueva y está activa, al crearla
        programáticamente (el editor de Wagtail ya lo gestiona por sí solo)."""
        super().save(*args, **kwargs)
        page = Page.objects.filter(pk=self.pk).first()
        if page and not page.live and self.activo and self.path:
            try:
                self.save_revision().publish()
            except Exception:
                pass

    def get_context(self, request, *args, **kwargs):
        context = super().get_context(request, *args, **kwargs)
        context["es_reciente"] = self.es_reciente
        return context


# ---------------------------------------------------------------------------
# Información (comunicado / noticia / aviso / alerta)
# ---------------------------------------------------------------------------
class Informacion(ContenidoPublicable, Page):
    """
    Una única información publicable.

    Hereda de ``ContenidoPublicable`` (campos comunes) y de Page para poder
    publicarla/despublicarla desde Wagtail y obtener URL y slug automáticos.
    """

    TIPO_AVISO = "aviso"
    TIPO_COMUNICADO = "comunicado"
    TIPO_NOTICIA = "noticia"
    TIPO_ALERTA = "alerta"

    TIPO_CHOICES = [
        (TIPO_AVISO, "Aviso"),
        (TIPO_COMUNICADO, "Comunicado"),
        (TIPO_NOTICIA, "Noticia"),
        (TIPO_ALERTA, "Alerta"),
    ]

    CATEGORIA = "informacion"

    tipo = models.CharField(
        max_length=20,
        choices=TIPO_CHOICES,
        default=TIPO_AVISO,
        verbose_name="Tipo",
    )

    INDEX_CLASS = None  # se fija debajo (InformacionesIndexPage)

    content_panels = ContenidoPublicable.edit_handler_tabs
    promote_panels = Page.promote_panels

    parent_page_types = ["informaciones.InformacionesIndexPage"]
    subpage_types = []
    template = "informaciones/informacion_page.html"

    search_fields = Page.search_fields + ContenidoPublicable.search_fields

    class Meta:
        verbose_name = "Información"
        verbose_name_plural = "Informaciones"

    def __str__(self):
        return self.title

    def etiqueta_tipo(self):
        """Clase de icono Bootstrap según el tipo."""
        return {
            self.TIPO_AVISO: "bi-megaphone-fill",
            self.TIPO_COMUNICADO: "bi-envelope-paper-fill",
            self.TIPO_NOTICIA: "bi-newspaper",
            self.TIPO_ALERTA: "bi-exclamation-triangle-fill",
        }.get(self.tipo, "bi-info-circle-fill")


# ---------------------------------------------------------------------------
# Novedad (promoción / oferta / noticia / lanzamiento)
# ---------------------------------------------------------------------------
class Novedad(ContenidoPublicable, Page):
    """
    Una única novedad publicable (promociones, ofertas, lanzamientos...).

    Se muestra en una columna propia de la portada y en el listado de
    :class:`NovedadesIndexPage`. Al ser ``Page``, se puede programar y publicar.
    """

    TIPO_PROMOCION = "promocion"
    TIPO_OFERTA = "oferta"
    TIPO_REBAJA = "rebaja"
    TIPO_NOTICIA = "noticia"
    TIPO_LANZAMIENTO = "lanzamiento"
    TIPO_EMPLEO = "empleo"
    TIPO_LICITACION = "licitacion"

    TIPO_CHOICES = [
        (TIPO_PROMOCION, "Promoción"),
        (TIPO_OFERTA, "Oferta"),
        (TIPO_REBAJA, "Rebaja"),
        (TIPO_NOTICIA, "Noticia"),
        (TIPO_LANZAMIENTO, "Lanzamiento"),
        (TIPO_EMPLEO, "Oferta de empleo"),
        (TIPO_LICITACION, "Oferta de licitación"),
    ]

    CATEGORIA = "novedad"

    tipo = models.CharField(
        max_length=20,
        choices=TIPO_CHOICES,
        default=TIPO_PROMOCION,
        verbose_name="Tipo",
    )

    aparecer_en_carrusel = models.BooleanField(
        default=False,
        verbose_name="Aparecer en carrusel",
        help_text="Si está marcado, esta novedad aparecerá en el carrusel de la página de inicio.",
        db_index=True,
    )
    orden_carrusel = models.IntegerField(
        default=0,
        verbose_name="Orden en carrusel",
        help_text="Menor número = aparece primero en el carrusel.",
    )

    # ------------------------------------------------------------------
    # Visualización de la imagen (banner y tarjetas)
    # Etiquetas y ayudas redactadas sin tecnicismos para el editor.
    # ------------------------------------------------------------------
    MODO_BANNER_CHOICES = [
        ("completo", "Completo"),
        ("miniatura", "Miniatura"),
        ("auto", "Automático"),
    ]
    TAMANO_MINIATURA_CHOICES = [
        ("pequeno", "Pequeño"),
        ("mediano", "Mediano"),
        ("grande", "Grande"),
        ("completo", "Completo"),
    ]
    ESTILO_FONDO_CHOICES = [
        ("blur", "Desenfocado"),
        ("negro", "Fondo negro"),
        ("degradado", "Degradado oscuro"),
    ]
    POSICION_VERTICAL_CHOICES = [
        ("top", "Arriba"),
        ("center", "Centro"),
        ("bottom", "Abajo"),
    ]
    POSICION_HORIZONTAL_CHOICES = [
        ("left", "Izquierda"),
        ("center", "Centro"),
        ("right", "Derecha"),
    ]

    # Proporción mínima (ancho / alto) para considerar la imagen "ancha".
    # 16/9 ≈ 1.78; 1.7 es un umbral cómodo para decidir.
    UMBRAL_ASPECTO_COMPLETO = 1.7

    modo_banner = models.CharField(
        max_length=10,
        choices=MODO_BANNER_CHOICES,
        default="auto",
        verbose_name="Cómo se mostrará la imagen en el banner",
        help_text=(
            "Completo llena todo el banner. Miniatura muestra la imagen centrada "
            "sobre un fondo. Automático elige la mejor opción según la foto."
        ),
    )
    tamano_miniatura = models.CharField(
        max_length=10,
        choices=TAMANO_MINIATURA_CHOICES,
        default="mediano",
        verbose_name="Qué tan grande quieres que se vea la imagen",
        help_text=(
            "Aplica solo si elegiste Miniatura o Automático. "
            "Pequeño, Mediano, Grande o Completo."
        ),
    )
    estilo_fondo = models.CharField(
        max_length=12,
        choices=ESTILO_FONDO_CHOICES,
        default="blur",
        verbose_name="Cómo rellenar el espacio alrededor de la imagen",
        help_text=(
            "Desenfocado usa la propia imagen de fondo. "
            "Fondo negro o Degradado oscuro son alternativas sobrias."
        ),
    )
    posicion_vertical = models.CharField(
        max_length=10,
        choices=POSICION_VERTICAL_CHOICES,
        default="center",
        verbose_name="Alineación vertical de la imagen",
        help_text="Solo aplica cuando la imagen se muestra en miniatura.",
    )
    posicion_horizontal = models.CharField(
        max_length=10,
        choices=POSICION_HORIZONTAL_CHOICES,
        default="center",
        verbose_name="Alineación horizontal de la imagen",
        help_text="Solo aplica cuando la imagen se muestra en miniatura.",
    )
    auto_ajuste = models.BooleanField(
        default=True,
        verbose_name="Detectar automáticamente el mejor modo",
        help_text=(
            "Si el modo es Automático, el sistema decide según la forma de la "
            "foto: las imágenes anchas llenan el banner; las cuadradas o altas "
            "se muestran en miniatura para no cortarse."
        ),
    )

    # Compromiso de contraste: si el editor no elige color, se usa el sugerido
    # para el tipo de novedad (ver COLORES_RIBBON_SUGERIDOS).
    color_ribbon = models.CharField(
        max_length=7,
        blank=True,
        verbose_name="Color de la etiqueta de la tarjeta",
        help_text=(
            "Elige el color de la cinta que aparece sobre la imagen de la "
            "tarjeta. En blanco se usa el color sugerido para el tipo."
        ),
    )

    COLORES_RIBBON_SUGERIDOS = {
        TIPO_PROMOCION: "#E63946",
        TIPO_OFERTA: "#C1121F",
        TIPO_REBAJA: "#16A34A",
        TIPO_NOTICIA: "#0D6EFD",
        TIPO_LANZAMIENTO: "#7C3AED",
        TIPO_EMPLEO: "#0B7285",
        TIPO_LICITACION: "#495057",
    }

    def get_modo_efectivo(self):
        """Devuelve el modo real del banner ('completo' o 'miniatura').

        Si el editor eligió uno concreto, se respeta. Si eligió 'auto', el
        sistema decide según la relación de aspecto de la imagen salvo que la
        detección esté desactivada (entonces se usa el clásico 'completo').
        """
        if self.modo_banner != "auto":
            return self.modo_banner
        if not self.auto_ajuste:
            return "completo"
        imagen = self.imagen
        if imagen and imagen.width and imagen.height:
            proporcion = imagen.width / max(imagen.height, 1)
            if proporcion >= self.UMBRAL_ASPECTO_COMPLETO:
                return "completo"
        return "miniatura"

    @property
    def modo_efectivo(self):
        """Alias legible desde los templates (nunca devuelve 'auto')."""
        return self.get_modo_efectivo()

    INDEX_CLASS = None  # se fija debajo (NovedadesIndexPage)

    content_panels = ContenidoPublicable.edit_handler_tabs + [
        MultiFieldPanel(
            [
                HelpPanel(
                    content=(
                        "Si tu imagen es muy ancha, usa Completo. "
                        "Si es cuadrada o pequeña, usa Miniatura con fondo "
                        "desenfocado. Si tienes dudas, deja Automático y el "
                        "sistema lo decidirá por ti."
                    ),
                    heading="Consejos rápidos",
                ),
                FieldPanel("modo_banner"),
                FieldPanel("tamano_miniatura"),
                FieldPanel("estilo_fondo"),
                FieldPanel("posicion_vertical"),
                FieldPanel("posicion_horizontal"),
                FieldPanel("auto_ajuste"),
            ],
            heading="Visualización del banner",
            classname="collapsible",
        ),
        MultiFieldPanel(
            [
                FieldPanel("aparecer_en_carrusel"),
                FieldPanel("orden_carrusel"),
            ],
            heading="Carrusel de inicio",
        ),
        MultiFieldPanel(
            [
                HelpPanel(
                    content=(
                        "Si no eliges color, cada tipo usa el suyo: Promoción "
                        "rojo, Oferta rojo oscuro, Rebaja verde, Noticia azul, "
                        "Lanzamiento violeta, Empleo azul petróleo y "
                        "Licitación gris."
                    ),
                    heading="Colores sugeridos",
                ),
                FieldPanel(
                    "color_ribbon",
                    widget=forms.TextInput(attrs={"type": "color"}),
                ),
            ],
            heading="Etiqueta de la tarjeta",
            classname="collapsible",
        ),
    ]
    promote_panels = Page.promote_panels

    parent_page_types = ["informaciones.NovedadesIndexPage"]
    subpage_types = []
    template = "informaciones/novedad_page.html"

    search_fields = Page.search_fields + ContenidoPublicable.search_fields

    class Meta:
        verbose_name = "Novedad"
        verbose_name_plural = "Novedades"

    def __str__(self):
        return self.title

    def etiqueta_tipo(self):
        """Clase de icono Bootstrap según el tipo."""
        return {
            self.TIPO_PROMOCION: "bi-tag-fill",
            self.TIPO_OFERTA: "bi-tags-fill",
            self.TIPO_REBAJA: "bi-percent",
            self.TIPO_NOTICIA: "bi-newspaper",
            self.TIPO_LANZAMIENTO: "bi-rocket-takeoff-fill",
            self.TIPO_EMPLEO: "bi-briefcase-fill",
            self.TIPO_LICITACION: "bi-file-earmark-text-fill",
        }.get(self.tipo, "bi-stars")

    @property
    def ribbon(self):
        """Texto del ribbon que se muestra sobre la imagen de la tarjeta."""
        return dict(
            [
                (self.TIPO_PROMOCION, "Promoción"),
                (self.TIPO_OFERTA, "Oferta"),
                (self.TIPO_REBAJA, "Rebaja"),
                (self.TIPO_NOTICIA, "Noticia"),
                (self.TIPO_LANZAMIENTO, "Lanzamiento"),
                (self.TIPO_EMPLEO, "Empleo"),
                (self.TIPO_LICITACION, "Licitación"),
            ]
        ).get(self.tipo, "")

    @property
    def tiene_ribbon(self):
        return bool(self.ribbon)

    @staticmethod
    def _luminancia(color):
        """Luminancia relativa en 0-1 de un color HEX (para elegir el texto)."""
        c = (color or "").lstrip("#")
        if len(c) != 6:
            return 0.6
        try:
            r, g, b = (int(c[i:i + 2], 16) / 255 for i in (0, 2, 4))
        except ValueError:
            return 0.6
        return 0.299 * r + 0.587 * g + 0.114 * b

    @property
    def color_ribbon_efectivo(self):
        """Color que finalmente se usa: el elegido o el sugerido por tipo."""
        return self.color_ribbon or self.COLORES_RIBBON_SUGERIDOS.get(
            self.tipo, "#E63946"
        )

    @property
    def color_ribbon_texto(self):
        """Texto blanco u oscuro según el color efectivo (contraste)."""
        return "#1a1a1a" if Novedad._luminancia(self.color_ribbon_efectivo) > 0.6 else "#ffffff"


# ---------------------------------------------------------------------------
# Índice de novedades (listado público)
# ---------------------------------------------------------------------------
class NovedadesIndexPage(Page):
    """
    Contenedor principal de novedades.

    Sirve el listado público de :class:`Novedad` activas, con filtros por tipo y
    paginación, reutilizando la misma estructura que InformacionesIndexPage.
    """

    introduccion = RichTextField(blank=True, verbose_name="Introducción")

    dias_recientes = models.PositiveIntegerField(
        default=5,
        verbose_name="Días para novedades recientes",
        help_text="Cuántos días hacia atrás se consideran 'recientes' (campana / cartel).",
    )

    content_panels = Page.content_panels + [
        FieldPanel("introduccion"),
        FieldPanel("dias_recientes"),
    ]

    subpage_types = ["informaciones.Novedad"]
    parent_page_types = [
        "home.HomePage",
        "core.GenericPage",
        "automotive.AutomotivePage",
    ]
    max_count = 1
    template = "informaciones/novedades_index_page.html"

    ITEMS_POR_PAGINA = 15

    class Meta:
        verbose_name = "Novedades"
        verbose_name_plural = "Novedades"

    def __str__(self):
        return self.title

    @property
    def ventana_dias(self):
        if self.dias_recientes:
            return self.dias_recientes
        from apps.informaciones import notificaciones
        return notificaciones.dias_recientes()

    def recientes(self, limit=None):
        from apps.informaciones import notificaciones
        return notificaciones.novedades_recientes(
            dias=self.ventana_dias, limit=limit
        )

    def get_context(self, request, *args, **kwargs):
        context = super().get_context(request, *args, **kwargs)

        query = Novedad.objects.child_of(self).filter(activo=True, live=True)
        query = query.select_related("imagen").order_by("orden", "-fecha_publicacion")

        slug_tipo = (request.GET.get("tipo") or "").strip()
        tipos_validos = {c for c, _ in Novedad.TIPO_CHOICES}
        if slug_tipo in tipos_validos:
            query = query.filter(tipo=slug_tipo)

        paginator = Paginator(query, self.ITEMS_POR_PAGINA)
        pagina = request.GET.get("page")
        try:
            items = paginator.page(pagina)
        except PageNotAnInteger:
            items = paginator.page(1)
        except EmptyPage:
            items = paginator.page(paginator.num_pages)

        context.update(
            {
                "novedades": items,
                "tipo_activo": slug_tipo,
                "tipos_disponibles": Novedad.TIPO_CHOICES,
            }
        )
        return context


Novedad.INDEX_CLASS = NovedadesIndexPage
Informacion.INDEX_CLASS = InformacionesIndexPage


# ---------------------------------------------------------------------------
# Cinta de informaciones (ticker)
# ---------------------------------------------------------------------------
class InformacionCinta(models.Model):
    """
    Una información breve que se muestra en la cinta (ticker) superior.

    Cada registro alimenta una franja horizontal que se desplaza sobre el
    sitio. Se puede activar/desactivar, programar por fechas y configurar su
    color de fondo y texto individualmente.

    Se gestiona en: Wagtail admin → Snippets → Información de cinta.
    """

    TIPO_AVISO = "aviso"
    TIPO_PROMOCION = "promocion"
    TIPO_ALERTA = "alerta"
    TIPO_COMUNICADO = "comunicado"
    TIPO_OTRO = "otro"

    TIPO_CHOICES = [
        (TIPO_AVISO, "Aviso"),
        (TIPO_PROMOCION, "Promoción"),
        (TIPO_ALERTA, "Alerta"),
        (TIPO_COMUNICADO, "Comunicado"),
        (TIPO_OTRO, "Otro"),
    ]

    texto = models.CharField(
        max_length=200,
        verbose_name="Texto",
        help_text="Texto breve que se verá en la cinta (máx. 200 caracteres).",
    )
    tipo = models.CharField(
        max_length=20,
        choices=TIPO_CHOICES,
        default=TIPO_AVISO,
        verbose_name="Tipo",
    )
    enlace = models.URLField(
        null=True,
        blank=True,
        verbose_name="Enlace",
        help_text="Si se indica, el texto de la cinta será un enlace clicable.",
    )
    fecha_inicio = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Fecha de inicio",
        help_text="Si se deja vacía, se muestra desde ahora.",
        db_index=True,
    )
    fecha_fin = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Fecha de fin",
        help_text="Si se deja vacía, no expira.",
        db_index=True,
    )
    orden = models.IntegerField(
        default=0,
        verbose_name="Orden",
        help_text="Menor número = aparece primero en la cinta.",
    )
    activo = models.BooleanField(
        default=True,
        verbose_name="Activo",
        help_text="Si se desactiva, no se muestra en la cinta.",
        db_index=True,
    )
    color_fondo = models.CharField(
        max_length=7,
        default="#000000",
        verbose_name="Color de fondo",
        help_text="Color de fondo de esta franja (formato HEX, p. ej. #E63946).",
    )
    color_texto = models.CharField(
        max_length=7,
        default="#FFFFFF",
        verbose_name="Color de texto",
        help_text="Color del texto de esta franja (formato HEX, p. ej. #FFFFFF).",
    )
    velocidad = models.IntegerField(
        default=30,
        verbose_name="Velocidad",
        help_text=(
            "Píxeles por segundo del desplazamiento (marquee) o "
            "segundos que se muestra cada franja (slider)."
        ),
    )
    fecha_creacion = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Fecha de creación",
    )

    panels = [
        FieldPanel("texto"),
        FieldPanel("tipo"),
        FieldPanel("enlace"),
        FieldPanel("fecha_inicio"),
        FieldPanel("fecha_fin"),
        FieldPanel("orden"),
        FieldPanel("activo"),
        FieldPanel("color_fondo"),
        FieldPanel("color_texto"),
        FieldPanel("velocidad"),
    ]

    class Meta:
        verbose_name = "Información de cinta"
        verbose_name_plural = "Informaciones de cinta"
        ordering = ["orden", "-fecha_creacion"]

    def __str__(self):
        return self.texto

    # --- Lógica de visibilidad ---
    def esta_visible(self, ahora=None):
        """¿Se debe mostrar en este momento?"""
        if not self.activo:
            return False
        ahora = ahora or timezone.now()
        if self.fecha_inicio and self.fecha_inicio > ahora:
            return False
        if self.fecha_fin and self.fecha_fin <= ahora:
            return False
        return True

    @classmethod
    def activas(cls, ahora=None):
        """Informaciones de cinta que se muestran ahora, ordenadas por
        ``orden`` ascendente y luego por fecha de creación descendente."""
        ahora = ahora or timezone.now()
        return (
            cls.objects.filter(activo=True)
            .filter(Q(fecha_inicio__isnull=True) | Q(fecha_inicio__lte=ahora))
            .filter(Q(fecha_fin__isnull=True) | Q(fecha_fin__gt=ahora))
            .order_by("orden", "-fecha_creacion")
        )

    # --- Utilidades de presentación ---
    @property
    def nombre_tipo(self):
        return dict(self.TIPO_CHOICES).get(self.tipo, self.tipo)

    def etiqueta_tipo(self):
        """Icono Bootstrap según el tipo de información de cinta."""
        return {
            self.TIPO_AVISO: "bi-megaphone-fill",
            self.TIPO_PROMOCION: "bi-tag-fill",
            self.TIPO_ALERTA: "bi-exclamation-triangle-fill",
            self.TIPO_COMUNICADO: "bi-envelope-paper-fill",
            self.TIPO_OTRO: "bi-info-circle-fill",
        }.get(self.tipo, "bi-info-circle-fill")


class ConfiguracionCinta(models.Model):
    """
    Configuración global de la cinta de informaciones.

    Un único registro. Si ``activada=False``, la cinta no se renderiza
    aunque existan :class:`InformacionCinta` activas.

    Se gestiona en: Wagtail admin → Snippets → Configuración de cinta.
    """

    ESTILO_MARQUEE = "marquee"
    ESTILO_SLIDER = "slider"
    ESTILO_ESTATICO = "estatico"

    ESTILO_CHOICES = [
        (ESTILO_MARQUEE, "Desplazamiento continuo (marquee)"),
        (ESTILO_SLIDER, "Slider (una por vez, transición suave)"),
        (ESTILO_ESTATICO, "Estático (todas visibles, separadas)"),
    ]

    activada = models.BooleanField(
        default=False,
        verbose_name="Cinta activada",
        help_text="Si está desactivada, la cinta no aparece aunque haya informaciones.",
    )
    mostrar_iconos = models.BooleanField(
        default=True,
        verbose_name="Mostrar iconos",
        help_text="Muestra el icono correspondiente al tipo de cada información.",
    )
    estilo = models.CharField(
        max_length=20,
        choices=ESTILO_CHOICES,
        default=ESTILO_MARQUEE,
        verbose_name="Estilo de animación",
    )

    panels = [
        FieldPanel("activada"),
        FieldPanel("mostrar_iconos"),
        FieldPanel("estilo"),
    ]

    class Meta:
        verbose_name = "Configuración de cinta"
        verbose_name_plural = "Configuración de cinta"

    def __str__(self):
        return "Configuración de cinta"

    @classmethod
    def obtener(cls):
        """Devuelve la configuración global (crea una por defecto si no existe)."""
        config, _ = cls.objects.get_or_create(pk=1)
        return config



