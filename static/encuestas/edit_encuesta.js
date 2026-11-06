/*
Admin: muestra/oculta paneles segun `tipo_encuesta`.
- campana: muestra `fecha_inicio`/`fecha_fin`, oculta `dias_espera_respuesta`.
- fija: oculta `fecha_fin`, muestra `dias_espera_respuesta`.
Los paneles de Wagtail exponen wrappers `[data-contentpath="<campo>"]`.
*/
(function () {
  'use strict';
  function ready(fn) {
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', fn);
    } else {
      fn();
    }
  }

  ready(function () {
    var select = document.getElementById('id_tipo_encuesta');
    if (!select) return;

    var wrapFechaFin = document.querySelector('[data-contentpath="fecha_fin"]');
    var wrapDias = document.querySelector('[data-contentpath="dias_espera_respuesta"]');

    function apply() {
      if (select.value === 'fija') {
        if (wrapFechaFin) wrapFechaFin.style.display = 'none';
        if (wrapDias) wrapDias.style.display = '';
      } else {
        if (wrapFechaFin) wrapFechaFin.style.display = '';
        if (wrapDias) wrapDias.style.display = 'none';
      }
    }

    select.addEventListener('change', apply);
    apply();
  });
})();
