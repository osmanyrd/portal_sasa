/* ============================================================
   BUSCADOR DEL NAVBAR — búsqueda ágil con modal de resultados
   - Toggle de expansión con clic fuera para comprimir.
   - Modal de resultados vía AJAX a /api/buscar/?q=…
   - Accesibilidad: aria-expanded, aria-hidden, focus trap,
     aria-live para anunciar el número de resultados.
   - Sin dependencias externas (vanilla JS).
   ============================================================ */
(function () {
  'use strict';

  var MODAL_SELECTOR = '#searchModal';
  var RESULTS_SELECTOR = '[data-search-results]';
  var STATUS_SELECTOR = '[data-search-status]';
  var QUERY_SELECTOR = '[data-search-query]';
  var MORE_SELECTOR = '[data-search-more]';
  var OVERLAY_SELECTOR = '[data-search-overlay]';
  var MODAL_CLOSE_SELECTOR = '[data-search-modal-close]';
  var MODAL_FORM_SELECTOR = '[data-search-modal-form]';
  var MODAL_INPUT_SELECTOR = '[data-search-modal-input]';

  // Caché por término para evitar peticiones repetidas.
  var cache = {};
  // Controlador para abortar la petición anterior.
  var controller = null;
  // Debounce para escribir-para-buscar dentro del modal.
  var debounceTimer = null;
  var DEBOUNCE_MS = 400;

  // Referencias al buscador del navbar (puede haber uno en cada base).

  function qs(sel, ctx) { return (ctx || document).querySelector(sel); }
  function qsa(sel, ctx) { return Array.prototype.slice.call((ctx || document).querySelectorAll(sel)); }

  /* ── Utilidades de foco ── */
  function focusable(el) {
    return qsa('a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])', el)
      .filter(function (n) { return n.offsetParent !== null; });
  }

  function trapFocus(container, e) {
    var items = focusable(container);
    if (!items.length) return;
    var first = items[0];
    var last = items[items.length - 1];
    if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
    else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
  }

  /* ══════════════════════════════════════════════
     MODAL DE RESULTADOS
     ══════════════════════════════════════════════ */
  var modal = qs(MODAL_SELECTOR);
  var modalState = { open: false, lastFocused: null };

  function lockBody(on) {
    document.body.style.overflow = on ? 'hidden' : '';
  }

  function openModal() {
    if (!modal || modalState.open) return;
    modalState.lastFocused = document.activeElement;
    modalState.open = true;
    modal.hidden = false;
    lockBody(true);
    requestAnimationFrame(function () {
      modal.classList.add('is-open');
    });
    // El input del modal ya resuelve a la consulta del navbar.
    var input = qs(MODAL_INPUT_SELECTOR, modal);
    if (input) input.focus();
  }

  function closeModal() {
    if (!modal || !modalState.open) return;
    modalState.open = false;
    modal.classList.remove('is-open');
    setTimeout(function () {
      modal.hidden = true;
    }, 200); // espera la transición de escala/fade
    lockBody(false);
    // Devuelve el foco al elemento que abrió el modal (toggle del navbar).
    if (modalState.lastFocused && modalState.lastFocused.focus) {
      modalState.lastFocused.focus();
    }
  }

  /* ── Render de resultados ── */
  var TYPE_META = {
    novedad:      { icon: 'bi-megaphone-fill',      label: 'Novedad' },
    información:  { icon: 'bi-info-circle-fill',    label: 'Información' },
    producto:     { icon: 'bi-box-seam-fill',       label: 'Producto' },
    página:       { icon: 'bi-file-earmark-text',   label: 'Página' },
    foro:         { icon: 'bi-chat-left-text-fill', label: 'Foro' },
    mapa:         { icon: 'bi-geo-alt-fill',        label: 'Mapa' }
  };

  function resultCard(r) {
    var meta = TYPE_META[r.type] || TYPE_META['página'];
    var img = r.image
      ? '<img class="search-result__img" src="' + r.image + '" alt="" loading="lazy">'
      : '<div class="search-result__img search-result__img--empty" aria-hidden="true"><i class="bi ' + meta.icon + '"></i></div>';
    var excerpt = r.excerpt
      ? '<p class="search-result__excerpt">' + r.excerpt + '</p>'
      : '';
    return '' +
      '<a class="search-result" href="' + r.url + '" data-search-result>' +
        img +
        '<div class="search-result__body">' +
          '<h3 class="search-result__title">' + r.title + '</h3>' +
          excerpt +
          '<span class="search-result__type"><i class="bi ' + meta.icon + '" aria-hidden="true"></i> ' + meta.label + '</span>' +
        '</div>' +
      '</a>';
  }

  function renderResults(data) {
    var container = qs(RESULTS_SELECTOR, modal);
    var status = qs(STATUS_SELECTOR, modal);
    var query = qs(QUERY_SELECTOR, modal);
    var more = qs(MORE_SELECTOR, modal);

    if (query) query.textContent = data.query || '';

    if (!data.count || !data.results || !data.results.length) {
      container.innerHTML = '<div class="search-modal__empty"><i class="bi bi-search" aria-hidden="true"></i><p>No se encontraron resultados para <strong>' + (data.query || '') + '</strong></p></div>';
      if (status) status.textContent = '0 resultados';
      if (more) more.hidden = true;
      return;
    }

    container.innerHTML = '<div class="search-results">' + data.results.map(resultCard).join('') + '</div>';
    if (status) status.textContent = data.results.length + ' resultado' + (data.results.length === 1 ? '' : 's') + ' para «' + (data.query || '') + '»';

    // Botón "Ver todos" solo cuando el endpoint indica que hay más resultados.
    if (more) {
      more.href = '/buscar/?q=' + encodeURIComponent(data.query || '');
      more.hidden = !data.has_more;
    }
  }

  function showSpinner() {
    var container = qs(RESULTS_SELECTOR, modal);
    container.innerHTML = '<div class="search-modal__spinner" aria-hidden="true"><span class="spinner-border" role="status"></span></div>';
  }

  /* ── Búsqueda AJAX ── */
  function fetchResults(term) {
    if (!term) {
      renderResults({ query: '', count: 0, results: [] });
      return;
    }

    // Cachear resultados por término.
    if (cache[term]) {
      renderResults(cache[term]);
      return;
    }

    // Abortar la petición anterior si existe.
    if (controller) controller.abort();
    controller = new AbortController();

    showSpinner();

    fetch('/api/buscar/?q=' + encodeURIComponent(term), {
      signal: controller.signal,
      headers: { 'Accept': 'application/json' }
    })
      .then(function (res) {
        if (!res.ok) throw new Error('HTTP ' + res.status);
        return res.json();
      })
      .then(function (data) {
        cache[term] = data;
        // El input del modal es el "refinamiento"; el del navbar es el original.
        renderResults(data);
      })
      .catch(function (err) {
        if (err.name === 'AbortError') return; // se canceló una petición nueva
        var container = qs(RESULTS_SELECTOR, modal);
        container.innerHTML = '<div class="search-modal__error"><p>Ocurrió un error al buscar. Intentá de nuevo.</p></div>';
      });
  }

  /* ── Apertura del modal desde cualquier buscador del navbar/drawer ── */
  function openModalWith(term) {
    if (!modal) return;
    openModal();
    var input = qs(MODAL_INPUT_SELECTOR, modal);
    if (input) { input.value = term || ''; }
    fetchResults(term || '');
  }

  /* ══════════════════════════════════════════════
     BUSCADOR DEL NAVBAR (expansión / colapso)
     Delegación de eventos: un único listener por tipo en document.
     ══════════════════════════════════════════════ */
  // Registro de widgets para poder gestionarlos desde la delegación.
  var widgets = [];

  function registerWidget(widget) {
    var form = qs('[data-search-form]', widget);
    var input = qs('[data-search-input]', widget);
    var toggle = qs('[data-search-toggle]', widget);
    if (!toggle || !form) return;

    var state = {
      root: widget,
      form: form,
      input: input,
      toggle: toggle,
      isOpen: false
    };
    widgets.push(state);
  }

  function widgetOf(el) {
    for (var i = 0; i < widgets.length; i++) {
      if (widgets[i].root.contains(el)) return widgets[i];
    }
    return null;
  }

  function setWidgetAria(w) {
    w.toggle.setAttribute('aria-expanded', String(w.isOpen));
    w.form.setAttribute('aria-hidden', String(!w.isOpen));
    w.form.classList.toggle('active', w.isOpen);
    w.root.classList.toggle('is-open', w.isOpen);
  }

  function openWidget(w) {
    if (w.isOpen) return;
    w.isOpen = true;
    setWidgetAria(w);
    if (w.input) w.input.focus();
  }

  function closeWidget(w) {
    if (!w.isOpen) return;
    w.isOpen = false;
    setWidgetAria(w);
    if (w.input) w.input.value = '';
    w.toggle.focus();
  }

  function closeAllWidgets() {
    widgets.forEach(closeWidget);
  }

  /* Delegación de clic: toggle, botón X y clic fuera. */
  function onDocumentClick(e) {
    // Toggle de la lupa.
    var toggleEl = e.target.closest('[data-search-toggle]');
    if (toggleEl) {
      var w = widgetOf(toggleEl);
      if (w) { e.preventDefault(); w.isOpen ? closeWidget(w) : openWidget(w); return; }
    }

    // Botón de cerrar (X).
    var closeEl = e.target.closest('[data-search-close]');
    if (closeEl) {
      var wc = widgetOf(closeEl);
      if (wc) { e.preventDefault(); closeWidget(wc); return; }
    }

    // Clic fuera del contenedor → comprimir todos los buscadores abiertos.
    if (!e.target.closest('[data-navbar-search]')) closeAllWidgets();
  }

  /* Delegación de submit: abre el modal en lugar de navegar. */
  function onDocumentSubmit(e) {
    var form = e.target.closest('[data-search-form]');
    if (!form) return;
    e.preventDefault();
    var w = widgetOf(form);
    var value = w && w.input ? w.input.value.trim() : '';
    if (value) openModalWith(value);
  }

  /* Delegación de teclado: Escape cierra el buscador y el modal. */
  function onDocumentKeydown(e) {
    if (e.key !== 'Escape') return;
    closeAllWidgets();
    if (modalState.open) closeModal();
  }

  function initDrawerSearch(form) {
    form.addEventListener('submit', function (e) {
      e.preventDefault();
      var input = qs('input[name="q"]', form);
      if (input && input.value.trim()) {
        // Cierra la lista/overlay del drawer abierto (existe en ambos navbars).
        var drawer = document.getElementById('navDrawer');
        if (drawer) drawer.setAttribute('aria-hidden', 'true');
        var overlay = document.getElementById('navOverlay');
        if (overlay) overlay.hidden = true;
        openModalWith(input.value.trim());
      }
    });
  }

  /* ══════════════════════════════════════════════
     INICIALIZACIÓN
     ══════════════════════════════════════════════ */
  function init() {
    qsa('[data-navbar-search]').forEach(registerWidget);
    qsa('[data-drawer-search]').forEach(initDrawerSearch);

    // Delegación global de eventos.
    document.addEventListener('click', onDocumentClick);
    document.addEventListener('submit', onDocumentSubmit);
    document.addEventListener('keydown', onDocumentKeydown);

    if (!modal) return;

    // Cierre por botón X.
    qsa(MODAL_CLOSE_SELECTOR, modal).forEach(function (btn) {
      btn.addEventListener('click', closeModal);
    });

    // Cierre por clic fuera del contenido (overlay).
    var overlay = qs(OVERLAY_SELECTOR, modal);
    if (overlay) overlay.addEventListener('click', closeModal);

    // Refinar búsqueda sin cerrar el modal (debounce 400ms).
    var modalForm = qs(MODAL_FORM_SELECTOR, modal);
    var modalInput = qs(MODAL_INPUT_SELECTOR, modal);
    if (modalForm && modalInput) {
      modalForm.addEventListener('submit', function (e) {
        e.preventDefault();
        fetchResults(modalInput.value.trim());
      });
      modalInput.addEventListener('input', function () {
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(function () {
          fetchResults(modalInput.value.trim());
        }, DEBOUNCE_MS);
      });
    }

    // Focus trap mientras el modal está abierto.
    modal.addEventListener('keydown', function (e) {
      if (e.key === 'Tab' && modalState.open) trapFocus(modal, e);
    });

    // Clic en un resultado → cerrar modal y navegar.
    modal.addEventListener('click', function (e) {
      var result = e.target.closest('[data-search-result]');
      if (result) {
        closeModal();
        // La navegación la hace el <a href>, sólo cerramos el modal.
      }
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();