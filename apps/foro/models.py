"""Modelos del módulo de foro (Servicios Automotores S.A).

- ``ForoIndexPage`` : página contenedora del foro (config + listados + nuevo tema).
- ``CategoriaForo`` : snippet que clasifica los temas.
- ``TemaForo``      : página de detalle de un tema de discusión.
- ``RespuestaForo`` : modelo cluster hijo, respuestas de un tema (InlinePanel).

La moderación funciona así: un ``TemaForo`` con ``estado='pendiente'`` nunca
se lista en el frontend; el staff lo aprueba (``'aprobado'``/``'fijado'``) desde
el panel de Wagtail. Las ``RespuestaForo`` tienen un campo ``aprobado`` que se
respeta según ``moderacion_previa`` de la página índice.
"""

from django.conf import settings
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.db import models
from django.db.models import Count, Q
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from modelcluster.fields import ParentalKey
from wagtail.admin.panels import FieldPanel, InlinePanel, MultiFieldPanel
from wagtail.fields import RichTextField
from wagtail.models import Page
from wagtail.search import index


# ---------------------------------------------------------------------------
# Categoría de foro (snippet)
# ---------------------------------------------------------------------------
class CategoriaForo(models.Model):
    """Categoría a la que pertenecen los temas (mecánica, repuestos, etc.)."""

    nombre = models.CharField(max_length=150, verbose_name="Nombre")
    slug = models.SlugField(max_length=160, unique=True, verbose_name="Slug")
    descripcion = models.TextField(blank=True, verbose_name="Descripción")
    icono = models.CharField(
        max_length=60, blank=True,
        verbose_name="Icono (Bootstrap)",
        help_text="Clase de icono Bootstrap, p. ej. 'bi-gear-fill' (opcional).",
    )
    orden = models.IntegerField(default=0, verbose_name="Orden")
    activo = models.BooleanField(default=True, verbose_name="Activa", db_index=True)

    panels = [
        FieldPanel("nombre"),
        FieldPanel("slug"),
        FieldPanel("descripcion"),
        FieldPanel("icono"),
        FieldPanel("orden"),
        FieldPanel("activo"),
    ]

    class Meta:
        verbose_name = "Categoría de foro"
        verbose_name_plural = "Categorías de foro"
        ordering = ["orden", "nombre"]

    def __str__(self):
        return self.nombre

    def total_temas(self):
        if hasattr(self, "temas_count") and self.temas_count is not None:
            return self.temas_count
        return self.temas.filter(estado__in=["aprobado", "fijado"]).count()

    total_temas.short_description = "Temas"

    def ultimo_tema(self):
        return (
            self.temas.filter(estado__in=["aprobado", "fijado"])
            .order_by("-first_published_at")
            .first()
        )

    ultimo_tema.short_description = "Último tema"


# ---------------------------------------------------------------------------
# Respuesta de un tema (modelo cluster hijo)
# ---------------------------------------------------------------------------
class RespuestaForo(models.Model):
    """Una respuesta dentro de un tema (relación 1:N con TemaForo)."""

    tema = ParentalKey(
        "foro.TemaForo",
        on_delete=models.CASCADE,
        related_name="respuestas",
    )
    autor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="respuestas_foro",
        verbose_name="Autor (usuario)",
    )
    nombre_anonimo = models.CharField(
        max_length=150, null=True, blank=True, verbose_name="Nombre (anónimo)"
    )
    cuerpo = RichTextField(verbose_name="Contenido")
    fecha_creacion = models.DateTimeField(auto_now_add=True, verbose_name="Fecha")
    aprobado = models.BooleanField(default=False, verbose_name="Aprobada", db_index=True)

    panels = [
        FieldPanel("autor", read_only=True),
        FieldPanel("nombre_anonimo"),
        FieldPanel("cuerpo"),
        FieldPanel("aprobado"),
    ]

    class Meta:
        verbose_name = "Respuesta"
        verbose_name_plural = "Respuestas"
        ordering = ["fecha_creacion"]

    def __str__(self):
        return f"Respuesta a {self.tema_id}"

    @property
    def autor_visible(self):
        """Nombre mostrado: el del usuario autenticado o el nombre anónimo."""
        if self.autor_id:
            return self.autor.get_full_name() or self.autor.username
        return self.nombre_anonimo or "Anónimo"

    def inicial(self):
        nombre = self.autor_visible
        return (nombre or "?").strip()[0].upper()


