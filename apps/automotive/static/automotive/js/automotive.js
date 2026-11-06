(function () {
  var prefersReduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  /* ---- Panel Manager: solo un panel flotante abierto a la vez ---- */
  var _panelClosers = [];
  var _activePanel = null;

  window.__panelManager = {
    register: function (closeFn) {
      if (typeof closeFn === 'function' && _panelClosers.indexOf(closeFn) === -1) {
        _panelClosers.push(closeFn);
      }
    },
    closeAll: function (except) {
      _panelClosers.forEach(function (fn) {
        if (fn !== except) fn();
      });
    },
    opened: function (openFn) {
      _activePanel = openFn || null;
    },
    getActive: function () {
      return _activePanel;
    }
  };

  /* Cerrar todos los paneles con click afuera del área del panel */
  document.addEventListener('click', function (e) {
    if (_panelClosers.length === 0) return;
    /* No cerrar si el click es dentro de un botón trigger o un panel registrado */
    var isInside = e.target.closest(
      '.chatbot-trigger, .chatbot-window, ' +
      '[data-info-bell], ' +
      '.user-menu__dropdown, .user-menu__toggle, ' +
      '.navbar-sa__lang, .navbar-sa__lang-toggle, .navbar-sa__lang-menu, ' +
      '.navbar-sa__user, .navbar-sa__user-toggle, .navbar-sa__user-dropdown, ' +
      '#chatbotWindow, #chatbotTrigger, ' +
      '[data-info-bell-panel], [data-info-bell-btn], ' +
      '.mapa-modal-overlay, .mapa-fab'
    );
    if (!isInside) {
      window.__panelManager.closeAll();
    }
  });

  /* Cerrar todos los paneles con Escape */
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') {
      window.__panelManager.closeAll();
    }
  });

/* ---- Preloader ---- */
  var preloader = document.getElementById("preloader");
  function hidePreloader() {
    if (preloader && !preloader.classList.contains("is-done")) {
      preloader.classList.add("is-done");
      setTimeout(function () { preloader.remove(); }, 550);
    }
  }
  if (prefersReduced) { hidePreloader(); }
  else {
    window.addEventListener("load", function () { setTimeout(hidePreloader, 350); });
    setTimeout(hidePreloader, 2800);
  }

  /* ---- Navbar scroll ---- */
  var nav = document.getElementById("mainNav");
  function onScroll() {
    var y = window.scrollY || document.documentElement.scrollTop;
    if (nav) nav.classList.toggle("is-scrolled", y > 60);
  }
  window.addEventListener("scroll", function () { requestAnimationFrame(onScroll); }, { passive: true });
  onScroll();

  /* ---- Scroll spy ---- */
  var sections = document.querySelectorAll("section[id]");
  var navLinks = document.querySelectorAll("#navbarNav .nav-link");
  function updateActiveNav() {
    var y = window.scrollY + 120;
    sections.forEach(function (sec) {
      if (y >= sec.offsetTop && y < sec.offsetTop + sec.offsetHeight) {
        navLinks.forEach(function (a) { a.classList.remove("active"); });
        var active = document.querySelector('#navbarNav .nav-link[href="#' + sec.id + '"]');
        if (active) active.classList.add("active");
      }
    });
  }
  window.addEventListener("scroll", function () { requestAnimationFrame(updateActiveNav); }, { passive: true });

  /* ---- Smooth scroll for nav links ---- */
  document.querySelectorAll('a[href^="#"]').forEach(function (a) {
    a.addEventListener("click", function (e) {
      var id = this.getAttribute("href");
      if (id.length < 2) return;
      var target = document.querySelector(id);
      if (target) {
        e.preventDefault();
        var offset = nav ? nav.offsetHeight : 0;
        window.scrollTo({ top: target.offsetTop - offset, behavior: prefersReduced ? "auto" : "smooth" });
      }
    });
  });

