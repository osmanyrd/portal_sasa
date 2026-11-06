/*
 * Encuestas interactivas — Servicios Automotores S.A.
 * Componentes: estrellas, NPS, slider, emojis, si/no, ranking (SortableJS),
 * matriz, imagenes, pares, contadores de texto y wizard de una pregunta por
 * pantalla con autoguardado en sesion.
 *
 * Convenciones:
 *  - Cada respuesta real vive en un input `name="pregunta_<id>"` (visible u oculto).
 *  - Los componentes visuales escriben en ese input.
 *  - `prefers-reduced-motion`: anime apenas.
 */
(function () {
  'use strict';

  var REDUCED = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  function ready(fn) {
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', fn);
    } else {
      fn();
    }
  }

  ready(function () {
    var form = document.getElementById('surveyForm');
    if (!form) return;

    initComponentes(form);
    initWizard(form);
  });

  /* ── Utilidades ── */
  function setInput(form, namePart, valor) {
    var input = form.querySelector('[name="' + namePart + '"]');
    if (input) input.value = valor;
    markQuestionState(form, input);
  }

  function getInput(form, namePart) {
    var input = form.querySelector('[name="' + namePart + '"]');
    return input ? input.value : '';
  }

  function markQuestionState(form, input) {
    if (!input) return;
    var step = input.closest ? input.closest('.survey-step') : null;
    if (!step) return;
    var tienes = !!String(input.value).trim();
    // si el input es un radio/checkbox con hermanos del mismo name, contar checked
    if (input.type === 'radio' || input.type === 'checkbox') {
      var grupo = step.querySelectorAll('[name="' + input.name + '"]');
      tienes = grupo.length
        ? Array.prototype.some.call(grupo, function (g) { return g.checked; })
        : input.checked;
    }
    step.classList.toggle('is-answered', tienes);
  }

  /* Radio-group con teclado (flechas) */
  function bindRadiogroupKeyboard(group) {
    var buttons = Array.prototype.filter.call(
      group.querySelectorAll('[role="radio"]'),
      function (b) { return !b.disabled; }
    );
    if (!buttons.length) return;

    buttons.forEach(function (btn, idx) {
      btn.addEventListener('keydown', function (e) {
        var next = null;
        if (e.key === 'ArrowRight' || e.key === 'ArrowDown') {
          next = buttons[(idx + 1) % buttons.length];
        } else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') {
          next = buttons[(idx - 1 + buttons.length) % buttons.length];
        } else if (e.key === 'Home') {
          next = buttons[0];
        } else if (e.key === 'End') {
          next = buttons[buttons.length - 1];
        }
        if (next) {
          e.preventDefault();
          selectRadio(group, next, true);
          next.focus();
        }
      });
    });
  }

  function selectRadio(group, btn, moverFoco) {
    var val = btn.getAttribute('data-valor');
    var form = group.closest('form');
    var input = group.parentElement.querySelector('[name="' + group.dataset.target + '"]');
    if (!input) {
      // el input oculto puede estar dentro del mismo step
      input = btn.closest('.survey-step').querySelector('[data-component-input]') ||
              group.previousElementSibling;
    }
    if (!input || !form) return;

    group.querySelectorAll('[role="radio"]').forEach(function (b) {
      var esta = b === btn;
      b.setAttribute('aria-checked', esta ? 'true' : 'false');
      b.classList.toggle('is-selected', esta);
      b.classList.toggle('is-active', esta);
      if (esta && moverFoco === false) {
        // mantener foco en el boton actual
      }
      b.setAttribute('tabindex', esta ? '0' : '-1');
    });

    setInput(form, input.name, val);
    announce(group.parentElement);
  }

  function announce(el) {
    var region = document.getElementById('surveyLiveRegion');
    if (region && el) {
      var etiqueta = el.getAttribute('aria-label');
      region.textContent = 'Seleccionaste ' + (etiqueta || 'una opcion');
    }
  }

  /* ── Componentes ── */
  function initComponentes(form) {
    initEstrellas(form);
    initNPS(form);
    initSlider(form);
    initEmojis(form);
    initSino(form);
    initImagenesYPares(form);
    initRanking(form);
    initMatriz(form);
    initContadores(form);
    bindTextoNormal(form);
  }

  /* Estrellas: hover + click + foco */
  function initEstrellas(form) {
    form.querySelectorAll('.survey-stars').forEach(function (group) {
      var estrellas = Array.prototype.slice.call(group.querySelectorAll('.survey-star'));
      var nombre = group.closest('.survey-step').querySelector('[name^="pregunta_"]').name;

      function pintar(hasta, fija) {
        estrellas.forEach(function (s, i) {
          var activa = i < hasta;
          s.classList.toggle('is-on', activa);
        });
        if (fija) {
          var valor = hasta > 0 ? String(hasta) : '';
          estrellas.forEach(function (s, i) {
            var seleccionada = i < hasta && hasta > 0;
            s.setAttribute('aria-checked', seleccionada ? 'true' : 'false');
            s.setAttribute('tabindex', seleccionada ? '0' : '-1');
          });
          setInput(form, nombre, valor);
          var region = document.getElementById('surveyLiveRegion');
          if (region) region.textContent = 'Calificacion: ' + (hasta || 'sin seleccion') + (hasta ? ' de 5' : '');
        }
      }

      estrellas.forEach(function (s, i) {
        s.addEventListener('click', function () {
          var nueva = i + 1;
          var actual = getInput(form, nombre);
          pintar(Number(actual) === nueva ? 0 : nueva, true);
        });
        s.addEventListener('mouseenter', function () { pintar(i + 1, false); });
        s.addEventListener('mouseleave', function () {
          var actual = Number(getInput(form, nombre));
          pintar(actual, false);
        });
        s.addEventListener('keydown', function (e) {
          if (e.key === ' ' || e.key === 'Enter') {
            e.preventDefault();
            var nueva = i + 1;
            var actual = getInput(form, nombre);
            pintar(Number(actual) === nueva ? 0 : nueva, true);
          }
        });
        s.addEventListener('focus', function () { pintar(i + 1, false); });
        s.addEventListener('blur', function () {
          var actual = Number(getInput(form, nombre));
          pintar(actual, false);
        });
      });

      // Restaurar valor inicial de autosave
      var inicial = getInput(form, nombre);
      if (inicial) pintar(Number(inicial), false);
    });
  }

  /* NPS: botones 0..10 con colores */
  function initNPS(form) {
    form.querySelectorAll('.survey-nps').forEach(function (group) {
      var nombre = group.previousElementSibling.name || group.closest('.survey-step').querySelector('[name^="pregunta_"]').name;
      bindRadiogroupKeyboard(group);
      group.dataset.target = nombre;
      group.querySelectorAll('[role="radio"]').forEach(function (btn) {
        var selec = getInput(form, nombre);
        if (selec === btn.getAttribute('data-valor')) {
          btn.setAttribute('aria-checked', 'true');
          btn.classList.add('is-selected');
          btn.setAttribute('tabindex', '0');
        } else {
          btn.setAttribute('tabindex', '-1');
        }
        btn.addEventListener('click', function () { selectRadio(group, btn, false); });
      });
    });
  }

  /* Slider */
  function initSlider(form) {
    form.querySelectorAll('.survey-slider').forEach(function (range) {
      var nombre = range.getAttribute('data-target');
      var out = document.getElementById(nombre + '_out');
      if (!out) out = range.parentElement.querySelector('.survey-slider-value');

      function actualizar(valor, anunciar) {
        setInput(form, nombre, valor);
        if (out) out.textContent = valor;
        var region = document.getElementById('surveyLiveRegion');
        if (anunciar && region) region.textContent = 'Valor: ' + valor;
      }

      range.addEventListener('input', function () {
        actualizar(range.value, false);
      });
      range.addEventListener('change', function () {
        actualizar(range.value, true);
      });

      var inicial = getInput(form, nombre);
      if (inicial !== '') actualizar(inicial, false);
    });
  }

  /* Emojis */
  function initEmojis(form) {
    form.querySelectorAll('.survey-emojis').forEach(function (group) {
      var nombre = group.previousElementSibling.name || group.closest('.survey-step').querySelector('[name^="pregunta_"]').name;
      bindRadiogroupKeyboard(group);
      group.dataset.target = nombre;
      group.querySelectorAll('[role="radio"]').forEach(function (btn) {
        var selec = getInput(form, nombre);
        if (selec === btn.getAttribute('data-valor')) {
          btn.setAttribute('aria-checked', 'true');
          btn.classList.add('is-selected');
          btn.setAttribute('tabindex', '0');
        } else {
          btn.setAttribute('tabindex', '-1');
        }
        btn.addEventListener('click', function () { selectRadio(group, btn, false); });
      });
    });
  }

  /* Si / No: toggle con iconos */
  function initSino(form) {
    form.querySelectorAll('.survey-sino').forEach(function (group) {
      var nombre = group.previousElementSibling.name || group.closest('.survey-step').querySelector('[name^="pregunta_"]').name;
      bindRadiogroupKeyboard(group);
      group.dataset.target = nombre;
      group.querySelectorAll('[role="radio"]').forEach(function (btn) {
        var selec = getInput(form, nombre);
        if (selec === btn.getAttribute('data-valor')) {
          btn.setAttribute('aria-checked', 'true');
          btn.classList.add('is-selected');
        }
        btn.addEventListener('click', function () { selectRadio(group, btn, false); });
      });
    });
  }

  /* Imagenes y Pares: tarjetas de seleccion */
  function initImagenesYPares(form) {
    ['.survey-img-grid', '.survey-pares'].forEach(function (sel) {
      form.querySelectorAll(sel).forEach(function (group) {
        var nombre = group.previousElementSibling.name || group.closest('.survey-step').querySelector('[name^="pregunta_"]').name;
        bindRadiogroupKeyboard(group);
        group.dataset.target = nombre;
        group.querySelectorAll('[role="radio"]').forEach(function (btn) {
          var selec = getInput(form, nombre);
          if (selec === btn.getAttribute('data-valor')) {
            btn.setAttribute('aria-checked', 'true');
            btn.classList.add('is-selected');
            btn.setAttribute('tabindex', '0');
          } else {
            btn.setAttribute('tabindex', '-1');
          }
          btn.addEventListener('click', function () { selectRadio(group, btn, false); });
        });
      });
    });
  }

  /* Ranking: SortableJS + guardar orden en el hidden */
  function initRanking(form) {
    if (!window.Sortable) return;
    form.querySelectorAll('.survey-ranking').forEach(function (lista) {
      var input = lista.previousElementSibling;
      var nombre = null;
      if (input && input.tagName === 'INPUT' && input.name) {
        nombre = input.name;
      } else {
        input = lista.closest('.survey-step').querySelector('[name^="pregunta_"]');
        nombre = input ? input.name : null;
      }
      if (!nombre) return;

      function guardarOrden() {
        var items = Array.prototype.map.call(
          lista.querySelectorAll('.survey-ranking__item'),
          function (el) { return el.getAttribute('data-opcion-id'); }
        );
        var orden = items.filter(Boolean);
        if (input) input.value = JSON.stringify(orden);
        lista.querySelectorAll('.survey-ranking__item').forEach(function (el, i) {
          var pos = el.querySelector('.survey-ranking__pos');
          if (pos) pos.textContent = i + 1;
        });
        markQuestionState(form, input);
      }

      // Restaurar orden autoguardado (si existe) antes de numerar
      if (input && input.value) {
        try {
          var ordenGuardado = JSON.parse(input.value);
          var porId = {};
          lista.querySelectorAll('.survey-ranking__item').forEach(function (el) {
            porId[el.getAttribute('data-opcion-id')] = el;
          });
          var itemsOrdenados = ordenGuardado
            .map(function (id) { return porId[String(id)]; })
            .filter(Boolean);
          itemsOrdenados.forEach(function (el) { lista.appendChild(el); });
        } catch (e) { /* ignore */ }
      }

      new Sortable(lista, {
        animation: REDUCED ? 0 : 150,
        handle: '.survey-ranking__handle',
        draggable: '.survey-ranking__item',
        ghostClass: 'is-dragging',
        chosenClass: 'is-chosen',
        onEnd: guardarOrden,
      });

      guardarOrden();
    });
  }

  /* Matriz: radios -> hidden JSON {fila: valor} */
  function initMatriz(form) {
    form.querySelectorAll('.survey-matrix').forEach(function (tabla) {
      var nombre = tabla.getAttribute('data-tipo');
      var input = document.getElementById(nombre);
      if (!input) input = form.querySelector('[name="' + nombre + '"]');

      function guardar() {
        var data = {};
        tabla.querySelectorAll('tbody tr').forEach(function (tr) {
          var marcado = tr.querySelector('input[type="radio"]:checked');
          var fila = tr.querySelector('th').textContent.trim();
          if (marcado) data[fila] = Number(marcado.value);
        });
        if (input) {
          input.value = Object.keys(data).length ? JSON.stringify(data) : '';
          markQuestionState(form, input);
        }
      }

      var requiere = input ? input.getAttribute('data-requerida') : null;
      tabla.querySelectorAll('input[type="radio"]').forEach(function (radio) {
        radio.addEventListener('change', guardar);
      });

      // Restaurar desde autosave
      if (input && input.value) {
        try {
          var data = JSON.parse(input.value);
          Object.keys(data).forEach(function (fila) {
            var radio = tabla.querySelector('input[data-fila="' + CSS.escape(fila) + '"][value="' + data[fila] + '"]');
            if (radio) radio.checked = true;
          });
        } catch (e) { /* ignorar */ }
      }
    });
  }

  /* Contadores de caracteres (texto corto / largo) */
  function initContadores(form) {
    form.querySelectorAll('input[type="text"][maxlength], textarea[maxlength]').forEach(function (input) {
      var contador = null;
      var step = input.closest('.survey-step');
      if (step) contador = step.querySelector('[data-counter-for]');
      if (!contador && input.id) contador = document.querySelector('[data-counter-for="' + input.id + '"]');
      if (!contador) return;

      function actualizar() {
        var max = input.maxLength;
        var actual = input.value.length;
        contador.textContent = actual + ' / ' + max + ' caracteres';
        contador.classList.toggle('text-danger', actual > max);
      }
      input.addEventListener('input', actualizar);
      actualizar();
    });
  }

  function bindTextoNormal(form) {
    form.querySelectorAll('.survey-step input[type="text"], .survey-step textarea, .survey-step input[type="date"], .survey-step input[type="time"], .survey-step input[type="email"], .survey-step input[type="number"].survey-numero').forEach(function (input) {
      input.addEventListener('input', function () { markQuestionState(form, input); });
      input.addEventListener('change', function () { markQuestionState(form, input); });
    });
    // radios/checkboxes nativos (simple/multiple) tambien marcan respondido
    form.querySelectorAll('.survey-step input[type="radio"], .survey-step input[type="checkbox"]').forEach(function (input) {
      input.addEventListener('change', function () { markQuestionState(form, input); });
    });
  }

  /* ── Wizard: una pregunta por pantalla ── */
  function initWizard(form) {
    var unaPorPantalla = form.getAttribute('data-una-por-pantalla') === '1';
    var prevBtn = document.getElementById('surveyPrevBtn');
    var nextBtn = document.getElementById('surveyNextBtn');
    var submitBtn = document.getElementById('surveySubmitBtn');
    var barra = document.getElementById('surveyProgressBar');
    var label = document.getElementById('surveyProgressLabel');
    var pct = document.getElementById('surveyProgressPct');

    if (!unaPorPantalla) {
      // Todo en una pantalla: ocultar navegacion wizard y barra de progreso
      if (prevBtn) prevBtn.style.display = 'none';
      if (nextBtn) nextBtn.style.display = 'none';
      if (submitBtn) submitBtn.style.display = '';
      if (barra) barra.closest('.survey-progress-head').style.display = 'none';
      // mostrar la seccion de envio destacada
      var nav = document.querySelector('.survey-wizard-nav');
      if (label) label.textContent = 'Responde todas las preguntas y envia cuando termines.';
      return;
    }

    var pasos = Array.prototype.filter.call(
      form.querySelectorAll('.survey-step'),
      function (s) { return s.style.display !== 'none'; }
    );
    var preguntas = pasos.filter(function (s) { return s.dataset.index !== 'correo'; });
    var total = preguntas.length;
    var actual = 0;

    if (!pasos.length) return;

    var region = document.getElementById('surveyLiveRegion');
    var permitirAtras = form.getAttribute('data-permitir-atras') === '1';

    function esPregunta(paso) { return paso.dataset.index !== 'correo'; }

    function pasoEsValido(paso) {
      var tipo = paso.dataset.tipo || '';
      var esRequerida = paso.dataset.requerida === '1';
      if (!esRequerida) {
        // si no es requerida, se valida solo si hay algo escrito
        return true;
      }
      var marcados = paso.querySelectorAll('[name^="pregunta_"]:checked');
      var presente = marcados.length > 0;

      if (tipo === 'matriz') {
        var radios = paso.querySelectorAll('.survey-matrix input[type="radio"]:checked');
        var filas = paso.querySelectorAll('.survey-matrix tbody tr').length;
        presente = filas > 0 && radios.length === filas;
      } else if (tipo === 'slider') {
        var hidden = paso.querySelector('input[type="hidden"][name^="pregunta_"]');
        presente = !!hidden && !!String(hidden.value).trim();
      } else if (tipo === 'nps' || tipo === 'estrellas' || tipo === 'emojis' || tipo === 'sino' || tipo === 'ranking' || tipo === 'imagenes' || tipo === 'par') {
        var h = paso.querySelector('input[type="hidden"][name^="pregunta_"]');
        presente = !!h && !!String(h.value).trim();
      }

      if (!presente && (tipo === 'simple' || tipo === 'multiple')) {
        var checkedRadio = paso.querySelector('[name^="pregunta_"]:checked');
        presente = !!checkedRadio;
      }
      if (tipo === 'texto_corto' || tipo === 'texto_largo' || tipo === 'fecha' || tipo === 'hora' || tipo === 'numero') {
        var textInput = paso.querySelector('input[type="text"], input[type="date"], input[type="time"], input[type="number"], textarea');
        if (textInput) presente = !!String(textInput.value).trim();
      }

      paso.classList.toggle('is-error', !presente);
      return presente;
    }

    function mostrarPaso(idx) {
      pasos.forEach(function (p, i) {
        if (i === idx) {
          p.hidden = false;
        } else {
          p.hidden = true;
        }
      });

      var esUltima = idx === pasos.length - 1;
      actual = idx;
      if (nextBtn) nextBtn.style.display = esUltima ? 'none' : '';
      if (submitBtn) submitBtn.style.display = esUltima ? '' : 'none';
      if (prevBtn) prevBtn.style.display = (permitirAtras && idx > 0) ? '' : 'none';

      var idxPregunta = 0;
      for (var i = 0; i <= idx; i++) {
        if (esPregunta(pasos[i])) idxPregunta++;
      }
      var nroVisible = esPregunta(pasos[idx]) ? idxPregunta : idxPregunta;
      if (label) {
        label.textContent = esPregunta(pasos[idx])
          ? 'Pregunta ' + idxPregunta + ' de ' + total
          : 'Tus datos (opcional)';
      }
      var avance = Math.round(((idx + 1) / pasos.length) * 100);
      if (pct) pct.textContent = avance + '%';
      if (barra) {
        barra.style.width = avance + '%';
        barra.setAttribute('aria-valuenow', avance);
      }

      if (region) {
        var texto = pasos[idx].querySelector('.survey-question-label');
        region.textContent = 'Pregunta ' + (idxPregunta) + ' de ' + total + '. ' +
          (texto ? texto.textContent.replace(/\s+/g, ' ').trim() : '');
      }
    }

    function siguiente() {
      if (!pasoEsValido(pasos[actual])) {
        if (region) region.textContent = 'Esta pregunta es obligatoria. Responde para continuar.';
        return;
      }
      if (actual < pasos.length - 1) {
        mostrarPaso(actual + 1);
        guardarAutosave();
      }
    }

    function anterior() {
      if (actual > 0) {
        mostrarPaso(actual - 1);
        guardarAutosave();
      }
    }

    if (nextBtn) nextBtn.addEventListener('click', siguiente);
    if (prevBtn) prevBtn.addEventListener('click', anterior);

    // Enter en inputs normales avanza (no salta)
    form.querySelectorAll('.survey-step input[type="text"], .survey-step input[type="date"], .survey-step input[type="time"]').forEach(function (input) {
      input.addEventListener('keydown', function (e) {
        if (e.key === 'Enter' && nextBtn && nextBtn.style.display !== 'none') {
          e.preventDefault();
          siguiente();
        }
      });
    });

    // Autoguardar en sesion
    var autosaveUrl = form.getAttribute('data-autosave-url');
    var autosaveActivo = form.getAttribute('data-autoguardar') === '1';

    function guardarAutosave() {
      if (!autosaveActivo || !autosaveUrl) return;
      var respuestas = {};
      var inputs = form.querySelectorAll('[name^="pregunta_"], [name="correo_participante"]');
      inputs.forEach(function (input) {
        if (input.type === 'radio' && !input.checked) return;
        var valor = input.value;
        if (typeof valor === 'string' && valor !== '') respuestas[input.name] = valor;
      });
      if (!Object.keys(respuestas).length) return;

      fetch(autosaveUrl, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': form.querySelector('[name="csrfmiddlewaretoken"]').value
        },
        body: JSON.stringify({ respuestas: respuestas })
      }).catch(function () { /* fallo silencioso */ });
    }

    // Guardar al pasar preguntas y al enviar
    form.addEventListener('submit', function () {
      guardarAutosave();
    });

    mostrarPaso(0);
  }
})();