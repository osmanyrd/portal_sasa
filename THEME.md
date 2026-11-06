# THEME — Sistema de tema claro/oscuro

Sistema de tema para **Servicios Automotores S.A**. Driver: el atributo `data-theme` en el elemento `<html>`. Paleta institucional: blanco / negro / rojo `#E63946`.

## Tokens

Toda la paleta vive como variables CSS en `static/css/theme.css`:

- **Modo claro**: en `:root` (por defecto).
- **Modo oscuro**: dentro de `[data-theme="dark"]`.

| Variable            | Claro                     | Oscuro                        |
| ------------------- | ------------------------- | ----------------------------- |
| `--bg-primary`      | `#FFFFFF`                 | `#121212`                     |
| `--bg-secondary`    | `#F5F5F5`                 | `#1E1E1E`                     |
| `--bg-navbar`       | `#FFFFFF`                 | `#000000`                     |
| `--text-primary`    | `#000000`                 | `#FFFFFF`                     |
| `--text-secondary`  | `#444444`                 | `#CCCCCC`                     |
| `--text-navbar`     | `#000000`                 | `#FFFFFF`                     |
| `--icon-navbar`     | `#000000`                 | `#FFFFFF`                     |
| `--border-color`    | `#E0E0E0`                 | `#333333`                     |
| `--accent`          | `#E63946`                 | `#E63946`                     |
| `--accent-hover`    | `#B71C2C`                 | `#FF5566`                     |
| `--shadow-color`    | `rgba(0,0,0,0.08)`        | `rgba(255,255,255,0.05)`      |

Los tokens nuevos se suman (no reemplazan) a las variables existentes del proyecto (`--accent`, `--navbar-*`, `--brand`, ...). `theme.css` se carga **al final** de `<head>` y gana en cascada solo donde lo necesita.

## Cómo se aplica el tema

### 1. Anti-flash en `<head>`

En `templates/base.html` y `apps/automotive/templates/automotive/base_automotive.html` hay un script **inline** (antes de que cargue el CSS) que:

```html
<script>
  (function () {
    try {
      var t = localStorage.getItem('theme')
        || localStorage.getItem('sa-theme')
        || (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
      document.documentElement.setAttribute('data-theme', t === 'light' ? 'light' : 'dark');
      document.documentElement.setAttribute('data-bs-theme', t === 'light' ? 'light' : 'dark');
    } catch (e) { /* fallback: claro */ }
  })();
</script>
```

- Lee la clave `theme` de `localStorage`.
- **Migración**: si todavía no existe `theme`, lee la clave legada `sa-theme`.
- Sin preferencia guardada → sigue `prefers-color-scheme` del sistema.
- Pinta el tema **antes** del primer render para evitar parpadeo (FOUC).

> `data-bs-theme` se mantiene sincronizado para que Bootstrap y algunos CSS heredados (`html[data-bs-theme="dark"]`, `body.dark-mode`, `survey_interactive.css`) sigan funcionando sin tocarlos.

### 2. Toggle del navbar

Botón redondo sol/luna en ambos navbars (`navbar-sa__theme`), con:

- `aria-label="Cambiar tema"`
- `aria-pressed` (refleja si el modo oscuro está activo)
- Icono: sol en claro, luna en oscuro.

Lo controla `static/js/theme.js` (cargado con `defer`):

- **Escribe/lee** `localStorage` clave `theme` (y mantiene `sa-theme` sincronizada por migración).
- **Aplica**: `data-theme`, `data-bs-theme` y la clase `body.dark-mode`.
- **Reacciona** a `prefers-color-scheme` solo cuando el usuario no tiene preferencia guardada.

Implementación sugerida para el botón (ya presente en el proyecto):

```html
<button class="navbar-sa__theme" type="button" data-theme-toggle
        aria-label="Cambiar tema" aria-pressed="false" title="Modo claro/oscuro">
  <i class="bi bi-sun-fill navbar-sa__theme-sun" aria-hidden="true"></i>
  <i class="bi bi-moon-stars-fill navbar-sa__theme-moon" aria-hidden="true"></i>
</button>
```

### 3. Logo

El logo de la imagen se muestra **rojo en ambos temas** vía filtro CSS en `theme.css`:

```css
.navbar-sa__logo-img,
.navbar-sa__drawer-logo {
  filter: sepia(1) saturate(6) hue-rotate(318deg) brightness(.95) contrast(1.02);
}
```

El filtro tiñe de rojo la forma del logo manteniendo la transparencia, sin depender del color original del asset.

## Cobertura

Adaptados a oscuro (en `theme.css`, sección 6):

- Navbar (adaptativo: blanco en claro / negro en oscuro) + drawer fijo de marca.
- Foro: tarjetas, temas, mensajes, reglas, formulario de tema nuevo.
- Catálogo ERP: categorías, producto, resumen, ayuda.
- Mapa de dependencias: panel, tarjetas `dep-card`, tooltip, leyenda.
- Mapa modal flotante (`mapa_modal.css`).
- Informaciones: campana/panel, chips, listado `info-card`, toast.
- Usuarios: `auth-card`, perfil.
- Encuestas: panel de campana, panel flotante, modal, listado.
- PWA: botón "Instalar app".
- Formularios Bootstrap (`form-control`/`form-select`), inputs genéricos.

Módulos con dark propio que **ya existían** (no se duplican): `automotive.css`, `automotive-destacados.css`, `chatbot.css`, `survey_interactive.css` (usan `body.dark-mode` / `html[data-bs-theme="dark"]`, compatibles porque el script sincroniza ambos).

## Reglas para componentes nuevos

Al crear un componente:

1. Nunca escribir colores en duro. Usar los tokens (`--bg-primary`, `--text-primary`, `--accent`, `--border-color`, ...) o, si es específico de un módulo, definir la variable en `:root` y su override en `[data-theme="dark"]`.
2. Para superficies tipo tarjeta: `background: var(--card-bg); border-color: var(--border-color);`.
3. Texto secundario: `var(--text-secondary)`.
4. Agregar el selector + sus overrides oscuros en `theme.css` si el módulo no tiene dark propio.
5. **Accesibilidad AA**: no bajar de `#444` sobre fondo claro ni de `#CCC` sobre `#121212` para texto normal.
6. No añadir transiciones que dupliquen; el bloque `@media (prefers-reduced-motion: reduce)` desactiva todas al pedido del usuario.
7. Verificar en ambos temas y en móvil/drawer.

## Verificación

- Claro: `data-theme="light"`, navbar blanco, logo rojo, texto negro.
- Oscuro: `data-theme="dark"`, navbar negro, logo rojo, texto blanco, tarjetas `#1E1E1E`.
- Toggle: cambia al instante, persiste en `localStorage.theme`, no parpadea al recargar.
- Preferencia de sistema: se sigue si el usuario nunca tocó el toggle.