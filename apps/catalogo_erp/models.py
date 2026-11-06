"""Modelos del catálogo ERP.

- ``ConfiguracionERP``   : snippet único con la conexión a PostgreSQL (ERP).
- ``CategoriaProductoERP``: snippet que describe cómo buscar un grupo de
                            productos en el ERP (tabla, campos, método).
- ``CatalogoERPPage``    : página pública con el grid de categorías y el
                           modal de consulta de disponibilidad.
"""

from django import forms
from django.core.cache import cache
from django.db import models
from django.utils.text import slugify
from wagtail.admin.panels import (
    FieldPanel,
    HelpPanel,
    MultiFieldPanel,
    ObjectList,
    TabbedInterface,
)
from wagtail.fields import RichTextField
from wagtail.models import Page

from apps.catalogo_erp import crypto

CACHE_CATEGORIAS = "catalogo_erp:categorias"


class BotonProbarConexion(HelpPanel):
    """Panel no editable: enlace/botón "Probar conexión" en el editor."""

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("template", "wagtailadmin/catalogo_erp/boton_probar_conexion.html")
        kwargs.setdefault("content", "")
        super().__init__(*args, **kwargs)


# ---------------------------------------------------------------------------
# Configuración de la conexión al ERP (snippet, preferiblemente una sola)
# ---------------------------------------------------------------------------
class ConfiguracionERP(models.Model):
    """Parámetros de conexión a la base ERP (PostgreSQL, solo lectura)."""

    host = models.CharField(max_length=255, verbose_name="Host / IP", help_text="Ej.: 192.168.1.20")
    puerto = models.IntegerField(default=5432, verbose_name="Puerto")
    nombre_bd = models.CharField(max_length=120, verbose_name="Base de datos")
    usuario = models.CharField(max_length=120, verbose_name="Usuario")
    password = models.CharField(
        max_length=512,
        verbose_name="Contraseña",
        blank=True,
        help_text="Se guarda cifrada. Déjala vacía para conservar la actual.",
    )
    schema = models.CharField(
        max_length=120, default="public", verbose_name="Esquema",
        help_text="Esquema PostgreSQL donde viven las tablas (por defecto 'public').",
    )

    # ── Tabla de stock / dependencias (supuestos del ERP) ──
    tabla_stock = models.CharField(
        max_length=120, default="stock_productos", verbose_name="Tabla de stock",
        help_text="Tabla/vista con la disponibilidad por dependencia.",
    )
    campo_stock_codigo = models.CharField(
        max_length=120, default="codigo_producto", verbose_name="Campo código (stock)",
    )
    campo_stock_dependencia = models.CharField(
        max_length=120, default="codigo_dependencia", verbose_name="Campo dependencia (stock)",
    )
    campo_stock_cantidad = models.CharField(
        max_length=120, default="cantidad", verbose_name="Campo cantidad",
    )
    tabla_dependencias = models.CharField(
        max_length=120, default="dependencias", verbose_name="Tabla de dependencias",
        help_text="Catálogo de sucursales/talleres/almacenes (codigo → nombre).",
    )
    campo_dep_codigo = models.CharField(
        max_length=120, default="codigo", verbose_name="Campo código (dependencia)",
    )
    campo_dep_nombre = models.CharField(
        max_length=120, default="nombre", verbose_name="Campo nombre (dependencia)",
    )

    # ── Estado ──
    activo = models.BooleanField(
        default=False, verbose_name="Activa",
        help_text="Solo una configuración activa se usa en el sitio.",
    )
    ultimo_test = models.DateTimeField(
        null=True, blank=True, editable=False, verbose_name="Última prueba de conexión",
    )

    panels = [
        ObjectList(
            [
                HelpPanel(
                    heading="Datos de conexión",
                    content="""
Para conectar el catálogo a tu ERP necesitas la URL/IP, el puerto PostgreSQL,
la base de datos y las credenciales de un usuario con permiso SOLO LECTURA.
Las consultas usan conexiones efímeras, parametrizadas y con
statement_timeout para no bloquear consultas largas.
""".strip(),
                ),
                BotonProbarConexion(),
                MultiFieldPanel(
                    [
                        FieldPanel("host"),
                        FieldPanel("puerto"),
                        FieldPanel("nombre_bd"),
                        FieldPanel("usuario"),
                        FieldPanel(
                            "password",
                            widget=forms.PasswordInput(
                                render_value=False,
                                attrs={
                                    "autocomplete": "new-password",
                                    "placeholder": "••••••••  (déjala en blanco para conservarla)",
                                },
                            ),
                        ),
                        FieldPanel("schema"),
                    ],
                    heading="Conexión",
                ),
            ],
            heading="Conexión",
        ),
        ObjectList(
            [
                MultiFieldPanel(
                    [
                        FieldPanel("tabla_stock"),
                        FieldPanel("campo_stock_codigo"),
                        FieldPanel("campo_stock_dependencia"),
                        FieldPanel("campo_stock_cantidad"),
                    ],
                    heading="Tabla de stock",
                ),
                MultiFieldPanel(
                    [
                        FieldPanel("tabla_dependencias"),
                        FieldPanel("campo_dep_codigo"),
                        FieldPanel("campo_dep_nombre"),
                    ],
                    heading="Dependencias (sucursales / talleres / almacenes)",
                ),
            ],
            heading="Stock y dependencias",
        ),
        ObjectList(
            [
                FieldPanel("activo"),
            ],
            heading="Estado",
        ),
    ]

    BASE_PANEL = panels[0]
    SIDE_PANELS = []
    EDIT_HANDLER = TabbedInterface(
        ObjectList(panels[0].children, heading="Conexión"),
        ObjectList(panels[1].children, heading="Stock y dependencias"),
        ObjectList(panels[2].children, heading="Estado"),
    )

    class Meta:
        verbose_name = "Configuración ERP"
        verbose_name_plural = "Configuración ERP (única)"

    def __str__(self):
        return f"ERP {self.usuario}@{self.host}:{self.puerto}/{self.nombre_bd}"

    # -- Utilidades de instancia -------------------------------------------------
    @property
    def password_plana(self):
        """Contraseña descifrada (nevera de la conexión)."""
        return crypto.descifrar(self.password)

    # -- Utilidades de clase -----------------------------------------------------
    @classmethod
    def obtener(cls):
        """Devuelve la configuración (la primera creada o ``None``)."""
        return cls.objects.order_by("pk").first()

    @classmethod
    def activa(cls):
        """Devuelve la configuración activa o ``None``.

        Se busca por ``activo=True`` y no por "la primera": si quedara más de
        una fila (p. ej. una configuración de ejemplo desactivada junto a la
        real), la primera no tiene por qué ser la activa.
        """
        return cls.objects.filter(activo=True).order_by("pk").first()

    # -- Persistencia ------------------------------------------------------------
    def save(self, *args, **kwargs):
        # Encripta la contraseña solo si es nueva (texto plano o token no cifrado).
        if self.password:
            if not self.password.startswith(crypto._PREFIJOS_CIFRADOS):  # noqa: SLF001
                self.password = crypto.cifrar(self.password)
        elif self.pk:
            # El formulario devuelve "" cuando no se quiere cambiar la contraseña.
            self.password = type(self).objects.filter(pk=self.pk).values_list(
                "password", flat=True
            ).first() or ""
        # Garantiza una única configuración activa (estilo "singleton").
        if self.activo:
            type(self).objects.filter(activo=True).exclude(pk=self.pk).update(activo=False)
        super().save(*args, **kwargs)


