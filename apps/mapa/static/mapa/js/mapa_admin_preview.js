/**
 * Vista previa + edición por arrastre de pines en el panel del snippet Provincia.
 *
 * Renderiza la imagen del mapa sobre las dependencias y permite arrastrar cada
 * pin para actualizar en vivo los campos posicion_x / posicion_y (0-100%) del
 * formulario. Al guardar la provincia, los valores quedan persistidos.
 *
 * Se auto-desactiva si no existe la sección del panel de Dependencias
 * (#panel-dependencias-section), propio del snippet Provincia.
 */
(function () {
  'use strict';

  document.addEventListener('DOMContentLoaded', function () {
    var panelSection = document.getElementById('panel-dependencias-section');
    if (!panelSection) return; // no estamos en la edición de Provincia

    var panelContent = document.getElementById('panel-dependencias-content');
    var formsContainer = document.getElementById('id_dependencias-FORMS');
    if (!panelContent) panelContent = panelSection; // fallback

    /* 1. Resolver la URL de la imagen del mapa (la misma del frontend) */
    var mapaUrl = '';
    function fetchMapaUrl(cb) {
      fetch('/api/mapa/datos/')
        .then(function (r) { return r.json(); })
        .then(function (d) { mapaUrl = d.mapa_url || ''; cb(); })
        .catch(function () { cb(); });
    }

    /* 2. Crear el contenedor de vista previa */
    function buildPreviewContainer() {
      var wrap = document.createElement('div');
      wrap.id = 'mapaAdminPreview';
      wrap.style.cssText =
        'border:1px solid #d0d0d0;border-radius:8px;padding:12px;margin-bottom:12px;' +
        'background:#fff;color:#333;font-family:inherit';
      wrap.innerHTML =
        '<div style="font-weight:600;margin-bottom:4px">Vista previa del mapa — arrastra los pines</div>' +
        '<div style="font-size:12px;color:#777;margin-bottom:10px">' +
        'Arrastra cada pin rojo para cambiar su posición (%). 0% = izquierda/superior, 100% = derecha/inferior. ' +
        'Guarda la provincia al terminar.</div>' +
        '<div id="mapaAdminPane"></div>';
      panelContent.insertBefore(wrap, formsContainer ? formsContainer : panelContent.firstChild);
      return document.getElementById('mapaAdminPane');
    }

    /* 3. Obtener las filas de dependencia (InlinePanel children) */
    function getDepRows() {
      return Array.prototype.slice.call(document.querySelectorAll('[data-inline-panel-child]')).filter(function (el) {
        return el.id && el.id.indexOf('inline_child_dependencias-') === 0;
      });
    }

    function rowInput(row, field) {
      var m = row.id.match(/inline_child_dependencias-(\d+)/);
      if (!m) return null;
      var input = row.querySelector('input[name="dependencias-' + m[1] + '-' + field + '"]');
      return input;
    }

    /* 4. Render de pines y lógica de arrastre */
    var pinsLayer = null;
    function renderPins() {
      if (!pinsLayer) return;
      pinsLayer.innerHTML = '';

      getDepRows().forEach(function (row) {
        var xInput = rowInput(row, 'posicion_x');
        var yInput = rowInput(row, 'posicion_y');
        var nameInput = rowInput(row, 'nombre');
        var idInput = rowInput(row, 'id');
        if (!xInput || !yInput) return;

        var x = parseFloat(xInput.value);
        var y = parseFloat(yInput.value);
        if (isNaN(x)) x = 50;
        if (isNaN(y)) y = 50;

        var nombre = nameInput && nameInput.value ? nameInput.value : '';
        var depId = idInput ? idInput.value : '';

        var pin = document.createElement('div');
        pin.className = 'mapa-admin-pin';
        pin.style.left = x + '%';
        pin.style.top = y + '%';
        pin.innerHTML =
          '<span class="mapa-admin-pin__dot">&#9679;</span>' +
          '<span class="mapa-admin-pin__label"></span>';
        pin.setAttribute('role', 'button');
        pin.setAttribute('tabindex', '0');
        pin.setAttribute('aria-label', 'Pin: ' + (nombre || '') + ' (x ' + x + '%, y ' + y + '%)');
        pin.dataset.depId = depId;

        var labelEl = pin.querySelector('.mapa-admin-pin__label');
        function updateLabel() {
          var vx = parseFloat(xInput.value);
          var vy = parseFloat(yInput.value);
          if (isNaN(vx)) vx = 50;
          if (isNaN(vy)) vy = 50;
          labelEl.textContent = (nombre || 'pin').substring(0, 14) + ' ' + vx + ',' + vy;
        }
        updateLabel();

        function setPosition(clientX, clientY) {
          var wrap = document.getElementById('mapaAdminImgbox');
          if (!wrap) return;
          var rect = wrap.getBoundingClientRect();
          var px = (clientX - rect.left) / rect.width * 100;
          var py = (clientY - rect.top) / rect.height * 100;
          px = Math.max(0, Math.min(100, px));
          py = Math.max(0, Math.min(100, py));
          xInput.value = Math.round(px);
          yInput.value = Math.round(py);
          pin.style.left = px + '%';
          pin.style.top = py + '%';
          pin.setAttribute('aria-label', 'Pin: ' + (nombre || '') + ' (x ' + Math.round(px) + '%, y ' + Math.round(py) + '%)');
          updateLabel();
        }

        /* Arrastre con mouse */
        pin.addEventListener('mousedown', function (e) {
          e.preventDefault();
          e.stopPropagation();
          var moved = false;
          function onMove(ev) {
            moved = true;
            setPosition(ev.clientX, ev.clientY);
          }
          function onUp() {
            document.removeEventListener('mousemove', onMove);
            document.removeEventListener('mouseup', onUp);
          }
          document.addEventListener('mousemove', onMove);
          document.addEventListener('mouseup', onUp);
        });

        /* Arrastre táctil */
        pin.addEventListener('touchstart', function (e) {
          var t = e.touches[0];
          e.preventDefault();
          function onMove(ev) {
            var tt = ev.touches[0];
            setPosition(tt.clientX, tt.clientY);
          }
          function onUp() {
            document.removeEventListener('touchmove', onMove);
            document.removeEventListener('touchend', onUp);
          }
          document.addEventListener('touchmove', onMove);
          document.addEventListener('touchend', onUp);
        });

        /* Teclado: flechas para micro-ajuste */
        pin.addEventListener('keydown', function (e) {
          var step = e.shiftKey ? 5 : 1;
          var dx = 0, dy = 0;
          if (e.key === 'ArrowLeft') dx = -step;
          else if (e.key === 'ArrowRight') dx = step;
          else if (e.key === 'ArrowUp') dy = -step;
          else if (e.key === 'ArrowDown') dy = step;
          else return;
          e.preventDefault();
          var nx = Math.max(0, Math.min(100, (parseFloat(xInput.value) || 0) + dx));
          var ny = Math.max(0, Math.min(100, (parseFloat(yInput.value) || 0) + dy));
          xInput.value = Math.round(nx);
          yInput.value = Math.round(ny);
          pin.style.left = nx + '%';
          pin.style.top = ny + '%';
          updateLabel();
        });

        pinsLayer.appendChild(pin);
      });
    }

    /* 5. Construcción inicial */
    function init() {
      var pane = buildPreviewContainer();
      if (!pane) return;
      pane.innerHTML =
        '<div id="mapaAdminImgbox" style="position:relative;display:inline-block;max-width:100%;width:100%;overflow:hidden">' +
        '  <img id="mapaAdminImg" alt="Mapa de Cuba" style="width:100%;height:auto;display:block;border-radius:6px">' +
        '  <div id="mapaAdminPins" style="position:absolute;inset:0;pointer-events:none"></div>' +
        '</div>' +
        '<div style="font-size:11px;color:#999;margin-top:6px">Pines: <span id="mapaAdminCount">0</span>. Arrastra sobre la imagen para reubicar.</div>';
      pinsLayer = document.getElementById('mapaAdminPins');
      pinsLayer.style.pointerEvents = 'none';

      fetchMapaUrl(function () {
        var img = document.getElementById('mapaAdminImg');
        if (mapaUrl) {
          img.src = mapaUrl;
        } else {
          var box = document.getElementById('mapaAdminImgbox');
          box.style.background = '#fafafa';
          box.style.padding = '20px';
          box.style.borderRadius = '6px';
          box.innerHTML = 'Sube la imagen en Configuración → Configuración del Mapa.';
        }
        renderPins();
        var count = document.getElementById('mapaAdminCount');
        if (count) count.textContent = getDepRows().length;
      });
    }

    init();
  });
})();
