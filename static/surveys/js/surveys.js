/* Encuestas — Servicios Automotores S.A.
   Interacciones: campanita de encuestas (dropdown accesible) y
   botón flotante de encuesta pendiente. */
(function () {
  'use strict';

  /* ── Campanita: dropdown ── */
  function initBell() {
    var wrapper = document.querySelector('[data-survey-bell]');
    if (!wrapper) return;

    var btn = wrapper.querySelector('[data-survey-bell-btn]');
    var panel = wrapper.querySelector('[data-survey-bell-panel]');
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

    panel.addEventListener('click', function (e) { e.stopPropagation(); });
    document.addEventListener('click', function () {
      if (abierto) setAbierto(false);
    });

    document.addEventListener('keydown', function (e) {
      if (abierto && e.key === 'Escape') cerrarYDevolverFoco();
    });

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

  /* ── Aviso temporal "Encuesta nueva" (pildora junto a la campana) ──
     Se muestra al cargar la pagina si existe la pildora en el DOM y el
     usuario no la oculto (cookie), y se auto-oculta a los pocos segundos
     o al hacer clic en la "x". */
  function initNueva() {
    var pill = document.querySelector('[data-survey-bell-nueva]');
    if (!pill) return;

    var cookieName = "survey_bell_nueva_visto";
    var getCookie = function (name) {
      var v = document.cookie.match('(^|;)\\s*' + name + '\\s*=\\s*([^;]+)');
      return v ? v.pop() : null;
    };
    var setCookie = function (name, val, days) {
      var d = new Date();
      d.setTime(d.getTime() + (days * 24 * 60 * 60 * 1000));
      document.cookie = name + "=" + val + ";expires=" + d.toUTCString() + ";path=/;SameSite=Lax";
    };

    var autoTimer = null;

    function ocultar() {
      if (pill.classList.contains("survey-bell__nueva--leaving")) return;
      pill.classList.add("survey-bell__nueva--leaving");
      pill.addEventListener("animationend", function () {
        pill.hidden = true;
      }, { once: true });
      if (autoTimer) { clearTimeout(autoTimer); autoTimer = null; }
    }

    // Si ya lo vio antes, no se vuelve a mostrar.
    if (getCookie(cookieName)) return;

    pill.hidden = false;

    // Auto-ocultar tras 8s de estar visible.
    autoTimer = setTimeout(ocultar, 8000);

    // Cierre manual con la "x".
    var closeBtn = document.getElementById("surveyBellNuevaClose");
    if (closeBtn) {
      closeBtn.addEventListener("click", function (e) {
        e.stopPropagation();
        setCookie(cookieName, "1", 2);
        ocultar();
      });
    }
  }

  /* ── Botón flotante: panel con las encuestas disponibles ──
     Al pulsarlo abre un cuadro (estilo campana) listando las encuestas
     pendientes para elegir cuál responder. */
  function initFloat() {
    var wrapper = document.querySelector('[data-survey-float]');
    if (!wrapper) return;

    var btn = wrapper.querySelector('[data-survey-float-btn]');
    var panel = wrapper.querySelector('[data-survey-float-panel]');
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

    if (window.__panelManager) {
      window.__panelManager.register(cerrarYDevolverFoco);
    }

    btn.addEventListener('click', function (e) {
      e.stopPropagation();
      setAbierto(!abierto);
    });

    panel.addEventListener('click', function (e) { e.stopPropagation(); });

    var closeBtn = panel.querySelector('[data-survey-float-close]');
    if (closeBtn) {
      closeBtn.addEventListener('click', function (e) {
        e.stopPropagation();
        setAbierto(false);
        btn.focus();
      });
    }

    document.addEventListener('click', function () {
      if (abierto) setAbierto(false);
    });

    document.addEventListener('keydown', function (e) {
      if (abierto && e.key === 'Escape') cerrarYDevolverFoco();
    });

    panel.querySelectorAll('a').forEach(function (a) {
      a.addEventListener('click', function () {
        setAbierto(false);
      });
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function () {
      initBell();
      initNueva();
      initFloat();
    });
  } else {
    initBell();
    initNueva();
    initFloat();
  }
})();