# ---------------------------------------------------------------------------
# Categoría de productos del ERP (snippet)
# ---------------------------------------------------------------------------
class CategoriaProductoERP(models.Model):
    """Describe una categoría del catálogo y cómo consultarla en el ERP."""

    METODO_CODIGO = "codigo_exacto"
    METODO_SEGMENTO = "segmento"
    METODO_DESCRIPCION = "descripcion"
    METODO_MULTIPLE = "multiple"
    METODO_CHOICES = [
        (METODO_CODIGO, "Código exacto"),
        (METODO_SEGMENTO, "Segmento / prefijo"),
        (METODO_DESCRIPCION, "Descripción libre"),
        (METODO_MULTIPLE, "Múltiple (varios campos)"),
    ]

    nombre = models.CharField(max_length=150, verbose_name="Nombre")
    slug = models.SlugField(
        max_length=160, unique=True, verbose_name="Slug",
        help_text="Identificador único (autogenerado si se deja vacío).",
    )
    descripcion = models.TextField(blank=True, verbose_name="Descripción")
    imagen = models.ForeignKey(
        "wagtailimages.Image",
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        verbose_name="Imagen",
    )

    tabla_origen = models.CharField(
        max_length=120, verbose_name="Tabla / vista en el ERP",
        help_text="Tabla o vista que contiene los productos de la categoría.",
    )
    campo_codigo = models.CharField(
        max_length=120, default="codigo", verbose_name="Campo código",
        help_text="Columna que identifica el código del producto.",
    )
    campo_nombre = models.CharField(
        max_length=120, default="nombre", verbose_name="Campo nombre/descripción",
    )
    campo_extra1 = models.CharField(
        max_length=120, blank=True, verbose_name="Campo extra 1",
        help_text="Opción: dato adicional que se muestra (ej.: 'marca').",
    )
    campo_extra2 = models.CharField(
        max_length=120, blank=True, verbose_name="Campo extra 2",
    )
    campo_extra3 = models.CharField(
        max_length=120, blank=True, verbose_name="Campo extra 3",
    )
    campo_categoria = models.CharField(
        max_length=120, blank=True, verbose_name="Campo de categoría (filtro)",
        help_text="Opcional: columna que distingue el tipo de producto en el ERP "
                  "(ej.: 'categoria'). Vacío = sin filtro.",
    )
    valor_categoria = models.CharField(
        max_length=120, blank=True, verbose_name="Valor de categoría",
        help_text="Valor exacto que identifica este tipo en el campo anterior "
                  "(ej.: 'NEUMATICOS'). Vacío = sin filtro.",
    )

    metodo_busqueda = models.CharField(
        max_length=20, choices=METODO_CHOICES, default=METODO_CODIGO,
        verbose_name="Método de búsqueda",
    )
    ayuda_busqueda = models.TextField(
        blank=True, verbose_name="Instrucciones de búsqueda",
        help_text="Orientación para el usuario: ejemplos de códigos, formatos, "
                  "qué escribir en cada campo. Se muestra como nota dentro del modal.",
    )

    consulta_sql = models.TextField(
        blank=True, verbose_name="Consulta SQL personalizada",
        help_text=(
            "Consulta SQL con los placeholders :q1, :q2 y/o :q3 que serán "
            "reemplazados por los valores del buscador (código, nombre, detalle). "
            "Las columnas de resultado DEBEN llamarse: codigo, nombre, "
            "dependencia, cantidad. Opcionalmente: extra1, extra2, extra3. "
            "Solo se permiten consultas SELECT (solo lectura)."
        ),
    )
    usar_consulta_personalizada = models.BooleanField(
        default=False, verbose_name="Usar consulta personalizada",
        help_text="Si está activo, se ejecuta la consulta SQL de arriba en "
                  "vez de la búsqueda generada automáticamente.",
    )

    orden = models.IntegerField(default=0, verbose_name="Orden")
    activo = models.BooleanField(default=True, verbose_name="Activa")

    panels = [
        ObjectList(
            [
                MultiFieldPanel(
                    [
                        FieldPanel("nombre"),
                        FieldPanel("slug"),
                        FieldPanel("descripcion"),
                        FieldPanel("imagen"),
                    ],
                    heading="Identificación",
                ),
            ],
            heading="Identificación",
        ),
        ObjectList(
            [
                MultiFieldPanel(
                    [
                        FieldPanel("tabla_origen"),
                        FieldPanel("campo_codigo"),
                        FieldPanel("campo_nombre"),
                        FieldPanel("campo_extra1"),
                        FieldPanel("campo_extra2"),
                        FieldPanel("campo_extra3"),
                        FieldPanel("campo_categoria"),
                        FieldPanel("valor_categoria"),
                    ],
                    heading="Campos del ERP",
                ),
            ],
            heading="Campos ERP",
        ),
        ObjectList(
            [
                MultiFieldPanel(
                    [
                        FieldPanel("metodo_busqueda"),
                        FieldPanel(
                            "ayuda_busqueda",
                            help_text="Escribí acá los ejemplos y la orientación que verá el "
                                      "usuario al abrir el buscador de esta categoría.",
                        ),
                    ],
                    heading="Búsqueda",
                ),
            ],
            heading="Búsqueda",
        ),
        ObjectList(
            [
                HelpPanel(
                    heading="Consulta SQL personalizada",
                    content="""
Escribí una consulta SELECT con los placeholders <code>:q1</code>, <code>:q2</code> y/o <code>:q3</code>.
Estos serán reemplazados por los valores del buscador:<br>
• <code>:q1</code> = Código<br>
• <code>:q2</code> = Nombre<br>
• <code>:q3</code> = Detalle<br><br>
Las columnas de resultado deben llamarse exactamente: <code>codigo</code>, <code>nombre</code>,
<code>dependencia</code>, <code>cantidad</code>. Opcionalmente: <code>extra1</code>, <code>extra2</code>, <code>extra3</code>.<br><br>
<strong>Ejemplo:</strong><br>
<pre style="background:#f8f8f8;padding:10px;border-radius:6px;font-size:13px;overflow-x:auto;">SELECT
  p.codigo,
  p.nombre,
  p.marca AS extra1,
  COALESCE(d.nombre, s.codigo_dependencia) AS dependencia,
  COALESCE(s.cantidad, 0) AS cantidad
FROM productes AS p
LEFT JOIN stock AS s ON s.codigo_producto::text = p.codigo::text
LEFT JOIN dependencias AS d ON d.codigo::text = s.codigo_dependencia::text
WHERE p.categoria = :q1
  AND p.nombre ILIKE '%' || :q2 || '%'
LIMIT 50</pre>
""",
                ),
                MultiFieldPanel(
                    [
                        FieldPanel("usar_consulta_personalizada"),
                        FieldPanel(
                            "consulta_sql",
                            help_text="SELECT con placeholders :q1, :q2, :q3. "
                                      "Columnas requeridas: codigo, nombre, dependencia, cantidad.",
                        ),
                    ],
                    heading="Consulta personalizada",
                ),
            ],
            heading="Consulta SQL",
        ),
        ObjectList(
            [
                MultiFieldPanel(
                    [
                        FieldPanel("orden"),
                        FieldPanel("activo"),
                    ],
                    heading="Estado",
                ),
            ],
            heading="Estado",
        ),
    ]

    EDIT_HANDLER = TabbedInterface(
        ObjectList(panels[0].children, heading="Identificación"),
        ObjectList(panels[1].children, heading="Campos ERP"),
        ObjectList(panels[2].children, heading="Búsqueda"),
        ObjectList(panels[3].children, heading="Consulta SQL"),
        ObjectList(panels[4].children, heading="Estado"),
    )

    class Meta:
        verbose_name = "Categoría de productos ERP"
        verbose_name_plural = "Categorías de productos ERP"
        ordering = ["orden", "nombre"]

    def __str__(self):
        return self.nombre

    def save(self, *args, **kwargs):
        """Autogenera el slug si no se indicó uno."""
        if not self.slug:
            from django.utils.text import slugify  # noqa: F401

            base = slugify(self.nombre)[:160]
            self.slug = base
            qs = type(self).objects.all()
            if self.pk:
                qs = qs.exclude(pk=self.pk)
            i = 1
            while qs.filter(slug=self.slug).exists():
                self.slug = f"{base}-{i}"
                i += 1
        super().save(*args, **kwargs)

    @property
    def etiqueta_busqueda(self):
        """Etiqueta legible del método de búsqueda."""
        return dict(self.METODO_CHOICES).get(self.metodo_busqueda, self.metodo_busqueda)


