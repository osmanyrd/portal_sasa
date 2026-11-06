/**
 * Mapa interactivo de dependencias — Modal + Pines
 * Superpone marcadores (pins) en posiciones porcentuales sobre una imagen real.
 *
 * Mejoras:
 *  - Badge numérico en pins con >1 dependencia en la provincia.
 *  - Al hacer clic en un pin se listan TODAS las dependencias de esa provincia.
 *  - Scroll interno si hay más de 4 tarjetas.
 *  - Header con nombre de provincia + conteo.
 */
(function () {
  'use strict';

  /* ── DOM refs ── */
  var fab = document.getElementById('mapaFabBtn');
  var modal = document.getElementById('mapaModal');
  var closeBtn = document.getElementById('mapaModalClose');
  var mapaImg = document.getElementById('mapaImagen');
  var pinsContainer = document.getElementById('mapaPins');
  var tooltip = document.getElementById('mapaTooltip');
  var tooltipNombre = document.getElementById('tooltipNombre');
  var tooltipProvincia = document.getElementById('tooltipProvincia');
  var filtro = document.getElementById('mapaFiltro');
  var panelEmpty = document.getElementById('panelEmpty');
  var panelContent = document.getElementById('panelContent');
  var panelHeader = document.getElementById('panelHeader');
  var panelBody = document.getElementById('panelBody');
  var wrapper = document.getElementById('mapaWrapper');
  var modalBody = document.querySelector('.mapa-modal__body');

  /* ── Data ── */
  var PROVINCIAS = [];
  var allPins = [];
  var mapaUrl = '';
  var filtroCodigo = '';

  /* ── Colores por tipo de dependencia (paleta del sitio) ── */
  var COLORES_TIPOS = {
    sucursal: '#1a1a2e',   /* negro (primario) */
    taller:   '#ffffff',   /* blanco (secundario) */
    oficina:  '#0D6EFD',   /* azul */
    almacen:  '#16A34A',   /* verde */
    otro:     '#7C3AED'    /* violeta */
  };
  var ETIQUETAS_TIPOS = {
    sucursal: 'Sucursales',
    taller:   'Talleres',
    oficina:  'Oficinas',
    almacen:  'Almacenes',
    otro:     'Otros'
  };

  /* ── Fetch data from API ── */
  function loadData(callback) {
    if (PROVINCIAS.length) { callback(); return; }
    fetch('/api/mapa/datos/')
      .then(function (r) { return r.json(); })
      .then(function (json) {
        mapaUrl = json.mapa_url || '';
        PROVINCIAS = json.provincias || [];
        buildFabAnillo();
        callback();
      })
      .catch(function () { callback(); });
  }

  /* ── Anillo multicolor del botón flotante ──
     Cuenta las dependencias por tipo y pinta un conic-gradient sobre el
     borde del botón: cada tipo aporta su color en proporción a su cantidad.
     Un solo tipo = anillo de un único color (etiqueta distintiva). */
  function buildFabAnillo() {
    if (!fab) return;
    var conteo = {};
    var total = 0;
    PROVINCIAS.forEach(function (p) {
      (p.dependencias || []).forEach(function (d) {
        conteo[d.tipo] = (conteo[d.tipo] || 0) + 1;
        total++;
      });
    });

    if (!total) return;

    var segmentos = [];
    var acumulado = 0;
    Object.keys(conteo).forEach(function (tipo) {
      var color = COLORES_TIPOS[tipo] || '#1a1a2e';
      var desde = (acumulado / total) * 100;
      acumulado += conteo[tipo];
      var hasta = (acumulado / total) * 100;
      segmentos.push(color + ' ' + redondear(desde) + '% ' + redondear(hasta) + '%');
    });

    fab.style.setProperty(
      '--fab-anillo',
      'conic-gradient(' + segmentos.join(', ') + ')'
    );
  }

  function redondear(n) {
    return Math.round(n * 100) / 100;
  }

  /* ── Helpers ── */
  function esc(str) {
    if (str === null || str === undefined) return '';
    var div = document.createElement('div');
    div.appendChild(document.createTextNode(String(str)));
    return div.innerHTML;
  }

  /* Sanitiza un teléfono para href="tel:..." */
  function telHref(str) {
    return String(str || '').replace(/[^+\d]/g, '');
  }

  function showEmpty() {
    panelEmpty.style.display = '';
    panelContent.style.display = 'none';
  }
  function showContent() {
    panelEmpty.style.display = 'none';
    panelContent.style.display = '';
  }

  /* Panel derecho: oculto hasta seleccionar un pin */
  function cerrarPanel() {
    if (modalBody) modalBody.classList.remove('mapa-modal__body--open');
  }
  function abrirPanel() {
    if (modalBody) modalBody.classList.add('mapa-modal__body--open');
  }

  /* ── Build province filter options ── */
  function buildFilter() {
    filtro.innerHTML = '<option value="">Todas las provincias</option>';
    PROVINCIAS.forEach(function (p) {
      if (p.dependencias && p.dependencias.length) {
        var opt = document.createElement('option');
        opt.value = p.codigo;
        opt.textContent = p.nombre + ' (' + p.dependencias.length + ')';
        filtro.appendChild(opt);
      }
    });
  }

  /* ── Helper: etiqueta resumen de tipos para el tooltip ── */
  function pinTipoLabel(deps) {
    var conteo = {};
    deps.forEach(function (d) { conteo[d.tipo] = (conteo[d.tipo] || 0) + 1; });
    var partes = [];
    Object.keys(conteo).forEach(function (t) {
      var nombre = ETIQUETAS_TIPOS[t] || t;
      partes.push(conteo[t] + ' ' + nombre);
    });
    return partes.join(', ');
  }

  /* ── Helper: conic-gradient de un tag pin según sus dependencias ── */
  function buildPinGradient(deps) {
    var conteo = {};
    var total = 0;
    deps.forEach(function (d) {
      conteo[d.tipo] = (conteo[d.tipo] || 0) + 1;
      total++;
    });
    if (!total) return COLORES_TIPOS.sucursal;
    if (total === 1) return COLORES_TIPOS[deps[0].tipo] || COLORES_TIPOS.sucursal;

    var seg = [];
    var acum = 0;
    Object.keys(conteo).forEach(function (t) {
      var color = COLORES_TIPOS[t] || '#1a1a2e';
      var desde = (acum / total) * 100;
      acum += conteo[t];
      var hasta = (acum / total) * 100;
      seg.push(color + ' ' + desde.toFixed(2) + '% ' + hasta.toFixed(2) + '%');
    });
    return 'conic-gradient(' + seg.join(', ') + ')';
  }

  /* ── Build pins over the image ── */
  function buildPins() {
    pinsContainer.innerHTML = '';
    allPins = [];

    PROVINCIAS.forEach(function (p) {
      if (!p.dependencias || p.dependencias.length === 0) return;

      var count = p.dependencias.length;

      /* Crear pin contenedor (puede tener badge) */
      var wrapper = document.createElement('button');
      wrapper.type = 'button';
      wrapper.className = 'mapa-pin-wrapper';
      wrapper.setAttribute('data-provincia', p.codigo);
      wrapper.setAttribute('tabindex', '0');
      wrapper.setAttribute('aria-label', p.nombre + ' — ' + count + (count === 1 ? ' dependencia' : ' dependencias'));
      wrapper.title = p.nombre + ' (' + count + ')';

      /* Posición: usar el primer pin de la provincia como referencia */
      var firstDep = p.dependencias[0];
      wrapper.style.left = firstDep.posicion_x + '%';
      wrapper.style.top = firstDep.posicion_y + '%';

      /* Contenedor que flota (icono + badge) — timing individual por pin */
      var bob = document.createElement('span');
      bob.className = 'mapa-pin-bob';
      var dur = (2.6 + Math.random() * 1.4).toFixed(2);
      bob.style.animationDuration = dur + 's';
      bob.style.animationDelay = (-Math.random() * dur).toFixed(2) + 's';

      /* Icono del pin — tag con forma de chincheta dividido por colores
         de tipo (el gradiente se aplica sobre el glifo vía --pin-tipo) */
      var icon = document.createElement('span');
      icon.className = 'mapa-pin-icon';
      icon.innerHTML = '<i class="bi bi-geo-alt-fill"></i>';
      var gradient = buildPinGradient(p.dependencias);
      icon.style.setProperty('--pin-tipo', gradient);
      icon.setAttribute('aria-hidden', 'true');
      bob.appendChild(icon);

      /* Badge numérico si hay más de 1 dependencia */
      if (count > 1) {
        var badge = document.createElement('span');
        badge.className = 'mapa-pin-badge';
        badge.textContent = count >= 10 ? '9+' : String(count);
        bob.appendChild(badge);
      }

      wrapper.appendChild(bob);

      /* Tooltip on hover */
      wrapper.addEventListener('mouseenter', function () {
        tooltipNombre.textContent = p.nombre;
        tooltipProvincia.textContent = count + (count === 1 ? ' dependencia' : ' dependencias') + ' — ' + pinTipoLabel(p.dependencias);
        tooltip.classList.add('visible');
      });
      wrapper.addEventListener('mousemove', function (e) {
        positionTooltip(e);
      });
      wrapper.addEventListener('mouseleave', function () {
        tooltip.classList.remove('visible');
      });

      /* Click: show ALL dependencias of this province */
      wrapper.addEventListener('click', function () {
        selectProvince(p);
      });
      wrapper.addEventListener('keydown', function (e) {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          selectProvince(p);
        }
      });

      allPins.push({ el: wrapper, provincia: p });
      pinsContainer.appendChild(wrapper);
    });

    applyFilter();
  }

  /* ── Tooltip positioning ── */
  function positionTooltip(e) {
    if (!wrapper) return;
    var rect = wrapper.getBoundingClientRect();
    var x = e.clientX - rect.left;
    var y = e.clientY - rect.top;
    tooltip.style.left = (x - tooltip.offsetWidth / 2) + 'px';
    tooltip.style.top = (y - tooltip.offsetHeight - 16) + 'px';
  }

  /* ── Province filter ── */
  function applyFilter() {
    allPins.forEach(function (item) {
      var match = (!filtroCodigo || item.provincia.codigo === filtroCodigo);
      item.el.style.display = match ? '' : 'none';
      item.el.setAttribute('aria-hidden', match ? 'false' : 'true');
    });
    document.querySelectorAll('.mapa-pin-wrapper--activa').forEach(function (el) {
      if (el.style.display === 'none') {
        el.classList.remove('mapa-pin-wrapper--activa');
        el.setAttribute('aria-pressed', 'false');
      }
    });
  }

  /* ── "Cómo llegar": abrir Google Maps con geolocalización ── */
  function abrirGoogleMaps(lat, lng, nombre) {
    var destino = lat + ',' + lng;
    var urlBasica = 'https://www.google.com/maps/dir/?api=1&destination=' + destino +
                    '&travelmode=driving';

    if (navigator.geolocation) {
      navigator.geolocation.getCurrentPosition(
        function (position) {
          var origen = position.coords.latitude + ',' + position.coords.longitude;
          window.open(
            'https://www.google.com/maps/dir/' + encodeURIComponent(origen) +
            '/' + encodeURIComponent(destino) + '/@' + destino + ',14z',
            '_blank', 'noopener'
          );
        },
        function () {
          /* Permiso denegado o error: abrir sin origen (Google preguntará) */
          window.open(urlBasica, '_blank', 'noopener');
        },
        { enableHighAccuracy: false, timeout: 5000, maximumAge: 300000 }
      );
    } else {
      window.open(urlBasica, '_blank', 'noopener');
    }
  }

  /* ── Select province: render ALL dependencias in panel ── */
  function selectProvince(p) {
    /* Mostrar el panel derecho (está oculto hasta seleccionar) */
    abrirPanel();

    /* Desactivar pins anteriores */
    document.querySelectorAll('.mapa-pin-wrapper--activa').forEach(function (pin) {
      pin.classList.remove('mapa-pin-wrapper--activa');
      pin.setAttribute('aria-pressed', 'false');
    });

    /* Activar pin de esta provincia */
    var pinEl = document.querySelector('.mapa-pin-wrapper[data-provincia="' + p.codigo + '"]');
    if (pinEl) {
      pinEl.classList.add('mapa-pin-wrapper--activa');
      pinEl.setAttribute('aria-pressed', 'true');
      pinEl.focus();
    }

    var deps = p.dependencias || [];
    if (deps.length === 0) {
      showContent();
      panelHeader.innerHTML =
        '<span class="mapa-panel__badge">' + esc(p.codigo) + '</span>' +
        '<h2>' + esc(p.nombre) + '</h2>' +
        '<p class="mapa-panel__no-deps">No hay dependencias activas.</p>';
      panelBody.innerHTML = '';
      return;
    }

    showContent();

    /* Header: provincia + conteo */
    var countLabel = deps.length === 1 ? '1 dependencia activa' : deps.length + ' dependencias activas';
    panelHeader.innerHTML =
      '<span class="mapa-panel__badge">' + esc(p.codigo) + '</span>' +
      '<h2>' + esc(p.nombre) + '</h2>' +
      '<span class="mapa-panel__count">' + countLabel + '</span>';

    /* Tarjetas de dependencias con scroll si hay muchas */
    var html = '<div class="mapa-deps-list">';
    deps.forEach(function (d, idx) {
      var meta = '';
      if (d.direccion) meta += '<li><i class="bi bi-geo-alt"></i> ' + esc(d.direccion) + '</li>';
      if (d.telefono) meta += '<li><i class="bi bi-telephone"></i> ' + esc(d.telefono) + '</li>';
      if (d.email) meta += '<li><i class="bi bi-envelope"></i> <a href="mailto:' + esc(d.email) + '">' + esc(d.email) + '</a></li>';
      if (d.horario) meta += '<li><i class="bi bi-clock"></i> ' + esc(d.horario) + '</li>';

      /* Acciones: Llamar (si hay teléfono) y Cómo llegar (si hay coordenadas) */
      var acciones = '';
      var btnLlamar = '';
      if (d.telefono) {
        btnLlamar =
          '<a class="dep-card__action dep-card__llamar" href="tel:' + esc(telHref(d.telefono)) + '" ' +
            'aria-label="Llamar a ' + esc(d.nombre) + '" title="Llamar">' +
            '<i class="bi bi-telephone" aria-hidden="true"></i>' +
            '<span>Llamar</span>' +
          '</a>';
      }
      var btnLlegar = '';
      if (d.latitud != null && d.longitud != null) {
        btnLlegar =
          '<button class="dep-card__action dep-card__llegar" type="button" ' +
            'data-lat="' + d.latitud + '" data-lng="' + d.longitud + '" ' +
            'data-nombre="' + esc(d.nombre) + '" ' +
            'aria-label="Cómo llegar a ' + esc(d.nombre) + '" ' +
            'title="Cómo llegar">' +
            '<i class="bi bi-signpost-2" aria-hidden="true"></i>' +
            '<span>Cómo llegar</span>' +
          '</button>';
      }
      if (btnLlamar || btnLlegar) {
        acciones = '<div class="dep-card__actions">' + btnLlamar + btnLlegar + '</div>';
      }

      html +=
        '<article class="dep-card">' +
          '<div class="dep-card__header">' +
            '<span class="dep-card__number">' + (idx + 1) + '</span>' +
            '<h3 class="dep-card__name">' + esc(d.nombre) + '</h3>' +
            '<span class="dep-card__badge">' + esc(d.tipo_display) + '</span>' +
          '</div>' +
          (d.foto_url
            ? '<img class="dep-card__foto" src="' + esc(d.foto_url) + '" alt="' + esc(d.nombre) + '" loading="lazy">'
            : '') +
          (d.descripcion ? '<p class="dep-card__desc">' + esc(d.descripcion) + '</p>' : '') +
          (meta ? '<ul class="dep-card__meta">' + meta + '</ul>' : '') +
          acciones +
        '</article>';
    });
    html += '</div>';
    panelBody.innerHTML = html;

    /* Delegación: click en "Cómo llegar" */
    panelBody.querySelectorAll('.dep-card__llegar').forEach(function (btn) {
      btn.addEventListener('click', function () {
        abrirGoogleMaps(
          parseFloat(btn.dataset.lat),
          parseFloat(btn.dataset.lng),
          btn.dataset.nombre
        );
      });
    });
  }

  /* ── Modal open / close ── */
  function openModal() {
    loadData(function () {
      if (mapaUrl) mapaImg.src = mapaUrl;
      buildFilter();
      buildPins();
      showEmpty();
      cerrarPanel();
      /* Cerrar otros paneles antes de abrir */
      if (window.__panelManager) window.__panelManager.closeAll(closeModal);
      modal.classList.remove('closing');
      modal.hidden = false;
      document.body.style.overflow = 'hidden';
      closeBtn.focus();
    });
  }

  function closeModal() {
    if (modal.hidden) return;
    modal.classList.add('closing');
    document.body.style.overflow = '';
    if (fab) fab.focus();
    /* Espera a que termine la transición de salida antes de ocultar */
    setTimeout(function () {
      if (modal.classList.contains('closing')) {
        modal.hidden = true;
        modal.classList.remove('closing');
      }
    }, 320);
  }

  /* Registro en el panel manager */
  if (window.__panelManager) {
    window.__panelManager.register(closeModal);
  }

  /* ── Event listeners ── */
  document.querySelectorAll('[data-mapa-abrir-modal]').forEach(function (btn) {
    btn.addEventListener('click', openModal);
  });
  if (fab) fab.addEventListener('click', openModal);
  if (closeBtn) closeBtn.addEventListener('click', closeModal);

  /* Cargar los datos al inicio para pintar el anillo del FAB de inmediato
     (sin necesidad de abrir el modal). El fetch se hace una sola vez. */
  loadData(function () {});
  /* Clic en el área del mapa (fuera de un pin): cierra el panel derecho */
  if (wrapper) {
    wrapper.addEventListener('click', function (e) {
      if (!e.target.closest('.mapa-pin-wrapper')) cerrarPanel();
    });
  }
  if (filtro) {
    filtro.addEventListener('change', function () {
      filtroCodigo = filtro.value;
      applyFilter();
      showEmpty();
    });
  }
  if (modal) {
    modal.addEventListener('click', function (e) {
      if (e.target === modal) closeModal();
    });
    document.addEventListener('keydown', function (e) {
      if (!modal.hidden && e.key === 'Escape') closeModal();
    });
  }
})();
