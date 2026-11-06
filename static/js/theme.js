/* ============================================
   TEMA SA — Claro/Oscuro
   Persiste la elección del usuario en localStorage.
   Driver: atributo `data-theme` en <html> (clave 'theme').
   Migra desde la clave anterior 'sa-theme'.
   Cuando no hay preferencia guardada: sigue prefers-color-scheme.
   ============================================ */
(function () {
  'use strict';

  var KEY = 'theme';
  var KEY_LEGACY = 'sa-theme';
  var root = document.documentElement;

  function guarded() {
    try { localStorage.getItem(KEY); } catch (e) { return false; }
    return true;
  }
  var ok = guarded();

  function storedTheme() {
    var v = null;
    if (ok) {
      try { v = localStorage.getItem(KEY); } catch (e) {}
      if (!v) { try { v = localStorage.getItem(KEY_LEGACY); } catch (e2) {} }
    }
    return v;
  }

  function systemTheme() {
    return window.matchMedia && window.matchMedia('(prefers-color-scheme: light)').matches
      ? 'light' : 'dark';
  }

  function currentTheme() {
    var s = storedTheme();
    var t = s ? s : systemTheme();
    return t === 'light' ? 'light' : 'dark';
  }

  function applyTheme(theme) {
    var isDark = theme === 'dark';
    root.setAttribute('data-theme', theme);
    root.setAttribute('data-bs-theme', theme);
    document.body.classList.toggle('dark-mode', isDark);
    if (ok) {
      try {
        localStorage.setItem(KEY, theme);
        /* Migración: conserva la clave legada sincronizada */
        localStorage.setItem(KEY_LEGACY, theme);
      } catch (e) {}
    }
    /* Sincronizar el estado visual de todos los toggles del navbar
       (aria-label fijo en el HTML: "Cambiar tema") */
    var toggles = document.querySelectorAll('[data-theme-toggle]');
    for (var i = 0; i < toggles.length; i++) {
      toggles[i].setAttribute('aria-pressed', String(isDark));
    }
  }

  function bindToggles() {
    var toggles = document.querySelectorAll('[data-theme-toggle]');
    for (var i = 0; i < toggles.length; i++) {
      toggles[i].addEventListener('click', function () {
        applyTheme(currentTheme() === 'dark' ? 'light' : 'dark');
      });
    }
  }

  bindToggles();
  applyTheme(currentTheme());

  /* Si no hay preferencia guardada, seguir los cambios del sistema */
  if (ok && !storedTheme() && window.matchMedia) {
    var mq = window.matchMedia('(prefers-color-scheme: light)');
    var onSystemChange = function () {
      if (!storedTheme()) applyTheme(systemTheme());
    };
    if (mq.addEventListener) {
      mq.addEventListener('change', onSystemChange);
    } else if (mq.addListener) {
      mq.addListener(onSystemChange);
    }
  }
})();