# README_BACKEND

Arquitectura, módulos, optimizaciones y tareas de mantenimiento del backend de
**Servicios Automotores S.A** (Wagtail 6 / Django 5).

---

## 1. Descripción de las apps (backend)

| App | Rol | Estado |
|-----|-----|--------|
| `core` | Páginas base, `SiteSettings`, `BannerCarrusel`, `Tema` (temporadas), `ContactSubmission`, formulario de contacto | Activa |
| `automotive` | Página raíz del sitio (`AutomotivePage`), portada con carrusel/hero/servicios/galería/ubicación | Activa |
| `informaciones` | **Novedades** y **Informaciones** (listados, carrusel, ticker), snippets `InformacionCinta`/`ConfiguracionCinta` | Activa |
| `foro` | Foro con categorías, temas (Page), respuestas y panel de moderación | Activa |
| `catalogo_erp` | Catálogo de productos integrado con ERP externo (psycopg2), cifrado Fernet | Activa |
| `mapa` | Mapa de dependencias/sucursales (Leaflet), provinceas, configuración | Activa |
| `surveys` | Encuestas con preguntas/opciones/votaciones y exportación CSV | Activa |
| `usuarios` | Perfiles (natural/jurídica), registro, sesión, integración SASA, sistema externo | Activa |
| `chatbot` | Chatbot con documentos de conocimiento y registro de conversaciones | Activa |
| `home` | `HomePage` institucional genérica (plantilla heredada/sin usar en la raíz) | Marginal |

### Eliminadas (verificados como código muerto)

Las apps **`blog`** y **`services`** fueron eliminadas (tablas, migraciones y código):
- El sitio activo (`AutomotivePage`) no las usaba en templates, urls ni menús.
- `informaciones` (Novedad) reemplaza a `blog`; el bloque `ServicesBlock` de `automotive` reemplaza a `services`.
- Se verificó que no había contenido real: 0 blog posts, 0 service pages, 1 categoría demo vacía.

Están en `INSTALLED_APPS` y tienen tablas creadas. **No se eliminaron en esta iteración**
por riesgo de pérdida de datos; ver "Cómo retomar" para el procedimiento seguro.

---

## 2. Administración de Wagtail (mejoras añadidas)

Todos los snippets usan `SnippetViewSet` (menú **Snippets** en el admin):

| Snippet | App | list_display | list_filter | search_fields |
|---------|-----|--------------|-------------|---------------|
| `ContactSubmission` | core | name, email, phone, created_at | created_at | name, email, phone, message |
| `Tema` | core | nombre, fecha_inicio, fecha_fin, activo | activo | nombre |
| `BannerCarrusel` | core | titulo, orden, activo | activo | titulo, subtitulo |
| `DocumentoConocimiento` | chatbot | titulo, categoria, fuente_titulo, activo, creado | categoria, activo | titulo, contenido, fuente_titulo |
| `RegistroConversacion` | chatbot | pregunta_corta, puntuacion_similitud, respondido, session_key, creado | respondido, creado | pregunta, respuesta, session_key |
| `PerfilUsuario` | usuarios | display_name, user, tipo_usuario, activo, fecha_registro | tipo_usuario, activo | user__username, user__email, nombre_empresa, cif_nit |

*(Ya existían): `CategoriaForo`, `ConfiguracionERP`, `CategoriaProductoERP`, `Provincia`,
`Dependencia`, `Encuesta`, `InformacionCinta`, `ConfiguracionSistemaExterno`.*

Archivos: `apps/core/wagtail_hooks.py`, `apps/chatbot/wagtail_hooks.py`,
`apps/usuarios/wagtail_hooks.py`. Se retiraron los `register_snippet` planos de los modelos.

---

## 3. Optimización de consultas aplicada

- `apps/informaciones/models.py`: en las páginas de listado de **Novedades** e **Informaciones**
  se añadió `.select_related("imagen")` para evitar N+1 en el renderizado de tarjetas.
- El foro (moderación) ya usaba `select_related("categoria", "autor")`.
- La portada (carrusel) usa querysets acotados (`[:6]`, `[:4]`).

### Índices de base de datos (`db_index=True`)

Añadidos en campos de filtro/ordenamiento frecuentes:

