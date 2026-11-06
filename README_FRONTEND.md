# README_FRONTEND

Guía de estilo, arquitectura y decisiones de frontend de **Servicios Automotores S.A** (Wagtail 5+ / Django 4+, plataforma Windows).

## 1. Arquitectura de estilos y scripts

### CSS
Cada módulo tiene su propia hoja dentro de su app (`apps/*/static/*/css/`). La hoja global de la plantilla servida (`base_automotive.html`) es:

- `apps/automotive/static/automotive/css/automotive.css` — estilos base y componentes globales.
- Hojas por módulo: `informaciones.css`, `mapa_modal.css`, `surveys.css`, `usuarios.css`, `catalog-erp.css`, `foro.css`, `chatbot.css`.
- Componentes específicos de página (carrusel, destacados) se inyectan vía `{% block extra_css %}` en la plantilla hija.

### JavaScript
Todos los scripts usan **IIFE + `'use strict'`** (sin jQuery salvo Bootstrap). Al final del `<body>` se cargan con `defer` (ver `base_automotive.html`):

- Vendors: `bootstrap.bundle.min.js`, `leaflet.js`.
- Propios: `automotive.js`, `informaciones.js`, `surveys.js`, `usuarios.js`.
- El JS del carrusel de inicio está embebido en `automotive_page.html` (vanilla, auto-contenido).

> Regla: no introducir dependencias adicionales. Todo es ES5-compatible (var, funciones) para máxima compatibilidad, aunque se favorezca Arrow Functions en código nuevo.

## 2. Variables CSS (Custom Properties)

Centralizadas en `:root` de `automotive.css`:

```css
--accent: #E63946;      /* rojo corporativo */
--accent-dark: #C1121F;
--dark: #000000;
--dark-2: #222222;
--gray: #F5F5F5;
--gray-mid: #6C757D;
--gray-light: #E9ECEF;
--radius: .75rem;
--radius-lg: 1rem;
--shadow, --shadow-lg;
--font-body: 'Inter', system-ui, sans-serif;
--font-heading: 'Montserrat', 'Inter', sans-serif;
--transition: .3s cubic-bezier(.16,1,.3,1);
```

Usar siempre estas variables en componentes nuevos. No hardcodear colores/radii salvo casos aislados.

## 3. Metodología y convenciones

- **Nombrado**: componentes con prefijo de módulo (`hero-carousel__`, `nv-card`, `service-card`, `info-card`, `theme-banner`). Se usa un estilo BEM-ish (`bloque__elemento`, `bloque--modificador`).
- **Mobile-first**: los breakpoints usan `@media (max-width: ...)` (desktop-first heredado); al añadir estilos nuevos priorizar `min-width` (mobile-first).
- **No usar `!important`** salvo para overrides de Bootstrap imprescindibles.
- **Imágenes**: siempre con `{% image %}` + `width`/`height` (evita CLS) y `loading="lazy"` salvo el LCP del hero.

## 4. Paleta y tipografía

- Colores: blanco `#fff`, negro `#000`, rojo `#E63946` (accent).
- Fuentes: `Inter` (cuerpo), `Montserrat` (títulos). Cargadas vía Google Fonts con `preconnect`.

## 5. SEO técnico

En `base_automotive.html` (head):
- `title` y `meta description` por bloque.
- `link rel="canonical"` (auto por URL).
- Open Graph (`og:title/description/url/image/locale/site_name`) + Twitter Card.
- JSON-LD: `AutoRepair` + `BreadcrumbList`.
- `meta theme-color`.
- `robots.txt` (ruta en `config/urls.py`) y `sitemap.xml` (Wagtail).

## 6. Accesibilidad

- `skip-link` → salta al `main#contenido-principal`.
- `:focus-visible` visible en toda interacción.
- `prefers-reduced-motion` desactiva animaciones (carrusel se pausa, hero se detiene, reveal se muestra completo).
- `aria-label` en botones de solo icono, `aria-live` en carrusel/toast.

## 7. Rendimiento

- GZip activado vía `django.middleware.gzip.GZipMiddleware` (verificado con `Accept-Encoding: gzip`).
- Scripts diferidos (`defer`), font-display swap, `preconnect` a Google Fonts.
- Imágenes hero con `srcset` + `sizes` + `fetchpriority="high"`.
- En producción se recomienda servir estáticos con **WhiteNoise** (con `MANIFEST` y compresión) o el servidor web (nginx) con Brotli/gzip. Consultar la sección de Configuración en producción.

## 8. Configuración en producción (compresión y caché)

Agregar a `config/settings/production.py`:

```python
# Para servir estáticos comprimidos y con caché en producción (WhiteNoise):
INSTALLED_APPS.insert(0, "whitenoise.runserver_nostatic")
INSTALLED_APPS.append("whitenoise")
MIDDLEWARE.insert(1, "whitenoise.middleware.WhiteNoiseMiddleware")

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}
WHITENOISE_MAX_AGE = 60 * 60 * 24 * 365  # 1 año para hasheados
```

Con nginx, en el `server`:

```nginx
gzip on;
gzip_types text/css application/javascript application/json image/svg+xml;
gzip_min_length 1024;
gzip_vary on;
location /static/ { expires 1y; add_header Cache-Control "public, immutable"; }
location /media/  { expires 30d; add_header Cache-Control "public, max-age=2592000"; }
```

## 9. Optimizaciones aplicadas

- **SEO**: head completo en `base_automotive.html` (canonical, OG, Twitter, JSON-LD, theme-color).
- **Accesibilidad**: `skip-link`, `main#contenido-principal`, decoración de focus, `defer` en scripts (evita bloqueo del render).
- **Rendimiento**: GZip middleware, `srcset/sizes` + `width/height` + `fetchpriority` en el hero, `loading="lazy"` en el resto.
- **SEO técnico**: `robots.txt` con rutas a no indexar y referencia al `sitemap.xml`.

## 10. Checklist de comprobación (accesibilidad y rendimiento)

- [ ] Contraste ≥ 4.5:1 en textos sobre imágenes (usar overlay oscuro).
- [ ] Navegación completa por teclado (Tab, Shift+Tab, Enter, Esc en modales).
- [ ] Foco visible en todos los elementos interactivos.
- [ ] `aria-label` en botones-icono.
- [ ] Formularios con `label` y mensajes de error asociados (`aria-describedby`).
- [ ] Modales con foco atrapado y cierre con Esc.
- [ ] `prefers-reduced-motion` respetado.
- [ ] LCP < 2.5s, CLS < 0.1 (imágenes con dimensiones, fuentes con `display=swap`).
- [ ] `loading="lazy"` en imágenes no críticas.
- [ ] Un solo `<h1>` por página.
