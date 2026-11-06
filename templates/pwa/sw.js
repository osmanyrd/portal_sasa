{% load static %}/*
 * sw.js — Service Worker de Servicios Automotores S.A
 *
 * Estrategias:
 *  - PRECACHÉ: recursos estáticos críticos al instalar (instalación offline).
 *  - NAVEGACIÓN: network-first con fallback a caché y, en último caso,
 *    a la página offline.
 *  - ESTÁTICOS e IMÁGENES: cache-first con actualización en segundo plano
 *    (stale-while-revalidate).
 *
 * Seguridad/privacidad:
 *  - Se ignoran las rutas privadas (/cms/, /django-admin/, /cuenta/, /api/…)
 *    y cualquier petición con query string, para no cachear datos personales.
 *  - El service worker solo es aplicable sobre HTTPS o localhost (lo impone
 *    el propio navegador).
 *
 * Actualización: al cambiar VERSION, install() reprecachea y skipWaiting()
 * toma el control sin esperar a cerrar la pestaña.
 */

const VERSION = 'v1.2.1';
const CACHES = {
  assets: `pwa-assets-${VERSION}`,
  pages: `pwa-pages-${VERSION}`,
  images: `pwa-images-${VERSION}`,
};
const STATIC_URL = '{{ STATIC_URL }}';

/* Recursos críticos para funcionar sin conexión. Se generan con la etiqueta
   "static" del proyecto, así las URLs son siempre las correctas. */
const PRECACHE = [
  `{% static 'vendor/css/google-fonts.css' %}`,
  `{% static 'vendor/css/bootstrap.min.css' %}`,
  `{% static 'vendor/css/bootstrap-icons.min.css' %}`,
  `{% static 'vendor/css/leaflet.css' %}`,
  `{% static 'automotive/css/automotive.css' %}`,
  `{% static 'automotive/css/automotive-destacados.css' %}`,
  `{% static 'chatbot/css/chatbot.css' %}`,
  `{% static 'surveys/css/surveys.css' %}`,
  `{% static 'mapa/css/mapa_modal.css' %}`,
  `{% static 'informaciones/css/informaciones.css' %}`,
  `{% static 'usuarios/css/usuarios.css' %}`,
  `{% static 'css/styles.css' %}`,
  `{% static 'css/navbar-redesign.css' %}`,
  `{% static 'vendor/js/bootstrap.bundle.min.js' %}`,
  `{% static 'vendor/js/leaflet.js' %}`,
  `{% static 'vendor/js/htmx.min.js' %}`,
  `{% static 'automotive/js/automotive.js' %}`,
  `{% static 'chatbot/js/chatbot.js' %}`,
  `{% static 'surveys/js/surveys.js' %}`,
  `{% static 'informaciones/js/informaciones.js' %}`,
  `{% static 'usuarios/js/usuarios.js' %}`,
  `{% static 'js/main.js' %}`,
  `{% static 'js/navbar.js' %}`,
  `{% static 'js/theme.js' %}`,
  `{% static 'pwa/pwa.js' %}`,
  `{% static 'icons/icon-192.png' %}`,
  `{% static 'icons/icon-512.png' %}`,
  `{% url 'pwa_offline' %}`,
];

/* ─────────── INSTALAR ─────────── */
self.addEventListener('install', (event) => {
  event.waitUntil((async () => {
    const cache = await caches.open(CACHES.assets);
    // add() individual con captura de errores: una URL 404 no aborta la instalación.
    await Promise.all(PRECACHE.map((url) =>
      cache.add(url).catch(() => console.warn('[SW] precaché omitido:', url))
    ));
    await self.skipWaiting();
  })());
});

/* ─────────── ACTIVAR: limpiar versiones viejas ─────────── */
self.addEventListener('activate', (event) => {
  event.waitUntil((async () => {
    const keep = new Set(Object.values(CACHES));
    const keys = await caches.keys();
    await Promise.all(
      keys.filter((key) => !keep.has(key)).map((key) => caches.delete(key))
    );
    await self.clients.claim();
  })());
});

/* ─────────── FETCH ─────────── */
self.addEventListener('fetch', (event) => {
  const req = event.request;
  if (req.method !== 'GET') return; // nunca cachear POST/PUT/DELETE

  const url = new URL(req.url);
  if (url.origin !== self.location.origin) return; // solo mismo origen

  // Rutas privadas o dinámicas: pasar por red, nunca cachear.
  if (/^\/(cms|django-admin|admin|cuenta|o\/|api|documentos|contacto|encuestas)/.test(url.pathname)) return;
  if (url.search) return;

  // Navegación (páginas HTML): network-first con fallback a offline.
  if (req.mode === 'navigate') {
    event.respondWith(networkFirst(req));
    return;
  }

  // Estáticos e imágenes: cache-first + revalidación en segundo plano.
  const esImagen = /\.(png|jpe?g|webp|gif|avif|svg|ico|woff2?)$/i.test(url.pathname);
  const cacheName = esImagen ? CACHES.images : CACHES.assets;
  if (url.pathname.startsWith(STATIC_URL) || esImagen) {
    event.respondWith(staleWhileRevalidate(req, cacheName));
  }
});

async function networkFirst(req) {
  const cache = await caches.open(CACHES.pages);
  try {
    const fresh = await fetch(req);
    if (fresh && fresh.ok) cache.put(req, fresh.clone());
    return fresh;
  } catch (err) {
    const cached = await cache.match(req);
    if (cached) return cached;
    const offline = await caches.match(`{% url 'pwa_offline' %}`);
    if (offline) return offline;
    return new Response('Sin conexión', {
      status: 503,
      headers: { 'Content-Type': 'text/plain; charset=utf-8' },
    });
  }
}

async function staleWhileRevalidate(req, cacheName) {
  const cache = await caches.open(cacheName);
  const cached = await cache.match(req);
  // Actualización en segundo plano (no bloquea la respuesta).
  fetch(req).then((res) => {
    if (res && res.ok) cache.put(req, res.clone());
  }).catch(() => {});
  return cached || fetch(req);
}

/* ─────────── NOTIFICACIONES PUSH (hook preparado) ───────────
   Integración prevista con servicio de terceros (OneSignal / FCM).
   Activar cuando el backend envíe suscripciones:
   1) en el cliente: navegador.subscribePush(subscription) → POST a API.
   2) en el SW: conviértalos en notificaciones.

self.addEventListener('push', (event) => {
  const data = event.data ? event.data.json() : { title: 'Novedades', body: '' };
  event.waitUntil(
    self.registration.showNotification(data.title, {
      body: data.body,
      icon: `${STATIC_URL}icons/icon-192.png`,
      badge: `${STATIC_URL}icons/icon-192.png`,
      data: { url: data.url || '/' },
    })
  );
});

self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  event.waitUntil(clients.openWindow(event.notification.data.url || '/'));
});
*/