# ---------------------------------------------------------------------------
# Página índice del foro
# ---------------------------------------------------------------------------
class ForoIndexPage(Page):
    """Contenedor principal del foro: configuración, categorías y temas recientes."""

    introduccion = RichTextField(blank=True, verbose_name="Introducción")
    reglas = RichTextField(blank=True, verbose_name="Reglas de la comunidad")
    allow_anonymous = models.BooleanField(
        default=False,
        verbose_name="Permitir participación anónima",
        help_text="Desactivado: se requiere iniciar sesión para publicar.",
    )
    moderacion_previa = models.BooleanField(
        default=True,
        verbose_name="Moderación previa",
        help_text="Si está activo, los temas requieren aprobación para mostrarse.",
    )

    content_panels = Page.content_panels + [
        FieldPanel("introduccion"),
        FieldPanel("reglas"),
        FieldPanel("allow_anonymous"),
        FieldPanel("moderacion_previa"),
    ]

    subpage_types = ["foro.TemaForo"]
    parent_page_types = [
        "home.HomePage",
        "core.GenericPage",
        "automotive.AutomotivePage",
    ]
    max_count = 1
    template = "foro/foro_index_page.html"

    TEMAS_POR_PAGINA = 20

    class Meta:
        verbose_name = "Foro de la comunidad"
        verbose_name_plural = "Foros de la comunidad"

    def __str__(self):
        return self.title

    # --- Utilidades de permisos ---
    def puede_participar(self, request):
        """Está permitido publicar: anónimo permitido o usuario autenticado."""
        if self.allow_anonymous or request.user.is_authenticated:
            return True
        return False

    def requiere_nombre(self, request):
        """El invitado debe dejar un nombre si se permite anónimo y no está logueado."""
        return self.allow_anonymous and not request.user.is_authenticated

    # --- Creación de temas ---
    def _crear_tema(self, request, form):
        """Crea la página TemaForo bajo este índice con la política de moderación."""
        from django.utils import timezone

        from apps.foro.forms import html_seguro

        dato = form.cleaned_data
        estado = (
            'pendiente'
            if self.moderacion_previa and not request.user.is_staff
            else 'aprobado'
        )

        titulo = dato["titulo"]
        tema = TemaForo(
            title=titulo,
            slug="",
            categoria=dato["categoria"],
            estado=estado,
            cuerpo=html_seguro(dato["cuerpo"]),
        )
        # Un Page debe crearse como hijo de otro Page (path/depth). add_child
        # asigna el árbol y dispara save() (que autogenera el slug).
        self.add_child(instance=tema)
        # Fecha de publicación para que aparezca en "último tema".
        if tema.estado == "aprobado":
            TemaForo.objects.filter(pk=tema.pk).update(
                first_published_at=timezone.now(), last_published_at=timezone.now()
            )

        if request.user.is_authenticated:
            tema.autor = request.user
        elif dato["nombre_anonimo"]:
            tema.nombre_anonimo = dato["nombre_anonimo"]
        else:
            tema.nombre_anonimo = "Anónimo"
        tema.save(update_fields=["autor", "nombre_anonimo"])
        return tema

    def serve(self, request, *args, **kwargs):
        from apps.foro.forms import NuevoTemaForm

        form = None
        if request.method == "POST":
            # Solo puede publicar quien cumpla el requisito de permisos.
            if not self.puede_participar(request):
                from django.contrib import messages
                messages.error(request, "Debes iniciar sesión para crear un tema.")
                return redirect(self.url + "?acceso=1")

            form = NuevoTemaForm(
                request.POST,
                requiere_nombre=self.requiere_nombre(request),
            )
            if form.is_valid():
                tema = self._crear_tema(request, form)
                from django.contrib import messages
                if tema.estado == "pendiente":
                    messages.info(
                        request,
                        "Gracias, tu tema está pendiente de moderación y se publicará en breve.",
                    )
                    return redirect(self.url)
                messages.success(request, "¡Tema publicado correctamente!")
                return redirect(tema.url)
        else:
            form = NuevoTemaForm(requiere_nombre=self.requiere_nombre(request))

        context = self.get_context(request)
        context["form_nuevo_tema"] = form
        return TemplateResponse(request, self.get_template(request), context)

    def get_context(self, request, *args, **kwargs):
        context = super().get_context(request, *args, **kwargs)

        # Búsqueda por título o contenido (GET ?q=)
        q = (request.GET.get("q") or "").strip()
        slug_cat = (request.GET.get("categoria") or "").strip()

        temas = TemaForo.objects.child_of(self).filter(
            estado__in=["aprobado", "fijado"]
        ).select_related("autor", "categoria").annotate(
            respuestas_aprobadas_count=Count(
                "respuestas",
                filter=Q(respuestas__aprobado=True),
            )
        )
        if q:
            temas = temas.filter(
                Q(title__icontains=q) | Q(cuerpo__icontains=q)
            )
        if slug_cat:
            temas = temas.filter(categoria__slug=slug_cat)
        temas = temas.order_by("-fecha_creacion")

        pagina = request.GET.get("page")
        paginator = Paginator(temas, self.TEMAS_POR_PAGINA)
        try:
            temas_pag = paginator.page(pagina)
        except PageNotAnInteger:
            temas_pag = paginator.page(1)
        except EmptyPage:
            temas_pag = paginator.page(paginator.num_pages)

        categorias = CategoriaForo.objects.filter(activo=True).order_by("orden", "nombre").annotate(
            temas_count=Count(
                "temas",
                filter=Q(temas__estado__in=["aprobado", "fijado"]),
            )
        )

        context.update(
            {
                "temas": temas_pag,
                "categorias": categorias,
                "q": q,
                "slug_cat": slug_cat,
                "pueden_participar": self.puede_participar(request),
            }
        )
        return context


