(function () {
  var prefersReduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  /* ── Preloader ───────────────────────────────────────────── */
  var preloader = document.getElementById("preloader");
  function hidePreloader() {
    if (preloader && !preloader.classList.contains("is-done")) {
      preloader.classList.add("is-done");
      setTimeout(function () { preloader.remove(); }, 550);
    }
  }
  if (prefersReduced) {
    hidePreloader();
  } else {
    window.addEventListener("load", function () {
      setTimeout(hidePreloader, 320);
    });
    setTimeout(hidePreloader, 2600);
  }

  /* ── Nav: cierre de drawer al navegar (el drawer se gestiona en navbar.js) ── */
  document.querySelectorAll(".navbar-sa__drawer-nav a, .navbar-sa__menu .nav-link").forEach(function (link) {
    link.addEventListener("click", function () {
      var overlay = document.getElementById("navOverlay");
      var drawer = document.getElementById("navDrawer");
      if (overlay) overlay.hidden = true;
      if (drawer) {
        drawer.classList.remove("is-open");
        drawer.setAttribute("aria-hidden", "true");
      }
      document.body.classList.remove("nav-drawer-open");
      document.body.style.position = "";
      document.body.style.width = "";
    });
  });

  /* ── Scroll reveal ──────────────────────────────────────── */
  var AUTO_REVEAL = [
    ".hero-section h1",
    ".hero-section p",
    ".hero-section .btn",
    ".page-header h1",
    ".page-header p",
    ".card-hover",
    ".icon-bubble",
    ".feature-list li",
    ".testimonial",
    ".cta-block",
    ".gallery-item",
    ".social-link",
    ".rich-text h2",
    ".rich-text h3"
  ];

  function initReveal() {
    document.querySelectorAll(AUTO_REVEAL.join(",")).forEach(function (el) {
      if (!el.hasAttribute("data-reveal") && !el.closest("[data-reveal]")) {
        el.setAttribute("data-reveal", "");
      }
    });
    var els = document.querySelectorAll("[data-reveal]:not(.is-visible)");
    if (prefersReduced || !("IntersectionObserver" in window)) {
      els.forEach(function (el) { el.classList.add("is-visible"); });
      return;
    }
    var groups = new Map();
    els.forEach(function (el) {
      var p = el.parentElement;
      var n = groups.get(p) || 0;
      el.style.setProperty("--reveal-delay", Math.min(n * 90, 450) + "ms");
      groups.set(p, n + 1);
    });
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) {
        if (en.isIntersecting) {
          en.target.classList.add("is-visible");
          io.unobserve(en.target);
        }
      });
    }, { threshold: 0.12, rootMargin: "0px 0px -45px" });
    els.forEach(function (el) { io.observe(el); });
  }
  initReveal();

  /* ── Scroll progress + Navbar is-scrolled + Back-to-top ─── */
  var bar = document.getElementById("scrollProgress");
  var nav = document.querySelector(".navbar-sa");
  var top = document.getElementById("backToTop");
  var ticking = false;

  function onScroll() {
    var y = window.scrollY || document.documentElement.scrollTop;
    var max = document.documentElement.scrollHeight - window.innerHeight;
    if (bar) bar.style.transform = "scaleX(" + (max > 0 ? y / max : 0) + ")";
    if (nav) nav.classList.toggle("is-scrolled", y > 10);
    if (top) top.classList.toggle("show", y > 560);
    ticking = false;
  }
  window.addEventListener("scroll", function () {
    if (!ticking) { requestAnimationFrame(onScroll); ticking = true; }
  }, { passive: true });
  onScroll();
  if (top) {
    top.addEventListener("click", function () {
      window.scrollTo({ top: 0, behavior: prefersReduced ? "auto" : "smooth" });
    });
  }

  /* ── HTMX: scroll al tope + estado de carga en formulario ── */
  document.body.addEventListener("htmx:beforeSwap", function () {
    window.scrollTo({ top: 0, behavior: prefersReduced ? "auto" : "smooth" });
  });

  document.body.addEventListener("htmx:beforeRequest", function (evt) {
    var f = evt.detail.elt && evt.detail.elt.closest && evt.detail.elt.closest("form");
    if (!f) return;
    var btn = f.querySelector('[type="submit"]');
    if (btn) { btn.classList.add("btn-loading"); btn.disabled = true; }
  });

  document.body.addEventListener("htmx:afterRequest", function () {
    document.querySelectorAll(".btn-loading").forEach(function (b) {
      b.classList.remove("btn-loading");
      b.disabled = false;
    });
  });

})();