/* ---- Back to top (con anillo de progreso) ---- */
  var topBtn = document.getElementById("backToTop");
  function updateTopProgress() {
    if (!topBtn) return;
    var max = document.documentElement.scrollHeight - window.innerHeight;
    var p = max > 0 ? Math.min(window.scrollY / max, 1) : 0;
    topBtn.style.setProperty("--progress", (p * 360).toFixed(1) + "deg");
    topBtn.classList.toggle("show", window.scrollY > 560);
  }
  window.addEventListener("scroll", updateTopProgress, { passive: true });
  window.addEventListener("resize", updateTopProgress);
  if (topBtn) topBtn.addEventListener("click", function () {
    window.scrollTo({ top: 0, behavior: prefersReduced ? "auto" : "smooth" });
  });
  updateTopProgress();

  /* ---- Tilt 3D sutil en tarjetas (solo dispositivos con mouse) ---- */
  function initTilt() {
    var finePointer = window.matchMedia("(hover: hover) and (pointer: fine)");
    if (prefersReduced || !finePointer.matches) return;
    document.querySelectorAll(".service-card, .nv-card").forEach(function (card) {
      card.addEventListener("mousemove", function (e) {
        var r = card.getBoundingClientRect();
        var px = ((e.clientX - r.left) / r.width) || 0;
        var py = ((e.clientY - r.top) / r.height) || 0;
        card.style.setProperty("--rx", ((0.5 - py) * 6).toFixed(2) + "deg");
        card.style.setProperty("--ry", ((px - 0.5) * 8).toFixed(2) + "deg");
        card.style.setProperty("--gx", (px * 100).toFixed(1) + "%");
        card.style.setProperty("--gy", (py * 100).toFixed(1) + "%");
      });
      card.addEventListener("mouseleave", function () {
        card.style.setProperty("--rx", "0deg");
        card.style.setProperty("--ry", "0deg");
        card.style.setProperty("--gx", "50%");
        card.style.setProperty("--gy", "50%");
      });
    });
  }
  initTilt();

  /* ---- Reveal animations ---- */
