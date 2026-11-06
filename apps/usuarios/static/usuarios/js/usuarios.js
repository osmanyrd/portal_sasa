/* Menú de usuario — toggle dropdown */
document.addEventListener("DOMContentLoaded", function () {
  "use strict";

  function setupMenu(toggleId, dropdownId) {
    var toggle = document.getElementById(toggleId);
    var dropdown = document.getElementById(dropdownId);
    if (!toggle || !dropdown) return;

    function posicionaDropdown() {
      var rect = toggle.getBoundingClientRect();
      dropdown.style.top = (rect.bottom + 6) + "px";

      var dropdownW = dropdown.offsetWidth || 232;
      var right = window.innerWidth - rect.right;
      var minRight = 8;
      var maxRight = window.innerWidth - dropdownW - minRight;
      right = Math.max(minRight, Math.min(right, maxRight));
      dropdown.style.right = right + "px";
    }

    function cerrarMenu() {
      if (!dropdown.classList.contains("is-open")) return;
      dropdown.classList.remove("is-open");
      toggle.setAttribute("aria-expanded", "false");
    }

    /* Registro en el panel manager */
    if (window.__panelManager) {
      window.__panelManager.register(cerrarMenu);
    }

    toggle.addEventListener("click", function (e) {
      e.preventDefault();
      e.stopPropagation();
      var wasOpen = dropdown.classList.contains("is-open");
      if (wasOpen) {
        cerrarMenu();
      } else {
        /* Cerrar otros paneles antes de abrir */
        if (window.__panelManager) window.__panelManager.closeAll(cerrarMenu);
        dropdown.classList.add("is-open");
        toggle.setAttribute("aria-expanded", "true");
        posicionaDropdown();
      }
    });

    document.addEventListener("click", function (e) {
      if (!toggle.contains(e.target) && !dropdown.contains(e.target)) {
        dropdown.classList.remove("is-open");
        toggle.setAttribute("aria-expanded", "false");
      }
    });

    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape" && dropdown.classList.contains("is-open")) {
        dropdown.classList.remove("is-open");
        toggle.setAttribute("aria-expanded", "false");
        toggle.focus();
      }
    });
  }

  setupMenu("userMenuToggle", "userMenuDropdown");
  setupMenu("authMenuToggle", "authMenuDropdown");
});

/* ── Modal de perfil: abrir desde el menú de usuario (AJAX) ── */
document.addEventListener("DOMContentLoaded", function () {
  "use strict";

  function csrfToken() {
    var m = document.cookie.match(/csrftoken=([^;]+)/);
    return m ? decodeURIComponent(m[1]) : "";
  }

  function guardarForm(tabla, form) {
    var feedback = form.querySelector(".modal-feedback");
    var btn = form.querySelector('[data-perfil-save][data-form="' + tabla + '"]');
    var fd = new FormData(form);
    fd.append("tabla", tabla);

    if (btn) { btn.disabled = true; btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Guardando…'; }
    if (feedback) feedback.className = "modal-feedback";

    fetch("/cuenta/perfil/", {
      method: "POST",
      headers: {"X-CSRFToken": csrfToken()},
      body: fd
    })
      .then(function (r) { return r.json().then(function (d) { return {ok: r.ok, data: d}; }); })
      .then(function (res) {
        if (feedback) {
          feedback.className = "modal-feedback alert " + (res.ok ? "alert-success" : "alert-danger");
          feedback.textContent = res.ok ? res.data.mensaje : (res.data.error || "Error al guardar.");
        }
        if (res.ok) window.dispatchEvent(new Event("perfilActualizado"));
        if (res.ok) setTimeout(function () { if (feedback) feedback.textContent = ""; }, 2500);
      })
      .catch(function () {
        if (feedback) { feedback.className = "modal-feedback alert alert-danger"; feedback.textContent = "Error de conexión. Intentalo de nuevo."; }
      })
      .finally(function () {
        if (btn) {
          btn.disabled = false;
          btn.innerHTML = tabla === "empresa" ? 'Guardar datos de empresa' : 'Guardar cambios';
        }
      });
  }

  // Delegación: botón guardar dentro de cualquier form de perfil
  document.addEventListener("click", function (e) {
    var btn = e.target.closest("[data-perfil-save]");
    if (btn) {
      e.preventDefault();
      var form = btn.closest("form");
      if (form) guardarForm(btn.getAttribute("data-form"), form);
    }
  });

  // Modal compartido desde el menú de usuario (carga AJAX)
  var modalEl = document.getElementById("usuarioPerfilModal");
  if (!modalEl) return;
  var bsModal = new bootstrap.Modal(modalEl, {backdrop: "static"});
  var content = modalEl.querySelector(".modal-content");

  function abreModal() {
    content.innerHTML =
      '<div class="modal-body text-center py-5"><div class="spinner-border text-danger" role="status"></div>' +
      '<p class="mt-2 text-secondary mb-0">Cargando perfil…</p></div>';
    bsModal.show();
    fetch("/cuenta/perfil/", {
      headers: {"X-Requested-With": "XMLHttpRequest", "X-CSRFToken": csrfToken()}
    })
      .then(function (r) { return r.text(); })
      .then(function (html) { content.innerHTML = html; })
      .catch(function () {
        content.innerHTML = '<div class="modal-body text-center py-5 text-secondary">No se pudo cargar el perfil.</div>';
      });
  }

  document.addEventListener("click", function (e) {
    var opener = e.target.closest("[data-open-perfil]");
    if (opener) { e.preventDefault(); abreModal(); }
  });
});
