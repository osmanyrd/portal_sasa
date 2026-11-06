/**
 * Mapa interactivo de dependencias — Servicios Automotores S.A.
 * Renderiza SVG + panel lateral con datos de window.MAPA_DATA.
 *
 * Mejoras:
 *  - Badge numérico en provincias con >1 dependencia.
 *  - Al hacer clic se listan TODAS las dependencias activas de la provincia.
 *  - Scroll interno si hay más de 4 tarjetas.
 */
(function () {
  'use strict';

  var DATA = window.MAPA_DATA || [];
  var tooltip = document.getElementById('mapaTooltip');
  var panelEmpty = document.getElementById('panelEmpty');
  var panelContent = document.getElementById('panelContent');
  var panelHeader = document.getElementById('panelHeader');
  var panelDeps = document.getElementById('panelDeps');
  var container = document.getElementById('mapaContainer');

  /* ── Index by code ── */
  var byCodigo = {};
  DATA.forEach(function (p) { byCodigo[p.codigo] = p; });

  /* ── Helpers ── */
  function esc(str) {
    if (!str) return '';
    var div = document.createElement('div');
    div.appendChild(document.createTextNode(str));
    return div.innerHTML;
  }

  /* Sanitiza un teléfono para href="tel:..." */
  function telHref(str) {
    return String(str || '').replace(/[^+\d]/g, '');
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

  function hideEmpty() {
    panelEmpty.style.display = 'none';
    panelContent.style.display = '';
  }
  function showEmpty() {
    panelEmpty.style.display = '';
    panelContent.style.display = 'none';
  }

  /* ── Crear badge numérico sobre la provincia SVG ── */
  function createBadge(prov) {
    var path = document.querySelector('.provincia[data-codigo="' + prov.codigo + '"]');
    if (!path || !prov.dependencias || prov.dependencias.length < 1) return;

    var count = prov.dependencias.length;
    if (count < 1) return;

    /* Calcular centroide approx del path para posicionar el badge */
    var bbox = path.getBBox();
    var cx = bbox.x + bbox.width / 2;
    var cy = bbox.y + bbox.height / 2;

    var svg = path.ownerSVGElement;
    var ns = 'http://www.w3.org/2000/svg';

    var g = document.createElementNS(ns, 'g');
    g.classList.add('mapa-badge-group');
    g.setAttribute('data-codigo', prov.codigo);

    /* Fondo del badge */
    var circle = document.createElementNS(ns, 'circle');
    circle.setAttribute('cx', cx);
    circle.setAttribute('cy', cy);
    circle.setAttribute('r', count >= 10 ? 11 : 9);
    circle.classList.add('mapa-badge-bg');
    g.appendChild(circle);

    /* Texto del conteo */
    var text = document.createElementNS(ns, 'text');
    text.setAttribute('x', cx);
    text.setAttribute('y', cy);
    text.setAttribute('text-anchor', 'middle');
    text.setAttribute('dominant-baseline', 'central');
    text.classList.add('mapa-badge-text');
    text.textContent = count >= 10 ? '9+' : String(count);
    g.appendChild(text);

    svg.appendChild(g);

    /* Timing individual: cada badge flota con su propio ritmo (no en sincronía) */
    var dur = (2.8 + Math.random() * 1.4).toFixed(2);
    g.style.animationDuration = dur + 's';
    g.style.animationDelay = (-Math.random() * dur).toFixed(2) + 's';
  }

  /* ── Activar provincia ── */
  function selectProvincia(codigo) {
    /* Mostrar el panel lateral (está oculto hasta seleccionar) */
    var layoutWrap = document.querySelector('.mapa-layout');
    if (layoutWrap) layoutWrap.classList.add('mapa-layout--panel-open');

    /* Desactivar todas */
    document.querySelectorAll('.provincia--activa').forEach(function (el) {
      el.classList.remove('provincia--activa');
      el.setAttribute('aria-pressed', 'false');
    });
    document.querySelectorAll('.mapa-badge-group--activa').forEach(function (el) {
      el.classList.remove('mapa-badge-group--activa');
    });

    var path = document.querySelector('.provincia[data-codigo="' + codigo + '"]');
    if (!path) { showEmpty(); return; }

    path.classList.add('provincia--activa');
    path.setAttribute('aria-pressed', 'true');
    path.focus();

    /* Resaltar badge */
    var badge = document.querySelector('.mapa-badge-group[data-codigo="' + codigo + '"]');
    if (badge) badge.classList.add('mapa-badge-group--activa');

    var prov = byCodigo[codigo];
    if (!prov || !prov.dependencias || prov.dependencias.length === 0) {
      hideEmpty();
      panelHeader.innerHTML =
        '<h2>' + (prov ? esc(prov.nombre) : esc(codigo)) + '</h2>' +
        '<p class="mapa-panel__no-deps">No hay dependencias registradas para esta provincia.</p>';
      panelDeps.innerHTML = '';
      return;
    }

    hideEmpty();

    /* Header con bandera + nombre + conteo */
    var flag = prov.bandera_url
      ? '<img src="' + esc(prov.bandera_url) + '" alt="Bandera de ' + esc(prov.nombre) + '" class="mapa-panel__flag">'
      : '';
    var count = prov.dependencias.length;
    var countLabel = count === 1 ? '1 dependencia' : count + ' dependencias';
    panelHeader.innerHTML =
      '<div class="mapa-panel__title-row">' +
        '<h2>' + flag + esc(prov.nombre) + '</h2>' +
        '<span class="mapa-panel__count">' + countLabel + '</span>' +
      '</div>';

    /* Tarjetas de dependencias */
    var html = '<div class="mapa-deps-list">';
    prov.dependencias.forEach(function (d, idx) {
      var meta = '';
      if (d.direccion) meta += '<li><i class="bi bi-geo-alt"></i>' + esc(d.direccion) + '</li>';
      if (d.telefono) meta += '<li><i class="bi bi-telephone"></i>' + esc(d.telefono) + '</li>';
      if (d.email) meta += '<li><i class="bi bi-envelope"></i><a href="mailto:' + esc(d.email) + '">' + esc(d.email) + '</a></li>';
      if (d.horario) meta += '<li><i class="bi bi-clock"></i>' + esc(d.horario) + '</li>';

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
        '<article class="dep-card" tabindex="0" aria-label="' + esc(d.nombre) + '">' +
          '<div class="dep-card__header">' +
            '<span class="dep-card__number">' + (idx + 1) + '</span>' +
            '<h3 class="dep-card__name">' + esc(d.nombre) + '</h3>' +
            '<span class="dep-card__badge">' + esc(d.tipo_display) + '</span>' +
          '</div>' +
          (d.foto_url
            ? '<img class="dep-card__img" src="' + esc(d.foto_url) + '" alt="' + esc(d.nombre) + '" loading="lazy">'
            : '') +
          '<div class="dep-card__body">' +
            (d.descripcion ? '<p class="dep-card__desc">' + esc(d.descripcion) + '</p>' : '') +
            (meta ? '<ul class="dep-card__meta">' + meta + '</ul>' : '') +
            acciones +
          '</div>' +
        '</article>';
    });
    html += '</div>';
    panelDeps.innerHTML = html;

    /* Delegación: click en "Cómo llegar" */
    panelDeps.querySelectorAll('.dep-card__llegar').forEach(function (btn) {
      btn.addEventListener('click', function () {
        abrirGoogleMaps(
          parseFloat(btn.dataset.lat),
          parseFloat(btn.dataset.lng),
          btn.dataset.nombre
        );
      });
    });
  }

  /* ── Marcar provincias con dependencias ── */
  function markProvincesWithDeps() {
    DATA.forEach(function (p) {
      var path = document.querySelector('.provincia[data-codigo="' + p.codigo + '"]');
      if (path && p.dependencias && p.dependencias.length > 0) {
        path.classList.add('provincia--con-deps');
      }
      createBadge(p);
    });
  }

  /* ── Eventos en cada path de provincia ── */
  function bindEvents() {
    document.querySelectorAll('.provincia').forEach(function (path) {
      var codigo = path.getAttribute('data-codigo');
      var nombre = path.getAttribute('data-nombre');

      path.addEventListener('click', function () {
        selectProvincia(codigo);
      });
      path.addEventListener('keydown', function (e) {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          selectProvincia(codigo);
        }
      });
      path.addEventListener('mouseenter', function () {
        var prov = byCodigo[codigo];
        var count = (prov && prov.dependencias) ? prov.dependencias.length : 0;
        tooltip.textContent = nombre + (count > 0 ? ' (' + count + ')' : '');
        tooltip.classList.add('visible');
      });
      path.addEventListener('mousemove', function (e) {
        var rect = container.getBoundingClientRect();
        tooltip.style.left = (e.clientX - rect.left - tooltip.offsetWidth / 2) + 'px';
        tooltip.style.top = (e.clientY - rect.top - tooltip.offsetHeight - 12) + 'px';
      });
      path.addEventListener('mouseleave', function () {
        tooltip.classList.remove('visible');
      });
    });
  }

  /* ── URL param ?provincia=XX ── */
  function checkUrlParam() {
    var params = new URLSearchParams(window.location.search);
    var prov = params.get('provincia');
    if (prov && byCodigo[prov.toUpperCase()]) {
      selectProvincia(prov.toUpperCase());
    }
  }

  /* ── Clic en el área del mapa (fuera de una provincia): cierra el panel ── */
  function bindMapClose() {
    if (!container) return;
    container.addEventListener('click', function (e) {
      if (e.target.closest('.provincia')) return;
      var layoutWrap = document.querySelector('.mapa-layout');
      if (layoutWrap) layoutWrap.classList.remove('mapa-layout--panel-open');
    });
  }

  /* ── Init ── */
  function init() {
    if (!DATA.length) return;
    markProvincesWithDeps();
    bindEvents();
    bindMapClose();
    checkUrlParam();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
