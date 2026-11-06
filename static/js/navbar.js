/* ============================================
   NAVBAR SA — Comportamiento
   Servicios Automotores S.A
   (Drawer, hamburguesa, scroll, búsqueda)
   ============================================ */
(function () {
  'use strict';

  var nav = document.querySelector('.navbar-sa');
  if (!nav) return;

  var hamburger = nav.querySelector('.navbar-sa__hamburger');
  var drawer = document.getElementById('navDrawer');
  var overlay = document.getElementById('navOverlay');
  var closeBtn = drawer && drawer.querySelector('.navbar-sa__drawer-close');

  var hasReducedMotion = window.matchMedia &&
    window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  function bodyLock(lock) {
    if (lock) {
      var scrollY = window.scrollY;
      document.body.style.top = (-scrollY) + 'px';
      document.body.style.position = 'fixed';
      document.body.style.left = '0';
      document.body.style.right = '0';
      document.body.style.width = '100%';
      document.body.dataset.scrollY = String(scrollY);
    } else {
      var prev = parseInt(document.body.dataset.scrollY || '0', 10);
      document.body.style.top = '';
      document.body.style.position = '';
      document.body.style.left = '';
      document.body.style.right = '';
      document.body.style.width = '';
      delete document.body.dataset.scrollY;
      if (!hasReducedMotion) {
        window.scrollTo({ top: prev, behavior: 'auto' });
      } else {
        window.scrollTo(0, prev);
      }
    }
  }

  function openDrawer() {
    if (!drawer || !overlay) return;
    drawer.classList.add('is-open');
    drawer.setAttribute('aria-hidden', 'false');
    overlay.classList.add('is-visible');
    overlay.hidden = false;
    document.body.classList.add('nav-drawer-open');
    bodyLock(true);
    if (hamburger) {
      hamburger.setAttribute('aria-expanded', 'true');
      hamburger.setAttribute('aria-label', 'Cerrar menú');
    }
    var firstLink = drawer.querySelector('a, button');
    if (firstLink) firstLink.focus();
  }

  function closeDrawer() {
    if (!drawer || !overlay) return;
    drawer.classList.remove('is-open');
    drawer.setAttribute('aria-hidden', 'true');
    overlay.classList.remove('is-visible');
    overlay.hidden = true;
    document.body.classList.remove('nav-drawer-open');
    bodyLock(false);
    if (hamburger) {
      hamburger.setAttribute('aria-expanded', 'false');
      hamburger.setAttribute('aria-label', 'Abrir menú');
    }
    if (hamburger) hamburger.focus();
  }

  if (hamburger) {
    hamburger.addEventListener('click', function () {
      var isOpen = hamburger.getAttribute('aria-expanded') === 'true';
      isOpen ? closeDrawer() : openDrawer();
    });
  }
  if (closeBtn) closeBtn.addEventListener('click', closeDrawer);
  if (overlay) overlay.addEventListener('click', closeDrawer);
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape' && drawer && drawer.classList.contains('is-open')) {
      closeDrawer();
    }
  });

  /* Cerrar drawer al hacer clic en un enlace interno */
  if (drawer) {
    drawer.addEventListener('click', function (e) {
      if (e.target.closest('a[href]') && !e.target.closest('.navbar-sa__lang-item') &&
          !e.target.closest('.navbar-sa__user-dropdown')) {
        closeDrawer();
      }
    });
  }

  /* ── Scroll: sombra ── */
  function onScroll() {
    var scrolled = window.scrollY > 8;
    nav.classList.toggle('is-scrolled', scrolled);
  }
  window.addEventListener('scroll', onScroll, { passive: true });
  onScroll();

  /* ── Dropdowns de usuario e idioma comparten panel manager global ── */
  var user = nav.querySelector('.navbar-sa__user');
  var lang = nav.querySelector('.navbar-sa__lang');

  function closeAllDropdowns(except) {
    if (user && except !== user) {
      user.classList.remove('is-open');
      var t = user.querySelector('[aria-expanded]');
      if (t) t.setAttribute('aria-expanded', 'false');
    }
    if (lang && except !== lang) {
      lang.classList.remove('is-open');
      var t2 = lang.querySelector('[aria-expanded]');
      if (t2) t2.setAttribute('aria-expanded', 'false');
    }
  }

  if (user) {
    var userToggle = user.querySelector('.navbar-sa__user-toggle');
    if (userToggle) {
      userToggle.addEventListener('click', function (e) {
        e.stopPropagation();
        var isOpen = user.classList.contains('is-open');
        closeAllDropdowns(user);
        user.classList.toggle('is-open', !isOpen);
        userToggle.setAttribute('aria-expanded', String(!isOpen));
      });
    }
  }

  /* ── Selector de idioma: toggle del menú + cambio de idioma (GT) ── */
  var langSelectors = document.querySelectorAll('#langSelector, #langSelectorDrawer');
  var gtSelect = null;

  /* Buscar el <select> que crea Google Translate (puede tardar en inicializar) */
  function findGtSelect(attempts) {
    gtSelect = document.querySelector('.goog-te-combo');
    if (!gtSelect && attempts < 40) {
      setTimeout(function () { findGtSelect(attempts + 1); }, 250);
    }
  }
  findGtSelect(0);

  function langMenu(sel, open) {
    if (!sel) return;
    sel.classList.toggle('is-open', !!open);
    var t = sel.querySelector('.navbar-sa__lang-toggle');
    if (t) t.setAttribute('aria-expanded', open ? 'true' : 'false');
  }

  langSelectors.forEach(function (sel) {
    if (!sel) return;
    var isHeader = sel.id === 'langSelector';
    var toggle = sel.querySelector('.navbar-sa__lang-toggle');

    if (toggle) {
      toggle.addEventListener('click', function (e) {
        e.stopPropagation();
        var open = sel.classList.contains('is-open');
        closeAllDropdowns(sel);
        langMenu(sel, !open);
      });
    }

    sel.querySelectorAll('[data-lang]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        var langCode = btn.getAttribute('data-lang');
        var selContainer = sel.querySelector('.navbar-sa__lang-items') ||
                           sel.querySelector('.navbar-sa__lang-menu') || sel;
        if (selContainer.contains(btn)) {
          langSelectors.forEach(function (s) {
            s.querySelectorAll('[data-lang]').forEach(function (b) {
              b.classList.toggle('is-active', b === btn);
            });
          });
        }
        if (isHeader) langMenu(sel, false);
        if (gtSelect) {
          gtSelect.value = langCode;
          gtSelect.dispatchEvent(new Event('change'));
        }
      });
    });
  });

  document.addEventListener('click', function (e) {
    langSelectors.forEach(function (sel) {
      if (sel.classList.contains('is-open') && !sel.contains(e.target)) {
        langMenu(sel, false);
      }
    });
  });
  document.addEventListener('keydown', function (e) {
    if (e.key !== 'Escape') return;
    langSelectors.forEach(function (sel) {
      if (sel.classList.contains('is-open')) {
        langMenu(sel, false);
        var t = sel.querySelector('.navbar-sa__lang-toggle');
        if (t) t.focus();
      }
    });
  });

  document.addEventListener('click', function (e) {
    if (user && !user.contains(e.target)) {
      user.classList.remove('is-open');
      var t = user.querySelector('[aria-expanded]');
      if (t) t.setAttribute('aria-expanded', 'false');
    }
  });

  /* Integración con el Panel Manager global: registrar cierres de dropdowns */
  function registerPanelCloser(el) {
    if (!el) return;
    if (el.getAttribute('data-sa-panel-registered')) return;
    el.setAttribute('data-sa-panel-registered', '1');
    if (window.__panelManager && typeof window.__panelManager.register === 'function') {
      window.__panelManager.register(function () {
        el.classList.remove('is-open');
        var t = el.querySelector('[aria-expanded]');
        if (t) t.setAttribute('aria-expanded', 'false');
      });
    }
  }
  registerPanelCloser(user);
  registerPanelCloser(lang);

  /* Cuando se abre un dropdown propio, cerrar los devueltos por el manager */
  [user, lang].forEach(function (el) {
    if (!el) return;
    el.addEventListener('click', function () {
      if (window.__panelManager && typeof window.__panelManager.closeAll === 'function') {
        window.__panelManager.closeAll();
      }
    }, true);
  });
})();