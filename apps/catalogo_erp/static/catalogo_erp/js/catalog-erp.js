/* Catálogo ERP — modal de consulta de disponibilidad.
   Abre el modal por categoría, consulta /api/catalogo/buscar/ con la provincia
   elegida y un único término (código o descripción) y renderiza los resultados. */
(function () {
  "use strict";

  var raiz = document.querySelector("[data-catalogo-erp]");
  if (!raiz) return;

  var API_URL = raiz.dataset.apiUrl || "/api/catalogo/buscar/";
  var modalEl = document.getElementById("catalogoErpModal");
  var modalInstancia = window.bootstrap
    ? new bootstrap.Modal(modalEl)
    : null;

  var categoriaActual = null;
  var provinciaActual = "";

  function esc(v) {
    return String(v == null ? "" : v).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  function el(html) {
    var tmp = document.createElement("template");
    tmp.innerHTML = html.trim();
    return tmp.content.firstElementChild;
  }

  function selProvincia() {
    return document.getElementById("catalogoErpProvincia");
  }

  function selTermino() {
    return document.getElementById("catalogoErpTermino");
  }

  // ── Validación ────────────────────────────────────────────────
  function validar() {
    if (!selProvincia().value) {
      mostrarError("Elegí la provincia donde querés consultar la disponibilidad.");
      selProvincia().focus();
      return false;
    }
    if (!selTermino().value.trim()) {
      mostrarError("Ingresá parte del código o de la descripción del producto.");
      selTermino().focus();
      return false;
    }
    return true;
  }

  function abrirModal(boton) {
    categoriaActual = {
      id: boton.dataset.categoriaId,
      nombre: boton.dataset.categoriaNombre,
      ayuda: boton.dataset.ayuda || ""
    };
    document.getElementById("catalogoErpModalCat").textContent = categoriaActual.nombre;
    var ayudaEl = document.getElementById("catalogoErpAyuda");
    ayudaEl.innerHTML = (categoriaActual.ayuda || "Elegí la provincia e ingresá el producto a consultar.")
      .split("\n")
      .map(function (linea) { return esc(linea.replace(/\r/g, "")) || "&nbsp;"; })
      .join("<br>");
    limpiarResultados();
    // reset() deja el valor por defecto del servidor (provincia sugerida).
    document.getElementById("catalogoErpForm").reset();
    provinciaActual = "";
    if (modalInstancia) modalInstancia.show();
    setTimeout(function () { selTermino().focus(); }, 250);
  }

  function limpiarResultados() {
    document.getElementById("catalogoErpResultados").innerHTML = "";
    document.getElementById("catalogoErpError").classList.add("d-none");
    document.getElementById("catalogoErpLoader").classList.add("d-none");
  }

  function mostrarError(msg) {
    var e = document.getElementById("catalogoErpError");
    e.textContent = msg;
    e.classList.remove("d-none");
  }

  function ocultarError() {
    document.getElementById("catalogoErpError").classList.add("d-none");
  }

  function nombreProvincia(codigo) {
    var opcion = selProvincia().querySelector('option[value="' + codigo + '"]');
    return opcion ? opcion.textContent.trim() : codigo;
  }

  // ── Consulta AJAX ─────────────────────────────────────────────
  function buscar(event) {
    if (event) event.preventDefault();
    if (!categoriaActual) return;
    if (!validar()) return;

    ocultarError();
    document.getElementById("catalogoErpLoader").classList.remove("d-none");
    provinciaActual = selProvincia().value;

    var parametros = new URLSearchParams({
      categoria_id: categoriaActual.id,
      provincia: provinciaActual,
      q: selTermino().value.trim()
    });

    fetch(API_URL + "?" + parametros.toString(), { credentials: "same-origin" })
      .then(function (resp) { return resp.json().catch(function () { return null; }); })
      .then(function (datos) {
        document.getElementById("catalogoErpLoader").classList.add("d-none");
        if (!datos) { mostrarError("El servidor no respondió correctamente."); return; }
        if (!datos.ok) { mostrarError(datos.error || "No se pudo completar la consulta."); return; }
        renderizar(datos.productos || []);
      })
      .catch(function () {
        document.getElementById("catalogoErpLoader").classList.add("d-none");
        mostrarError("No se pudo conectar con el catálogo.");
      });
  }

  // ── Renderizado de resultados ─────────────────────────────────
  function renderizar(productos) {
    var cont = document.getElementById("catalogoErpResultados");
    cont.innerHTML = "";

    var zona = nombreProvincia(provinciaActual);

    if (!productos.length) {
      cont.appendChild(el(
        '<div class="catalogo-erp__vacio-aviso">' +
          '<i class="bi bi-search" aria-hidden="true"></i>' +
          "No se encontraron productos con ese término en " + esc(zona) + "." +
        "</div>"
      ));
      return;
    }

    cont.appendChild(el(
      '<p class="catalogo-erp__resumen">' +
        "<span><strong>" + productos.length + "</strong> producto(s) encontrado(s)" +
        (productos.length >= 50 ? " — se muestran los primeros 50" : "") +
        "</span>" +
        '<span class="small">Disponibilidad en ' + esc(zona) + "</span>" +
      "</p>"
    ));

    productos.forEach(function (p) {
      cont.appendChild(detalleProducto(p));
    });
  }

  function detalleProducto(p) {
    var extrasHtml = "";
    ["extra1", "extra2", "extra3"].forEach(function (k) {
      if (p[k] != null && String(p[k]) !== "") {
        extrasHtml += '<span><i class="bi bi-info-circle me-1" aria-hidden="true"></i>' +
          esc(p[k]) + "</span>";
      }
    });

    var dispHtml;
    if (p.disponibilidad && p.disponibilidad.length) {
      var mayorme = null;
      p.disponibilidad.forEach(function (d) {
        if (mayorme == null || d.cantidad > mayorme.cantidad) mayorme = d;
      });
      dispHtml = '<div class="catalogo-erp__pendiente">' + p.disponibilidad.map(function (d) {
        var ok = d.cantidad > 0;
        var top = mayorme && d.cantidad > 0 && d.cantidad === mayorme.cantidad;
        var cant = esc(ok ? "Disponible · " + d.cantidad : "Sin stock");
        var clase = ok ? "catalogo-erp__cantidad--ok" : "catalogo-erp__cantidad--no";
        if (top) clase += " catalogo-erp__cantidad--top";
        return '<span class="catalogo-erp__dep" title="' + esc(d.dependencia) + '">' +
          '<i class="bi bi-geo-alt" aria-hidden="true"></i>' +
          "<span>" + esc(d.dependencia || "Sin dependencia") + "</span>" +
          '<span class="catalogo-erp__cantidad ' + clase + '">' + cant + "</span>" +
        "</span>";
      }).join("") + "</div>";
    } else {
      dispHtml = '<p class="catalogo-erp__sin-stock">' +
        '<i class="bi bi-exclamation-circle me-1" aria-hidden="true"></i>Sin registros de disponibilidad' +
      "</p>";
    }

    return el(
      '<article class="catalogo-erp__producto">' +
        '<div class="catalogo-erp__producto-cabeza">' +
          '<span class="catalogo-erp__producto-codigo">' + esc(p.codigo) + "</span>" +
        "</div>" +
        '<h3 class="catalogo-erp__producto-nombre">' + esc(p.nombre || "—") + "</h3>" +
        (extrasHtml ? '<div class="catalogo-erp__producto-extras">' + extrasHtml + "</div>" : "") +
        dispHtml +
      "</article>"
    );
  }

  // ── Enlace de eventos ─────────────────────────────────────────
  document.querySelectorAll("[data-abrir-modal]").forEach(function (boton) {
    boton.addEventListener("click", function () { abrirModal(boton); });
  });

  var form = document.getElementById("catalogoErpForm");
  if (form) form.addEventListener("submit", buscar);

  // Si la importación de Bootstrap falló, igual permitís consultar la primera.
  if (!modalInstancia) {
    try {
      modalEl.style.display = "block";
      modalEl.classList.add("show");
    } catch (e) { /* noop */ }
  }
})();
