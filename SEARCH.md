# BUSCADOR DEL NAVBAR — Modal de resultados AJAX

Buscador con expansión/colapso en el navbar y modal de resultados sin recargar
la página. JavaScript vanilla, compatible con el tema claro/oscuro y accesible.

## Archivos

| Archivo | Rol |
| --- | --- |
| `static/js/search.js` | Toggle, modal, AJAX, caché, focus trap, `AbortController`, delegación de eventos. |
| `static/css/search.css` | Animación de expansión y estilos del modal (usa variables de `theme.css`). |
| `templates/includes/search_modal.html` | Markup del modal (una sola vez por layout). |
| `apps/core/views.py` → `api_buscar` | Endpoint JSON `/api/buscar/?q=…`. |
| `config/urls.py` | Ruta `path("api/buscar/", api_buscar, name="api_buscar")`. |

Marcado del buscador (en `templates/includes/navbar.html` y en el navbar de
`base_automotive.html`). Los `data-*` son los que engancha `search.js`:

```html
<div class="navbar-sa__search" data-navbar-search>
  <button class="navbar-sa__search-toggle" data-search-toggle type="button"
          aria-label="Buscar" aria-expanded="false" aria-controls="searchForm">
    <i class="bi bi-search" aria-hidden="true"></i>
  </button>
  <form class="navbar-sa__search-form" id="searchForm" data-search-form
        role="search" aria-hidden="true" action="/buscar/" method="get">
    <input type="search" name="q" class="navbar-sa__search-input" data-search-input
           placeholder="Buscar en el sitio..." autocomplete="off" maxlength="200"
           aria-label="Buscar en el sitio">
    <button type="submit" class="navbar-sa__search-submit" aria-label="Ejecutar búsqueda">
      <i class="bi bi-arrow-right" aria-hidden="true"></i>
    </button>
    <button type="button" class="navbar-sa__search-close" data-search-close aria-label="Cerrar buscador">
      <i class="bi bi-x-lg" aria-hidden="true"></i>
    </button>
  </form>
</div>
```

## Integración en un layout nuevo

1. En el `<head>`, tras `theme.css`:
   ```html
   <link rel="stylesheet" href="{% static 'css/search.css' %}">
   ```
2. Antes de cerrar `</body>`, junto a los demás scripts:
   ```html
   {% include "includes/search_modal.html" %}
   <script src="{% static 'js/search.js' %}" defer></script>
   ```
3. El buscador del navbar debe tener el marcado de arriba (los `data-*`).
   La búsqueda del drawer móvil usa `data-drawer-search` en el `<form>` y
   `search.js` la engancha automáticamente.

No se necesita jQuery ni otra librería. `search.js` se carga con `defer`.

## Endpoint `GET /api/buscar/?q=…`

- Busca con `Page.objects.live().public().search(q)` (backend de Wagtail).
- Incluye novedades, informaciones, foro, catálogo y páginas — el `type` se
  deriva del `app_label` de la página.
- Limita la consulta a **200 caracteres** y devuelve como máximo **10** resultados.
- `has_more: true` indica que hay más de 10 resultados (habilita “Ver todos”).
- Cada resultado incluye imagen optimizada como thumbnail `fill-120x90`
  (`image_rendition`) cuando la página tiene imagen (`imagen`, `header_image` u `og_image`).

### Ejemplo con resultados

```json
{
  "query": "aceite",
  "count": 2,
  "has_more": false,
  "results": [
    {
      "title": "Aceite sintético 5W-30: ¿cada cuánto cambiarlo?",
      "excerpt": "Recomendamos cambiar el aceite cada 8.000-10.000 km o 6 meses…",
      "url": "/foro/aceite-sintetico-5w-30-cada-cuanto-cambiarlo/",
      "type": "foro",
      "image": null
    },
    {
      "title": "Llegan nuevos repuestos originales al catálogo",
      "excerpt": "Filtros, pastillas y bujías originales de primeras marcas ya en stock.",
      "url": "/informaciones/llegan-nuevos-repuestos-originales-al-cat%C3%A1logo/",
      "type": "información",
      "image": "/media/images/gallery-6.2e16d0ba.fill-120x90.jpg"
    }
  ]
}
```

### Ejemplo sin resultados

```json
{ "query": "xyzzy_inexistente", "count": 0, "has_more": false, "results": [] }
```

Valores de `type`: `novedad`, `información`, `producto`, `página`, `foro`, `mapa`.

## Comportamiento

- **Lupa:** expande el formulario con `max-width`/`opacidad`, enfoca el input y
  pone `aria-expanded="true"`.
- **Clic fuera** (`event.target.closest('[data-navbar-search]')`): comprime,
  limpia el input y devuelve el foco a la lupa.
- **Escape:** cierra el buscador y el modal.
- **Botón X:** colapsa el formulario.
- **Enviar (Enter o botón):** `preventDefault()` y abre el modal con spinner;
  el resultado se pide a `/api/buscar/?q=…` con `AbortController` (cancela la
  petición anterior) y caché por término.
- **Modal:** `role="dialog"`, `aria-modal="true"`, cierre por X / clic en el
  overlay / Escape; bloquea el scroll del `body`; focus trap con `Tab`; al
  cerrar devuelve el foco al elemento que lo abrió.
- **Refinar:** el input dentro del modal busca con **debounce de 400 ms** sin
  cerrarlo. El número de resultados se anuncia con `aria-live="polite"`.
- **Resultado:** cerrado el modal, navega a la URL del `<a>`.
- **“Ver todos”**: enlaza a `/buscar/?q=…` y solo aparece si `has_more` es `true`.

## Accesibilidad

`aria-expanded` en el toggle · `aria-hidden` en el formulario colapsado ·
`role="dialog"` + `aria-modal="true"` · `aria-label` en todos los botones de
icono · `aria-live="polite"` para el conteo · foco visible y navegación con
Tab/Enter/Escape · `prefers-reduced-motion` desactiva las animaciones.

## Responsive

En móvil el buscador del navbar se oculta y la búsqueda vive en el drawer
(`data-drawer-search`). El modal pasa a pantalla completa en `< 576px` y los
resultados se apilan en una columna.

## Rendimiento

JS con `defer`, caché por término, `AbortController`, tope de 10 resultados y
miniaturas con `image_rendition`. El endpoint `api_buscar` es de solo lectura
(`GET`) y nunca lanza 500: ante un fallo del índice devuelve `results: []`.