var AUTO_REVEAL = [
    ".hero-title", ".hero-subtitle", ".hero-section .btn",
    ".section-tag", ".section-title", ".section-intro",
    ".nv-card", ".service-card", ".gallery-item",
    ".info-item", ".channel-card", ".contact-form-card",
    ".stat-item", ".map-wrapper",
    ".portada-destacados-head", ".portada-col-titulo", ".portada-card"
  ];
  function initReveal() {
    document.querySelectorAll(AUTO_REVEAL.join(",")).forEach(function (el) {
      if (!el.hasAttribute("data-reveal") && !el.closest("[data-reveal]")) el.setAttribute("data-reveal", "");
    });
    var els = document.querySelectorAll("[data-reveal]:not(.is-visible)");
    if (prefersReduced || !("IntersectionObserver" in window)) {
      els.forEach(function (el) { el.classList.add("is-visible"); });
      return;
    }
var groups = new Map();
    els.forEach(function (el) {
      var p = (el.parentElement && el.parentElement.closest('.portada-col, [class*="row"]')) || el.parentElement;
      var n = groups.get(p) || 0;
      el.style.setProperty("--reveal-delay", Math.min(n * 80, 400) + "ms");
      groups.set(p, n + 1);
    });
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) {
        if (en.isIntersecting) { en.target.classList.add("is-visible"); io.unobserve(en.target); }
      });
    }, { threshold: 0.1, rootMargin: "0px 0px -40px" });
    els.forEach(function (el) { io.observe(el); });
  }
  initReveal();

  /* ---- Shuffle de tarjetas de portada (Novedades / Informaciones) ----
     Al aparecer la sección, las tarjetas se "barajan": entran en cascada
     y luego intercambian de posición usando la técnica FLIP (medir,
     reordenar DOM, invertir y animar). Respeta prefers-reduced-motion. */
  var SHUFFLE_PASSES = [
    function (cols) { return cols.slice().reverse(); },
    function (cols) { return cols.slice().reverse(); }
  ];

  function flipShufflePass(container, reorderFn, done) {
    var cols = Array.prototype.slice.call(container.children).filter(function (c) {
      return c.classList && c.classList.contains("col");
    });
    if (cols.length < 2) { done && done(); return; }

    var first = cols.map(function (c) { return c.getBoundingClientRect(); });

    container.classList.add("is-shuffling");
    cols.forEach(function (c, i) {
      c.style.setProperty("--rz", i % 2 === 0 ? "4deg" : "-4deg");
      c.style.setProperty("--rzn", i % 2 === 0 ? "-4deg" : "4deg");
    });

    var nuevoOrden = reorderFn(cols);
    nuevoOrden.forEach(function (c) { container.appendChild(c); });

    var last = cols.map(function (c) { return c.getBoundingClientRect(); });
    cols.forEach(function (c, i) {
      c.style.transform = "translate3d(" +
        (first[i].left - last[i].left).toFixed(1) + "px," +
        (first[i].top - last[i].top).toFixed(1) + "px,0)";
    });
    void container.offsetWidth; /* forzar reflow para aplicar inversión */

    cols.forEach(function (c) { c.style.transform = ""; });

    setTimeout(function () {
      container.classList.remove("is-shuffling");
      done && done();
    }, 760);
  }

  function runDestacadosShuffle(container) {
    var pass = 0;
    function next() {
      if (pass >= SHUFFLE_PASSES.length) {
        if (container.classList.contains("is-shuffled")) {
          container.classList.remove("is-shuffled");
        }
        container.classList.add("is-shuffled");
        setTimeout(function () { container.classList.remove("is-shuffled"); }, 1100);
        return;
      }
      flipShufflePass(container, SHUFFLE_PASSES[pass], function () {
        pass += 1;
        setTimeout(next, 140);
      });
    }
    next();
  }

  function initDestacadosShuffle() {
    var rows = document.querySelectorAll("[data-shuffle]");
    if (!rows.length || prefersReduced || !("IntersectionObserver" in window)) return;

    rows.forEach(function (row) {
      var io = new IntersectionObserver(function (entries) {
        entries.forEach(function (en) {
          if (!en.isIntersecting) return;
          io.unobserve(row);
          /* Esperar a que el reveal en cascada termine antes de barajar */
          var esperado = 2600;
          var t0 = Date.now();
          var bloque = row.closest(".portada-col");
          function revisarCards() {
            var cards = row.querySelectorAll(".portada-card");
            var entrada = !bloque || bloque.classList.contains("is-visible");
            var listos = entrada && Array.prototype.every.call(cards, function (c) {
              return c.classList.contains("is-visible");
            });
            if (listos || row.offsetWidth === 0 || Date.now() - t0 > esperado) {
              runDestacadosShuffle(row);
            } else {
              setTimeout(revisarCards, 80);
            }
          }
          setTimeout(revisarCards, 420);
        });
      }, { threshold: 0.45 });
      io.observe(row);
    });
  }
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initDestacadosShuffle);
  } else {
    initDestacadosShuffle();
  }

  /* ---- Entrada direccional de bloques de portada ----
     Novedades desde la derecha, Informaciones desde la izquierda:
     se revelan cuando el bloque entra a la vista (o al cargar, si ya está
     en el viewport). El barajado espera a que el bloque entre. */
  function initPortadaBlocksReveal() {
    if (prefersReduced || !("IntersectionObserver" in window)) return;
    var cols = document.querySelectorAll(".portada-col");
    cols.forEach(function (col) {
      if (col.classList.contains("is-visible")) return;
      var io = new IntersectionObserver(function (entries) {
        entries.forEach(function (en) {
          if (!en.isIntersecting) return;
          col.classList.add("is-visible");
          io.unobserve(col);
        });
      }, { threshold: 0.12, rootMargin: "0px 0px -4px 0px" });
      io.observe(col);
    });
  }
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initPortadaBlocksReveal);
  } else {
    initPortadaBlocksReveal();
  }

  /* ---- Stats counter ---- */
  function animateCounters() {
    var counters = document.querySelectorAll("[data-count]");
    counters.forEach(function (el) {
      var target = parseInt(el.getAttribute("data-count"), 10);
      var duration = 1800;
      var start = 0;
      var startTime = null;
      function step(timestamp) {
        if (!startTime) startTime = timestamp;
        var progress = Math.min((timestamp - startTime) / duration, 1);
        var eased = 1 - Math.pow(1 - progress, 3);
        el.textContent = Math.floor(eased * target).toLocaleString();
        if (progress < 1) requestAnimationFrame(step);
        else el.textContent = target.toLocaleString();
      }
      requestAnimationFrame(step);
    });
  }
  var statsRow = document.querySelector(".stats-row");
  if (statsRow && "IntersectionObserver" in window) {
    var counterIO = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) {
        if (en.isIntersecting) { animateCounters(); counterIO.unobserve(en.target); }
      });
    }, { threshold: 0.3 });
    counterIO.observe(statsRow);
  }

  /* ---- Leaflet map ---- */
  function initMap() {
    var mapEl = document.getElementById("map");
    if (typeof L === "undefined" || !mapEl) return;
    var lat = parseFloat(mapEl.getAttribute("data-lat")) || 19.4326;
    var lng = parseFloat(mapEl.getAttribute("data-lng")) || -99.1332;
    var map = L.map("map", { scrollWheelZoom: false }).setView([lat, lng], 15);

    /* Proveedores de tiles. Los mosaicos de OpenStreetMap pueden devolver
       403 ("osm.wiki/blocked") desde algunas redes (p. ej. usuarios
       corporativos/ISP), así que usamos CARTO como principal y OSM como
       respaldo; si falla el primero, se prueba el siguiente. */
    var provedores = [
      {
        url: "https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}.png",
        opciones: {
          attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="https://carto.com/attributions">CARTO</a>',
          subdomains: "abcd"
        },
        prueba: "https://a.basemaps.cartocdn.com/rastertiles/voyager/3/3/3.png"
      },
      {
        url: "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
        opciones: {
          attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
        },
        prueba: "https://a.tile.openstreetmap.org/3/3/3.png"
      }
    ];

    var indice = 0;
    function cargarProveedor(i) {
      var p = provedores[i];
      if (!p) return;
      var tile = L.tileLayer(p.url, p.opciones).addTo(map);
      tile.on("tileerror", function () {
        tile.remove();
        cargarProveedor(i + 1);
      });
    }
    cargarProveedor(0);

    var icon = L.divIcon({
      className: "custom-marker",
      html: '<div style="background:#E63946;width:36px;height:36px;border-radius:50%;border:3px solid #fff;box-shadow:0 2px 10px rgba(0,0,0,.3);display:grid;place-items:center;color:#fff;font-weight:900;font-size:.8rem;font-family:Montserrat,sans-serif">SA</div>',
      iconSize: [36, 36], iconAnchor: [18, 18]
    });
    L.marker([lat, lng], { icon: icon }).addTo(map)
      .bindPopup("<strong>Servicios Automotores S.A</strong><br>Av. Principal #1250, Zona Industrial<br>Lun-Vie: 8:00 — 18:00").openPopup();
  }
  if (typeof L !== "undefined") initMap();
  else window.addEventListener("load", initMap);

  /* ---- Gallery lightbox ---- */
  var lightbox = document.getElementById("lightbox");
  var lbImg = document.getElementById("lightboxImg");
  var galleryImages = [];
  var currentIdx = 0;
  document.querySelectorAll("[data-lightbox]").forEach(function (item, i) {
    var img = item.querySelector("img");
    if (img) galleryImages.push({ src: img.dataset.full || img.src, alt: img.alt });
    item.addEventListener("click", function () {
      currentIdx = i;
      openLightbox(galleryImages[i].src, galleryImages[i].alt);
    });
  });
  function openLightbox(src, alt) {
    if (!lightbox) return;
    lbImg.src = src; lbImg.alt = alt || "";
    lightbox.classList.add("active");
    document.body.style.overflow = "hidden";
  }
  if (lightbox) {
    lightbox.querySelector(".lightbox-close").addEventListener("click", closeLightbox);
    lightbox.addEventListener("click", function (e) { if (e.target === lightbox) closeLightbox(); });
    lightbox.querySelector(".lightbox-prev").addEventListener("click", function (e) {
      e.stopPropagation();
      currentIdx = (currentIdx - 1 + galleryImages.length) % galleryImages.length;
      lbImg.src = galleryImages[currentIdx].src; lbImg.alt = galleryImages[currentIdx].alt;
    });
    lightbox.querySelector(".lightbox-next").addEventListener("click", function (e) {
      e.stopPropagation();
      currentIdx = (currentIdx + 1) % galleryImages.length;
      lbImg.src = galleryImages[currentIdx].src; lbImg.alt = galleryImages[currentIdx].alt;
    });
    document.addEventListener("keydown", function (e) {
      if (!lightbox.classList.contains("active")) return;
      if (e.key === "Escape") closeLightbox();
      if (e.key === "ArrowLeft") lightbox.querySelector(".lightbox-prev").click();
      if (e.key === "ArrowRight") lightbox.querySelector(".lightbox-next").click();
    });
  }
  function closeLightbox() {
    if (!lightbox) return;
    lightbox.classList.remove("active");
    document.body.style.overflow = "";
  }

  /* ---- Contact form validation ---- */
  var form = document.getElementById("contactForm");
  var submitBtn = document.getElementById("submitBtn");
  var formSuccess = document.getElementById("formSuccess");
  if (form) {
    form.addEventListener("submit", function (e) {
      e.preventDefault();
      var valid = true;
      form.querySelectorAll("[required]").forEach(function (input) {
        var feedback = input.parentElement.querySelector(".invalid-feedback");
        input.classList.remove("is-invalid");
        if (feedback) feedback.textContent = "";
        if (!input.value.trim()) {
          input.classList.add("is-invalid");
          if (feedback) feedback.textContent = "Este campo es obligatorio.";
          valid = false;
        } else if (input.type === "email" && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(input.value)) {
          input.classList.add("is-invalid");
          if (feedback) feedback.textContent = "Ingresa un correo electrónico válido.";
          valid = false;
        }
      });
      if (valid) {
        submitBtn.disabled = true;
        submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2" role="status"></span>Enviando...';
        setTimeout(function () {
          form.classList.add("hide");
          formSuccess.classList.add("show");
        }, 1200);
      }
    });
    form.querySelectorAll("input, select, textarea").forEach(function (el) {
      el.addEventListener("input", function () {
        this.classList.remove("is-invalid");
        var fb = this.parentElement.querySelector(".invalid-feedback");
        if (fb) fb.textContent = "";
      });
    });
  }
  window.resetForm = function () {
    if (form) form.reset();
    if (form) form.classList.remove("hide");
    if (formSuccess) formSuccess.classList.remove("show");
    if (submitBtn) { submitBtn.disabled = false; submitBtn.innerHTML = '<i class="bi bi-send me-2"></i>Enviar mensaje'; }
  };

})();
