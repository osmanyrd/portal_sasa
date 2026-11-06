/**
 * pwa.js — Registro del Service Worker y flujo de instalación.
 *
 *  - Registra /sw.js (alcance raíz) con verificación de soporte.
 *  - Captura `beforeinstallprompt` para mostrar el botón "Instalar app"
 *    (Chrome/Edge/Android). Lo oculta cuando la app ya está instalada.
 *  - En iOS (no soporta beforeinstallprompt) muestra un aviso para
 *    "Agregar a pantalla de inicio".
 *  - Prepara el hook de suscripción push (opcional, comentado).
 */
(function () {
  'use strict';

  var SW_PATH = '/sw.js';
  var installBtn = document.getElementById('pwaInstallBtn');
  var iosHint = document.getElementById('pwaIosHint');
  var iosHintClose = iosHint && iosHint.querySelector('[data-pwa-hint-close]');
  var deferredPrompt = null;
  var isIOs = /iPad|iPhone|iPod/.test(navigator.userAgent) && !window.MSStream;

  /* ¿Entorno válido para PWA? (HTTPS u host local). El navegador solo
     permite instalar/registrar SW en contextos seguros. */
  function esContextoSeguro() {
    if (location.protocol === 'https:') return true;
    var host = location.hostname;
    return host === 'localhost' || host === '127.0.0.1' || host.endsWith('.localhost');
  }
  if (!esContextoSeguro()) {
    console.warn('[PWA] La instalación requiere HTTPS. Estás en ' + location.href +
      '. Probá por localhost/127.0.0.1 (dev) o públicá el sitio por HTTPS.');
  }

  /* ¿La app se está ejecutando como instalada? */
  function isStandalone() {
    var mq = window.matchMedia && (
      window.matchMedia('(display-mode: standalone)').matches ||
      window.matchMedia('(display-mode: minimal-ui)').matches
    );
    return !!(mq || navigator.standalone === true);
  }

  /* 1. Registro del Service Worker */
  if ('serviceWorker' in navigator) {
    window.addEventListener('load', function () {
      navigator.serviceWorker.register(SW_PATH, { scope: '/' })
        .then(function (reg) {
          console.info('[PWA] Service Worker registrado. Alcance: ' + reg.scope);
          navigator.serviceWorker.addEventListener('controllerchange', function () {
            console.info('[PWA] El Service Worker ahora controla esta página.');
          });
        })
        .catch(function (err) {
          console.warn('[PWA] No se pudo registrar el Service Worker:', err);
        });
    });
  } else {
    console.warn('[PWA] Este navegador no soporta Service Workers.');
  }

  /* 2. Botón de instalación (beforeinstallprompt) */
  window.addEventListener('beforeinstallprompt', function (e) {
    // El navegador decide cuándo mostrarlo; nosotros lo diferimos.
    e.preventDefault();
    deferredPrompt = e;
    if (installBtn && !isStandalone()) installBtn.hidden = false;
  });

  if (installBtn) {
    installBtn.addEventListener('click', function () {
      if (!deferredPrompt) return;
      deferredPrompt.prompt();
      deferredPrompt.userChoice.then(function (choice) {
        if (choice.outcome === 'accepted') {
          installBtn.hidden = true;
        }
        deferredPrompt = null;
      });
    });
    if (isStandalone()) installBtn.hidden = true;
  }

  window.addEventListener('appinstalled', function () {
    if (installBtn) installBtn.hidden = true;
    if (iosHint) iosHint.hidden = true;
  });

  /* 3. Aviso para iOS: "Compartir → Añadir a pantalla de inicio" */
  if (isIOs && !isStandalone() && iosHint) {
    setTimeout(function () { iosHint.hidden = false; }, 2000);
  }
  if (iosHintClose) {
    iosHintClose.addEventListener('click', function () {
      iosHint.hidden = true;
    });
  }

  /* 4. Push (opcional, integración futura con OneSignal/FCM).
       Cuando el backend exponga /api/push/subscribe:
         navigator.serviceWorker.ready.then(function (reg) {
           reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: <clave pública> })
             .then(sendToApi);
         }); */
})();