| Modelo | Campos indexados | Prioridad |
|--------|-----------------|-----------|
| `Tema` (core) | `activo`, `fecha_inicio`, `fecha_fin` | Crítica (cada request) |
| `ContenidoPublicable` (informaciones) | `tipo`, `fecha_publicacion`, `fecha_expiracion`, `activo` | Alta |
| `Novedad` (informaciones) | `aparecer_en_carrusel` | Alta (portada) |
| `InformacionCinta` (informaciones) | `activo`, `fecha_inicio`, `fecha_fin` | Media (cinta) |
| `TemaForo` (foro) | `estado`, `fecha_creacion` | Alta (listado) |
| `RespuestaForo` (foro) | `aprobado` | Alta (detalle tema) |
| `CategoriaForo` (foro) | `activo` | Baja |
| `Encuesta` (surveys) | `activa`, `tipo_encuesta`, `fecha_inicio`, `mostrar_modal`, `mostrar_modal_primera_visita` | Alta (template tag cada request) |
| `DocumentoConocimiento` (chatbot) | `activo` | Baja |
| `PerfilUsuario` (usuarios) | `tipo_usuario` | Media |
| `BannerCarrusel` (core) | `activo` | Media |

### Caché

- **Context processor `tema_activo`**: cache de bajo nivel (5 min) para evitar query en cada request.
- **Carrusel de portada**: fragment cache (`{% cache 300 %}`) en el HTML del hero-carousel.
- Framework: `django.core.cache` (Memcached o LocalMemoryCache según `CACHES` setting).

---

## 4. Seguridad

- **Password/env de conexión ERP** (`catalogo_erp`): cifrado **Fernet** (`cryptography`) con
  fallback de biblioteca estándar (PBKDF2-HMAC-SHA256 + HMAC-CTR), clave derivada de
  `SECRET_KEY`. Ya existía.
- **`ConfiguracionSistemaExterno.clave_api`** (usuarios): se añadió `save()` que cifra la clave
  en reposo y propiedad `clave_api_plana` para descifrar solo al usar (`apps/usuarios/models.py`).
- Vistas de usuario protegidas con `@login_required`/`@staff_member_required`.
- CSRF activo en formularios; entradas sanitizadas por el ORM (sin SQL raw).

---

## 5. Migraciones generadas

Aplicadas (pendientes de sesiones anteriores):
- `foro.0002_alter_foroindexpage_allow_anonymous`
- `informaciones.0006_alter_novedad_tipo` (nuevos tipos: `empleo`, `licitacion`)

---

## 6. Cómo aplicar / correr

```powershell
$py = "D:\SITE\venv\Scripts\python.exe"
$env:DJANGO_SETTINGS_MODULE="config.settings.dev"
$env:DB_ENGINE="sqlite"
$env:DJANGO_DEBUG="True"
$env:ALLOWED_HOSTS="localhost,127.0.0.1,*"

& $py manage.py makemigrations <app> --name <grupo>
& $py manage.py migrate
& $py manage.py check
```

Reinicio del servidor local (matar listener puerto 8000 y relanzar con `Start-Process`).

No definas `DJANGO_SECRET_KEY` al correr en local: la contraseña del ERP queda
cifrada con la clave de `.env` y, si se cambia, el catálogo deja de descifrarla.
Hay que matar **todos** los procesos `runserver` viejos (el padre del autoreload
respawna hijos y sigue ocupando el 8000), si no el server viejo queda sirviendo
con la `SECRET_KEY` anterior.

---

## 7. Pendiente / Cómo retomar

1. **Cache avanzado**: evaluar `django-cachalot` para consultas pesadas (catálogo ERP, encuestas).
2. **Cache invalidación**: al editar Tema/BannerCarrusel, limpiar `cache.delete("tema_activo_context")` desde signals de post_save.
3. **Rate limiting**: añadir throttling a la API de chatbot y formulario de contacto.

---

## 8. Notas de arquitectura

- Snippets rich: `SnippetViewSet` (Wagtail 6, `wagtail.snippets.views.snippets`).
- Registros de hooks se colocan en `wigtail_hooks.py` de cada app (auto-cargados por Wagtail).
- No hay `modeladmin`; todo el CRUD de datos auxiliares usa Snippets.
- JavaScript/CSS: ver `README_FRONTEND.md`.