# ---------------------------------------------------------------------------
# Tema de foro (página)
# ---------------------------------------------------------------------------
class TemaForo(Page):
    """Página de detalle de un único tema con sus respuestas."""

    ESTADO_PENDIENTE = "pendiente"
    ESTADO_APROBADO = "aprobado"
    ESTADO_CERRADO = "cerrado"
    ESTADO_FIJADO = "fijado"

    ESTADO_CHOICES = [
        (ESTADO_PENDIENTE, "Pendiente de moderación"),
        (ESTADO_APROBADO, "Aprobado"),
        (ESTADO_CERRADO, "Cerrado"),
        (ESTADO_FIJADO, "Fijado (destacado)"),
    ]

    categoria = models.ForeignKey(
        CategoriaForo,
        on_delete=models.PROTECT,
        related_name="temas",
        verbose_name="Categoría",
    )
    estado = models.CharField(
        max_length=20, choices=ESTADO_CHOICES, default=ESTADO_PENDIENTE,
        verbose_name="Estado",
        db_index=True,
    )
    autor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="temas_foro",
        verbose_name="Autor (usuario)",
    )
    nombre_anonimo = models.CharField(
        max_length=150, null=True, blank=True, verbose_name="Nombre (anónimo)"
    )
    cuerpo = RichTextField(verbose_name="Contenido")
    fecha_creacion = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de creación", db_index=True)
    fecha_modificacion = models.DateTimeField(auto_now=True, verbose_name="Última modificación")
    visitas = models.PositiveIntegerField(default=0, verbose_name="Visitas")

    # Campos de Page que reusamos como listado/títulos
    content_panels = [
        MultiFieldPanel(
            [
                FieldPanel("title"),
                FieldPanel("categoria"),
                FieldPanel("cuerpo"),
            ],
            heading="Contenido",
        ),
        MultiFieldPanel(
            [
                FieldPanel("estado"),
                FieldPanel("autor"),
                FieldPanel("nombre_anonimo"),
                FieldPanel("visitas"),
            ],
            heading="Publicación",
        ),
        MultiFieldPanel(
            [
                InlinePanel("respuestas", label="Respuestas", min_num=0),
            ],
            heading="Respuestas",
        ),
    ]
    promote_panels = Page.promote_panels

    parent_page_types = ["foro.ForoIndexPage"]
    subpage_types = []

    search_fields = Page.search_fields + [
        index.SearchField("title"),
        index.SearchField("cuerpo"),
        index.FilterField("estado"),
        index.FilterField("categoria"),
        index.FilterField("fecha_creacion"),
    ]

    template = "foro/tema_foro_page.html"

    class Meta:
        verbose_name = "Tema de foro"
        verbose_name_plural = "Temas de foro"

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        # El slug debe ser único dentro del índice. Se autogenera desde el título,
        # garantizando unicidad sin colisiones (slug-x si ya existe).
        from django.utils.text import slugify

        if not self.slug:
            base = slugify(self.title)[:255] or "tema"
            slug = base
            n = 1
            while TemaForo.objects.exclude(pk=self.pk).filter(slug=slug).exists():
                n += 1
                slug = f"{base}-{n}"
            self.slug = slug
        super().save(*args, **kwargs)

    # --- Estado / presentación ---
    @property
    def esta_clasificado(self):
        return self.estado in [self.ESTADO_APROBADO, self.ESTADO_FIJADO]

    @property
    def esta_cerrado(self):
        return self.estado == self.ESTADO_CERRADO

    @property
    def esta_fijado(self):
        return self.estado == self.ESTADO_FIJADO

    @property
    def autor_visible(self):
        if self.autor_id:
            return self.autor.get_full_name() or self.autor.username
        return self.nombre_anonimo or "Anónimo"

    def inicial(self):
        nombre = self.autor_visible or "?"
        return nombre.strip()[0].upper()

    @property
    def total_respuestas(self):
        return self.respuestas.count()

    @property
    def total_respuestas_aprobadas(self):
        if hasattr(self, "respuestas_aprobadas_count") and self.respuestas_aprobadas_count is not None:
            return self.respuestas_aprobadas_count
        return self.respuestas.filter(aprobado=True).count()

    # --- Navegación / detalle ---
    def get_context(self, request, *args, **kwargs):
        context = super().get_context(request, *args, **kwargs)
        respuestas = self.respuestas.filter(aprobado=True).select_related("autor")
        context["respuestas"] = respuestas
        context["respuestas_pendientes"] = self.respuestas.filter(aprobado=False).count()
        return context

    def serve(self, request, *args, **kwargs):
        from apps.foro.forms import NuevaRespuestaForm

        indice = self.get_parent().specific

        # Incrementar contador de visitas.
        TemaForo.objects.filter(pk=self.pk).update(visitas=models.F("visitas") + 1)

        form = None
        if request.method == "POST" and "__responder" in request.POST:
            if not indice.puede_participar(request):
                from django.contrib import messages
                messages.error(request, "Debes iniciar sesión para responder.")
                return redirect("#responder")

            if self.esta_cerrado:
                from django.contrib import messages
                messages.error(request, "El tema está cerrado y ya no admite respuestas.")
                return redirect(self.url)

            form = NuevaRespuestaForm(
                request.POST,
                requiere_nombre=indice.requiere_nombre(request),
            )
            if form.is_valid():
                from apps.foro.forms import html_seguro

                respuesta = RespuestaForo(
                    tema=self,
                    cuerpo=html_seguro(form.cleaned_data["cuerpo"]),
                    aprobado=(not indice.moderacion_previa) or request.user.is_staff,
                )
                if request.user.is_authenticated:
                    respuesta.autor = request.user
                elif form.cleaned_data["nombre_anonimo"]:
                    respuesta.nombre_anonimo = form.cleaned_data["nombre_anonimo"]
                else:
                    respuesta.nombre_anonimo = "Anónimo"
                respuesta.save()

                from django.contrib import messages
                if respuesta.aprobado:
                    messages.success(request, "Respuesta publicada correctamente.")
                else:
                    messages.info(
                        request,
                        "Gracias, tu respuesta está pendiente de moderación.",
                    )
                return redirect(self.url + "#respuestas")
        else:
            form = NuevaRespuestaForm(requiere_nombre=indice.requiere_nombre(request))

        context = self.get_context(request, *args, **kwargs)
        context["form_respuesta"] = form
        context["indice"] = indice
        context["pueden_participar"] = indice.puede_participar(request)
        return TemplateResponse(request, self.get_template(request), context)
