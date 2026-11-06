/**
 * Selector de coordenadas para el admin de Wagtail.
 *
 * El widget MapPointWidget renderiza un bloque [data-mapa-selector] con:
 *   - un input (data-map-input-id) que recibe el valor lat,lng;
 *   - un botón "Obtener coordenadas" (data-map-open);
 *   - un panel colapsable con el mapa Leaflet (data-map-canvas).
 *
 * El mapa se inicializa de forma perezosa la primera vez que se abre.
 * Si las teselas de OpenStreetMap no cargan (p. ej. sin internet), el mapa
 * queda gris pero el clic sigue funcionando: Leaflet no depende de las
 * teselas para interactuar, así que la selección del punto siempre funciona.
 *
 * Soporta filas nuevas del InlinePanel "Dependencias": un MutationObserver
 * re-escanea cuando Wagtail añade una línea nueva al formulario.
 */
(function () {
  'use strict';

  if (typeof window.L === 'undefined') return;

  var DEFAULT_CENTER = [21.5, -79.5]; // Cuba
  var DEFAULT_ZOOM = 6;
  var SELECTED_ZOOM = 12;

  function num(value) {
    var n = parseFloat(value);
    return isNaN(n) ? null : n;
  }

  function fmt(value) {
    return value.toFixed(8);
  }

  /* Inicializa un selector individual. idempotente (data-map-ready). */
  function initSelector(sel) {
    if (sel.hasAttribute('data-map-ready')) return;
    sel.setAttribute('data-map-ready', '1');

    var inputId = sel.getAttribute('data-map-input-id');
    var input = document.getElementById(inputId);
    if (!input) return;

    var btn = sel.querySelector('[data-map-open]');
    var panel = sel.querySelector('[data-map-panel]');
    var canvas = sel.querySelector('[data-map-canvas]');
    var status = sel.querySelector('[data-map-status]');
    var clearBtn = sel.querySelector('[data-map-clear]');
    var closeBtn = sel.querySelector('[data-map-close]');

    if (!btn || !panel || !canvas) return;

    var map = null;
    var marker = null;

    function valueCoords() {
      // El valor puede venir como "lat,lng" o como lat/lng individuales
      // según dónde se use el widget; aquí siempre es "lat,lng".
      var parts = String(input.value || '').split(',').map(num);
      if (parts.length === 2 && parts[0] !== null && parts[1] !== null) {
        return parts;
      }
      return null;
    }

    function applyToInput(lat, lng) {
      input.value = fmt(lat) + ', ' + fmt(lng);
      input.dispatchEvent(new Event('change', { bubbles: true }));
    }

    function ensureMarker(lat, lng, zoomTo) {
      if (marker) marker.remove();
      marker = L.marker([lat, lng]).addTo(map);
      if (zoomTo) map.setView([lat, lng], SELECTED_ZOOM);
      else map.setView([lat, lng], Math.max(map.getZoom(), 12));
    }

    function buildMap() {
      var coords = valueCoords();
      var center = coords || DEFAULT_CENTER;
      var zoom = coords ? SELECTED_ZOOM : DEFAULT_ZOOM;

      map = L.map(canvas, { scrollWheelZoom: false }).setView(center, zoom);
      var layers = [
        {
          url: 'https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}.png',
          options: {
            maxZoom: 20,
            subdomains: 'abcd',
            attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="https://carto.com/attributions">CARTO</a>'
          }
        },
        {
          url: 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
          options: {
            maxZoom: 19,
            attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
          }
        }
      ];
      var layerIndex = 0;
      function loadLayer(i) {
        if (i >= layers.length) return;
        var tile = L.tileLayer(layers[i].url, layers[i].options).addTo(map);
        tile.on('tileerror', function () {
          if (tile) tile.remove();
          loadLayer(i + 1);
        });
      }
      loadLayer(0);

      if (coords) ensureMarker(coords[0], coords[1], true);

      map.on('click', function (e) {
        applyToInput(e.latlng.lat, e.latlng.lng);
        ensureMarker(e.latlng.lat, e.latlng.lng, true);
        if (status) status.textContent =
          'Seleccionado: ' + fmt(e.latlng.lat) + ', ' + fmt(e.latlng.lng);
        map.flyTo([e.latlng.lat, e.latlng.lng], Math.max(map.getZoom(), 12));
      });

      // Corrige el tamaño si el panel se abre con el mapa oculto.
      setTimeout(function () { map.invalidateSize(); }, 80);
    }

    btn.addEventListener('click', function () {
      var opening = panel.hasAttribute('hidden');
      panel.toggleAttribute('hidden');
      btn.setAttribute('aria-expanded', opening ? 'true' : 'false');
      if (opening) {
        if (!map) buildMap();
        setTimeout(function () { map && map.invalidateSize(); }, 60);
        var coords = valueCoords();
        if (coords && map) ensureMarker(coords[0], coords[1], false);
      }
    });

    clearBtn.addEventListener('click', function (e) {
      e.stopPropagation();
      input.value = '';
      input.dispatchEvent(new Event('change', { bubbles: true }));
      if (marker) { marker.remove(); marker = null; }
      if (status) status.textContent = 'Campo vaciado. Haz clic en el mapa para elegir un punto.';
    });

    closeBtn.addEventListener('click', function () {
      panel.setAttribute('hidden', '');
      btn.setAttribute('aria-expanded', 'false');
    });
  }

  function scan(root) {
    var selectors = (root || document).querySelectorAll('[data-mapa-selector]');
    Array.prototype.forEach.call(selectors, initSelector);
  }

  /* Wagtail añade filas nuevas al InlinePanel de Dependencias: observamos
     el documento y activamos los selectores que aparezcan tarde. */
  if (window.MutationObserver) {
    var mo = new MutationObserver(function (mutations) {
      mutations.forEach(function (m) {
        m.addedNodes.forEach(function (node) {
          if (node.nodeType !== 1) return;
          if (node.hasAttribute && node.hasAttribute('data-mapa-selector')) initSelector(node);
          scan(node);
        });
      });
    });
    mo.observe(document.body, { childList: true, subtree: true });
    window.addEventListener('beforeunload', function () { mo.disconnect(); });
  }

  document.addEventListener('DOMContentLoaded', function () { scan(document); });
  if (document.readyState !== 'loading') scan(document);
})();