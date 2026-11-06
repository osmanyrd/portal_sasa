/* Informaciones — Servicios Automotores S.A.
   Interacciones: campana (dropdown accesible) y cartel/toast
   (localStorage + cierre por click-fuera / teclado). */
(function () {
  'use strict';

  var TOAST_STORAGE_KEY = 'info_toast_visto';

  /* ── Campana: dropdown ── */
  function initBell() {
    var wrapper = document.querySelector('[data-info-bell]');
    if (!wrapper) return;

    var btn = wrapper.querySelector('[data-info-bell-btn]');
    var panel = wrapper.querySelector('[data-info-bell-panel]');
    if (!btn || !panel) return;

    var abierto = false;

    function setAbierto(siguiente) {
      abierto = siguiente;
      btn.setAttribute('aria-expanded', abierto ? 'true' : 'false');
      panel.hidden = !abierto;
      if (abierto && window.__panelManager) {
        window.__panelManager.closeAll(cerrarYDevolverFoco);
      }
    }

    function cerrarYDevolverFoco() {
      if (!abierto) return;
      setAbierto(false);
      btn.focus();
    }

    /* Registro en el panel manager */
    if (window.__panelManager) {
      window.__panelManager.register(cerrarYDevolverFoco);
    }

    btn.addEventListener('click', function (e) {
      e.stopPropagation();
      setAbierto(!abierto);
    });

    /* Click-fuera cierra; los clics dentro del panel no propagan. */
    panel.addEventListener('click', function (e) { e.stopPropagation(); });
    document.addEventListener('click', function () {
      if (abierto) setAbierto(false);
    });

    /* Teclado: Escape cierra y devuelve el foco al botón. */
    document.addEventListener('keydown', function (e) {
      if (abierto && e.key === 'Escape') cerrarYDevolverFoco();
    });

    /* Al elegir un enlace del panel, se cierra (y cierra el menú móvil). */
    panel.querySelectorAll('a').forEach(function (a) {
      a.addEventListener('click', function () {
        setAbierto(false);
        var collapse = document.getElementById('navbarNav');
        if (collapse && collapse.classList.contains('show') && window.bootstrap && window.bootstrap.Collapse) {
          var instance = window.bootstrap.Collapse.getOrCreateInstance
            ? window.bootstrap.Collapse.getOrCreateInstance(collapse, { toggle: false })
            : new window.bootstrap.Collapse(collapse, { toggle: false });
          instance.hide();
        }
      });
    });
  }

  /* ── Cartel / toast ── */
  function initToast() {
    var toast = document.querySelector('[data-info-toast]');
    if (!toast) return;

    var closeBtn = toast.querySelector('[data-info-toast-close]');
    var idActual = toast.getAttribute('data-info-toast-id') || '';
    var timerMs = parseInt(toast.getAttribute('data-info-toast-timer') || '8000', 10);
    var visible = false;
    var autoTimer = null;

    /* Solo se muestra una vez por "top" de información reciente. */
    try {
      if (localStorage.getItem(TOAST_STORAGE_KEY) === idActual) return;
    } catch (e) { /* almacenamiento no disponible: se muestra igual */ }

    function marcarVisto() {
      try { localStorage.setItem(TOAST_STORAGE_KEY, idActual); } catch (e) { /* noop */ }
    }

    function ocultar(conFoco) {
      if (autoTimer) { window.clearTimeout(autoTimer); autoTimer = null; }
      if (!visible) {
        marcarVisto();
        return;
      }
      visible = false;
      toast.hidden = true;
      marcarVisto();
      if (conFoco && closeBtn) closeBtn.focus();
    }

    function mostrar() {
      visible = true;
      toast.hidden = false;
      autoTimer = window.setTimeout(function () { ocultar(false); }, timerMs);
    }

    if (closeBtn) {
      closeBtn.addEventListener('click', function () { ocultar(true); });
    }

    /* Clicks dentro del cartel no lo cierran por el handler global. */
    toast.addEventListener('click', function (e) { e.stopPropagation(); });
    document.addEventListener('click', function () {
      if (visible) ocultar(false);
    });

    /* Teclado: Escape cierra y devuelve el foco al botón de cierre. */
    document.addEventListener('keydown', function (e) {
      if (visible && e.key === 'Escape') ocultar(true);
    });

    window.setTimeout(mostrar, 1200);
  }

  /* ── Cinta de informaciones (ticker) ── */
  function initCinta() {
    var cinta = document.querySelector('[data-cinta-estilo]');
    if (!cinta) return;

    var nav = document.getElementById('mainNav');

    /* Coloca la cinta justo debajo del navbar (que es fijo y cambia de altura). */
    function fijarTop() {
      if (!nav) return;
      cinta.style.setProperty('--cinta-top', nav.offsetHeight + 'px');
    }
    fijarTop();

    var estilo = cinta.getAttribute('data-cinta-estilo');

    if (estilo === 'marquee') {
      var track = cinta.querySelector('[data-cinta-marquee] .cinta-marquee__track');
      if (track) dimensionarMarquee(track);
    } else if (estilo === 'slider') {
      iniciarSlider(cinta);
    }

    window.addEventListener('resize', function () {
      fijarTop();
      if (estilo === 'marquee' && track) dimensionarMarquee(track);
    });
    if (nav && 'ResizeObserver' in window) {
      new ResizeObserver(function () { fijarTop(); }).observe(nav);
    }
  }

  /* Marquee: la duración se calcula a partir de los px/s configurados.
     El track contiene 2 copias; recorrer una copia (la mitad del ancho
     total) a ``velocidad`` px/s define la duración del ciclo. */
  function dimensionarMarquee(track) {
    var velocidad = parseInt(track.closest('[data-cinta-estilo]')
      .getAttribute('data-cinta-velocidad') || '30', 10);
    if (!velocidad) velocidad = 30;
    var anchoUnaCopia = track.scrollWidth / 2;
    var duracion = anchoUnaCopia / velocidad; // segundos por ciclo
    track.style.setProperty('--cinta-duracion', Math.max(duracion, 6) + 's');
  }

  /* Slider: muestra una información por vez, alternando cada N segundos. */
  function iniciarSlider(cinta) {
    var tiempo = parseFloat(cinta.getAttribute('data-slider-tiempo') || '5');
    if (!tiempo || tiempo <= 0) tiempo = 5;
    var slides = Array.prototype.slice.call(cinta.querySelectorAll('[data-slide]'));
    if (slides.length < 2) { slides[0].classList.add('is-active'); return; }

    var idx = 0;
    slides[0].classList.add('is-active');

    window.setInterval(function () {
      slides[idx].classList.remove('is-active');
      idx = (idx + 1) % slides.length;
      slides[idx].classList.add('is-active');
    }, tiempo * 1000);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function () {
      initBell();
      initToast();
      initCinta();
    });
  } else {
    initBell();
    initToast();
    initCinta();
  }
  window.addEventListener('load', initCinta);
})();