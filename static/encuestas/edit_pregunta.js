/*
 * Admin: muestra/oculta paneles segun `tipo` de pregunta dentro de cada
 * inline de preguntas.
 *
 * Tipos que muestran:
 *   - escala:     estrellas, nps, slider, emojis (campos: min/max/paso/etiquetas)
 *   - pares:      par (etiqueta_izq/der)
 *   - matriz:     matriz (filas)
 *   - opciones:   simple, multiple, ranking, imagenes, par
 *
 * Cada inline child de Wagtail tiene un wrapper con atributo
 * `data-inline-panel-child` e ID `inline_child_preguntas-N`.
 * Los MultiFieldPanel con classname se renderizan como
 * `<div class="w-panel__wrapper ... [classname]">`.
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

  var TIPOS_CON_RANGO  = ['estrellas', 'nps', 'slider', 'emojis', 'numero'];
  var TIPOS_CON_PARES  = ['par'];
  var TIPOS_CON_MATRIZ = ['matriz'];
  var TIPOS_CON_OPCIONES = ['simple', 'multiple', 'ranking', 'imagenes', 'par'];

  ready(function () {
    function apply() {
      document.querySelectorAll('select[id$="-tipo"]').forEach(function (sel) {
        var tipo = sel.value;

        // Subir hasta el wrapper del child inline de preguntas
        var child = sel.closest('[data-inline-panel-child]');
        if (!child) return;

        var escala = child.querySelector('.pregunta-params-escala');
        var pares = child.querySelector('.pregunta-params-pares');
        var matriz = child.querySelector('.pregunta-params-matriz');
        var opciones = child.querySelector('.pregunta-params-opciones');

        if (escala)  escala.style.display  = TIPOS_CON_RANGO.indexOf(tipo) === -1  ? 'none' : '';
        if (pares)   pares.style.display   = TIPOS_CON_PARES.indexOf(tipo) === -1  ? 'none' : '';
        if (matriz)  matriz.style.display  = TIPOS_CON_MATRIZ.indexOf(tipo) === -1 ? 'none' : '';
        if (opciones) opciones.style.display = TIPOS_CON_OPCIONES.indexOf(tipo) === -1 ? 'none' : '';
      });
    }

    // Aplicar al cargar y cada vez que cambia un select de tipo
    document.addEventListener('change', function (e) {
      if (e.target.matches('select[id$="-tipo"]')) apply();
    });
    apply();
  });
})();