# ---------------------------------------------------------------------------
# Página pública del catálogo
# ---------------------------------------------------------------------------
class CatalogoERPPage(Page):
    """Grid de categorías activas; cada una abre un modal de consulta ERP."""

    introduccion = RichTextField(blank=True, verbose_name="Introducción")

    content_panels = Page.content_panels + [
        FieldPanel("introduccion"),
    ]

    max_count = 1
    parent_page_types = [
        "home.HomePage",
        "core.GenericPage",
        "automotive.AutomotivePage",
    ]
    subpage_types = []
    template = "catalogo_erp/catalogo.html"

    class Meta:
        verbose_name = "Catálogo ERP"
        verbose_name_plural = "Catálogo ERP"

    # -- Caché de categorías (no se cachean resultados ERP) ---------------------
    @classmethod
    def categorias_activas(cls):
        """Categorías activas cacheadas ~5 minutos."""
        cats = cache.get(CACHE_CATEGORIAS)
        if cats is None:
            cats = list(
                CategoriaProductoERP.objects.filter(activo=True)
                .select_related("imagen")
                .order_by("orden", "nombre")
            )
            cache.set(CACHE_CATEGORIAS, cats, 300)
        return cats

    # -- Provincia por defecto para el buscador ---------------------------------
    @classmethod
    def provincia_por_defecto(cls):
        """Provincia sugerida al abrir el buscador (La Habana si tiene UEBs)."""
        from apps.catalogo_erp.provincias import provincia_por_defecto

        return provincia_por_defecto()

    def get_context(self, request, *args, **kwargs):
        from apps.catalogo_erp.provincias import opciones_provincia

        context = super().get_context(request, *args, **kwargs)
        context["categorias"] = self.categorias_activas()
        context["provincias"] = opciones_provincia()
        context["provincia_actual"] = self.provincia_por_defecto()
        return context
