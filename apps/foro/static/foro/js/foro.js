/* Foro de la comunidad — interacciones mínimas.
   La mayoría de interacciones (expandir formulario, acordeones) son nativas
   HTML (<details>) y no requieren JavaScript. Este script solo añade
   comodidades: cerrar el menú de navegación al pulsar un enlace y autofoco. */
(function () {
  'use strict';

  /* Cerrar el colapso del navbar al hacer clic en un enlace (móvil). */
  var navbarCollapse = document.getElementById('navbarNav');
  if (navbarCollapse) {
    var links = navbarCollapse.querySelectorAll('a');
    var bsCollapse = null;
    if (window.bootstrap && bootstrap.Collapse) {
      bsCollapse = bootstrap.Collapse.getOrCreateInstance
        ? bootstrap.Collapse.getOrCreateInstance(navbarCollapse, { toggle: false })
        : new bootstrap.Collapse(navbarCollapse, { toggle: false });
    }
    links.forEach(function (a) {
      a.addEventListener('click', function () {
        if (bsCollapse && navbarCollapse.classList.contains('show')) {
          bsCollapse.hide();
        }
      });
    });
  }

  /* Si venimos de un enlace de "responder", desplazamos al formulario. */
  if (window.location.hash === '#responder') {
    var responder = document.getElementById('responder');
    if (responder) {
      var input = responder.querySelector('textarea') || responder.querySelector('input');
      if (input) {
        window.setTimeout(function () { input.focus(); }, 300);
      }
    }
  }
})();
