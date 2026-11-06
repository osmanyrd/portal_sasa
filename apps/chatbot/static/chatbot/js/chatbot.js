/**
 * Chatbot RAG — Widget JavaScript.
 *
 * Widget de chat flotante para Servicios Automotores S.A.
 *
 * Endpoints usados:
 *   GET  /api/chatbot/info/       configuración pública del widget
 *   POST /api/chatbot/consulta/   preguntas al asistente RAG
 *   POST /api/chatbot/feedback/   valoración 👍 / 👎
 *   POST /api/chatbot/escalar/    solicitud de contacto humano
 *   POST /api/chatbot/historial/  carga de conversación previa
 *   POST /api/chatbot/limpiar/    cerrar sesión
 *
 * Renderizado ligero de Markdown: **negrita**, _cursiva_, [enlaces](url),
 * listas con "- " y saltos de línea.
 */
(function () {
  "use strict";

  /* ── URLs ──────────────────────────────────────────────────────────────── */
  var API_BASE = "/api/chatbot/";
  var URL_INFO     = API_BASE + "info/";
  var URL_CONSULTA = API_BASE + "consulta/";
  var URL_FEEDBACK = API_BASE + "feedback/";
  var URL_ESCALAR  = API_BASE + "escalar/";
  var URL_HISTORIAL = API_BASE + "historial/";
  var URL_LIMPIAR  = API_BASE + "limpiar/";

  /* ── Constantes locales ────────────────────────────────────────────────── */
  var BIENVENIDA_DEFECTO =
    "¡Hola! Soy el asistente de Servicios Automotores S.A. " +
    "¿En qué puedo ayudarte?";
  var FOOTER_DEFECTO = "Respuestas con información del sitio web";
  var STORAGE_PREFIX  = "sasa_chatbot_";
  var STORAGE_THEME   = STORAGE_PREFIX + "theme";

  /* ── Elementos DOM ─────────────────────────────────────────────────────── */
  var trigger      = document.getElementById("chatbotTrigger");
  var win          = document.getElementById("chatbotWindow");
  var messagesEl   = document.getElementById("chatbotMessages");
  var inputEl      = document.getElementById("chatbotInput");
  var sendBtn      = document.getElementById("chatbotSend");
  var typingEl     = document.getElementById("chatbotTyping");
  var clearBtn     = document.getElementById("chatbotClear");
  var closeBtn     = document.getElementById("chatbotClose");
  var themeBtn     = document.getElementById("chatbotTheme");
  var backdropEl   = document.getElementById("chatbotBackdrop");
  var avatarEl     = document.getElementById("chatbotAvatar");
  var nameEl       = document.getElementById("chatbotName");
  var footerTextEl = document.getElementById("chatbotFooterText");
  var escaladoEl   = document.getElementById("chatbotEscalado");
  var escaladoCloseBtn = document.getElementById("chatbotEscaladoClose");
  var escaladoSendBtn  = document.getElementById("chatbotEscaladoSend");
  var escaladoNombreEl = document.getElementById("escaladoNombre");
  var escaladoTelEl    = document.getElementById("escaladoTelefono");
  var escaladoMotivoEl = document.getElementById("escaladoMotivo");

  if (!trigger || !win) return;

  /* ── Estado ─────────────────────────────────────────────────────────────── */
  var isOpen       = false;
  var isSending    = false;
  var sessionId    = sessionStorage.getItem(STORAGE_PREFIX + "session_id") || "";
  var bienvenidaMostrada = false;
  var infoLoaded   = false;

  /* ── Registro en el panel manager (survey/menu) ────────────────────────── */
  function cerrarChat() {
    if (!isOpen) return;
    isOpen = false;
    win.classList.remove("open");
    trigger.classList.remove("open");
    if (backdropEl) backdropEl.classList.remove("is-visible");
    hideEscalado();
  }

  function abrirChat() {
    if (isOpen) return;
    if (window.__panelManager) window.__panelManager.closeAll(cerrarChat);
    isOpen = true;
    win.classList.add("open");
    trigger.classList.add("open");
    if (backdropEl) backdropEl.classList.add("is-visible");
    inputEl.focus();
    var badge = trigger.querySelector(".badge-dot");
    if (badge) badge.remove();
    if (!infoLoaded) fetchInfo();
    if (!bienvenidaMostrada) mostrarBienvenida();
  }

  if (window.__panelManager) window.__panelManager.register(cerrarChat);

  function toggleChat() {
    isOpen ? cerrarChat() : abrirChat();
  }

  trigger.addEventListener("click", toggleChat);
  if (closeBtn) closeBtn.addEventListener("click", function () { cerrarChat(); trigger.focus(); });
  if (backdropEl) backdropEl.addEventListener("click", cerrarChat);

  /* ── Tema claro / oscuro ────────────────────────────────────────────────── */
  function aplicarTema(dark) {
    document.documentElement.classList.toggle("chatbot-dark", dark);
    if (themeBtn) themeBtn.querySelector(".ic-theme").className = "bi " + (dark ? "bi-sun-fill" : "bi-moon-stars-fill") + " ic-theme";
    localStorage.setItem(STORAGE_THEME, dark ? "1" : "0");
  }
  (function () { aplicarTema(localStorage.getItem(STORAGE_THEME) === "1"); })();
  if (themeBtn) themeBtn.addEventListener("click", function () {
    aplicarTema(!document.documentElement.classList.contains("chatbot-dark"));
  });

  /* ── Markdown-lite ──────────────────────────────────────────────────────── */
  function renderBotHTML(text) {
    if (!text) return "";
    text = String(text);
    var lineas = text.split("\n");
    var html = "";
    var enLista = false;
    lineas.forEach(function (linea) {
      var itemMatch = linea.match(/^\s*-\s+(.*)$/);
      if (itemMatch) {
        if (!enLista) { html += '<ul class="bot-list">'; enLista = true; }
        html += "<li>" + inlineFormat(itemMatch[1]) + "</li>";
      } else {
        if (enLista) { html += "</ul>"; enLista = false; }
        html += "<p>" + inlineFormat(linea || "&nbsp;") + "</p>";
      }
    });
    if (enLista) html += "</ul>";
    return html;
  }

  function inlineFormat(s) {
    s = s.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
    s = s.replace(/_(.+?)_/g, "<em>$1</em>");
    s = s.replace(/\[(.+?)\]\((https?:[^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');
    s = s.replace(/(https?:\/\/[^\s<]+)/g, function (url) {
      if (url.indexOf("<a href=") !== -1) return url;
      return '<a href="' + url + '" target="_blank" rel="noopener">' + url + '</a>';
    });
    return s;
  }

  /* ── Agregar mensaje al DOM ─────────────────────────────────────────────── */
  function appendMsg(role, html, meta) {
    meta = meta || {};
    var wrapper = document.createElement("div");
    wrapper.className = "msg msg-" + role + (meta.id ? " msg-id-" + meta.id : "");

    if (role === "bot") {
      wrapper.innerHTML =
        '<div class="bot-avatar-sm">SA</div>' +
        '<div class="bot-body">' +
        '<div class="bot-bubble">' + html + '</div>' +
        (meta.fuentes && meta.fuentes.length ? renderFuentes(meta.fuentes) : '') +
        '<div class="bot-actions">' +
          '<button class="btn-feedback btn-up" data-v="up" aria-label="Útil">👍</button>' +
          '<button class="btn-feedback btn-down" data-v="down" aria-label="No útil">👎</button>' +
          (meta.escalable ? '<button class="btn-escalado" aria-label="Contactar asesor">💬 Asesor</button>' : '') +
          '<span class="feedback-ok" hidden>Gracias</span>' +
        '</div>' +
        '</div>';
      attachFeedback(wrapper, meta.conversacionId, meta.sessionId);
      attachEscalado(wrapper, meta.sessionId);
    } else {
      wrapper.innerHTML = '<div class="user-bubble">' + html + '</div>';
    }
    messagesEl.insertBefore(wrapper, typingEl);
    scrollToBottom();
    return wrapper;
  }

  function renderFuentes(fuentes) {
    var seen = {};
    var items = "";
    fuentes.forEach(function (f) {
      var clave = f.titulo || f.fuente || "";
      if (seen[clave]) return;
      seen[clave] = true;
      var etiqueta = f.titulo || (f.fuente ? f.fuente.split("/").slice(-2).join("/") : "");
      var href = f.fuente || "#";
      if (href && href !== "#") items += '<a class="fuente-chip" href="' + href + '" target="_blank" rel="noopener">' + etiqueta + '</a>';
    });
    return items ? '<div class="fuentes-wrap">' + items + '</div>' : "";
  }

  function attachFeedback(wrapper, convId, sid) {
    wrapper.querySelectorAll(".btn-feedback").forEach(function (btn) {
      btn.addEventListener("click", function () {
        if (wrapper.dataset.rated) return;
        wrapper.dataset.rated = "1";
        fetch(URL_FEEDBACK, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ session_id: sid || sessionId, conversacion_id: convId || "", valoracion: btn.dataset.v })
        }).catch(function () {});
        var okEl = wrapper.querySelector(".feedback-ok");
        if (okEl) okEl.hidden = false;
        wrapper.querySelectorAll(".btn-feedback").forEach(function (b) { b.disabled = true; b.style.opacity = "0.4"; });
      });
    });
  }

  function attachEscalado(wrapper, sid) {
    var btn = wrapper.querySelector(".btn-escalado");
    if (!btn) return;
    btn.addEventListener("click", function () {
      showEscalado(sid || sessionId);
    });
  }

  /* ── Escalado a humano ──────────────────────────────────────────────────── */
  function showEscalado(sid) {
    if (!escaladoEl) return;
    escaladoEl.hidden = false;
    escaladoMotivoEl.value = escaladoMotivoEl.value || "";
    escaladoMotivoEl.focus();
    sessionId = sid || sessionId;
  }
  function hideEscalado() {
    if (escaladoEl) escaladoEl.hidden = true;
  }
  if (escaladoCloseBtn) escaladoCloseBtn.addEventListener("click", hideEscalado);
  if (escaladoSendBtn) escaladoSendBtn.addEventListener("click", function () {
    var motivo = escaladoMotivoEl.value.trim();
    if (!motivo) { escaladoMotivoEl.focus(); return; }
    escaladoSendBtn.disabled = true;
    fetch(URL_ESCALAR, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        session_id: sessionId,
        nombre: escaladoNombreEl.value.trim(),
        telefono: escaladoTelEl.value.trim(),
        motivo: motivo
      })
    }).then(function (r) { return r.json(); }).then(function (d) {
      appendMsg("bot", d.mensaje || "Un asesor te contactará pronto.");
      hideEscalado();
    }).catch(function () {
      appendMsg("bot", "No se pudo enviar la solicitud. Intenta de nuevo más tarde.");
    }).then(function () {
      escaladoSendBtn.disabled = false;
      escaladoMotivoEl.value = "";
    });
  });

  /* ── Bienvenida / info ──────────────────────────────────────────────────── */
  function mostrarBienvenida() {
    if (bienvenidaMostrada) return;
    bienvenidaMostrada = true;
    appendMsg("bot", renderBotHTML(localStorage.getItem(STORAGE_PREFIX + "bienvenida") || BIENVENIDA_DEFECTO), { sessionId: sessionId });
  }

  function fetchInfo() {
    infoLoaded = true;
    fetch(URL_INFO).then(function (r) { return r.json(); }).then(function (d) {
      if (!d) return;
      localStorage.setItem(STORAGE_PREFIX + "bienvenida", d.mensaje_bienvenida || "");
      localStorage.setItem(STORAGE_PREFIX + "footer", d.aviso_privacidad || FOOTER_DEFECTO);
      if (nameEl && d.nombre_asistente) nameEl.textContent = d.nombre_asistente;
      if (footerTextEl) footerTextEl.textContent = d.aviso_privacidad || FOOTER_DEFECTO;
      if (avatarEl && d.nombre_asistente) avatarEl.textContent = (d.nombre_asistente || "SA").substring(0, 2).toUpperCase();
    }).catch(function () {});
  }

  /* ── Historial ──────────────────────────────────────────────────────────── */
  function cargarHistorial() {
    if (!sessionId) return;
    fetch(URL_HISTORIAL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: sessionId })
    }).then(function (r) { return r.json(); }).then(function (d) {
      if (!d || !d.historial || !d.historial.length) return;
      d.historial.forEach(function (m) {
        appendMsg(m.rol === "bot" ? "bot" : "user", renderBotHTML(m.contenido), { sessionId: sessionId });
      });
      bienvenidaMostrada = true;
    }).catch(function () {});
  }

  /* ── Sugerencias (chips) ────────────────────────────────────────────────── */
  function mostrarSugerencias(items) {
    if (!items || !items.length) return;
    var wrap = document.createElement("div");
    wrap.className = "sugerencias-wrap";
    items.forEach(function (s) {
      var btn = document.createElement("button");
      btn.className = "chip";
      btn.textContent = s;
      btn.addEventListener("click", function () { enviarPregunta(s); });
      wrap.appendChild(btn);
    });
    messagesEl.insertBefore(wrap, typingEl);
    scrollToBottom();
  }

  /* ── Enviar pregunta ────────────────────────────────────────────────────── */
  function enviarPregunta(texto) {
    texto = (texto || "").trim();
    if (!texto || isSending) return;
    appendMsg("user", renderBotHTML(texto));
    inputEl.value = "";
    typingEl.classList.add("visible");
    isSending = true;
    scrollToBottom();

    fetch(URL_CONSULTA, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ pregunta: texto, session_id: sessionId })
    }).then(function (r) { return r.json(); }).then(function (d) {
      if (d.error) { appendMsg("bot", d.error); return; }
      if (d.session_id && d.session_id !== sessionId) {
        sessionId = d.session_id;
        sessionStorage.setItem(STORAGE_PREFIX + "session_id", sessionId);
      }
      appendMsg("bot", renderBotHTML(d.respuesta), {
        conversacionId: d.conversacion_id || "",
        sessionId: sessionId,
        fuentes: d.fuentes || [],
        escalable: !!d.escalable
      });
      mostrarSugerencias(d.sugerencias);
    }).catch(function () {
      appendMsg("bot", "Lo siento, hubo un problema de conexión. Intentá de nuevo.");
    }).then(function () {
      typingEl.classList.remove("visible");
      isSending = false;
      scrollToBottom();
    });
  }

  /* ── Limpiar conversación ───────────────────────────────────────────────── */
  function limpiar() {
    if (!confirm("¿Limpiar la conversación?")) return;
    fetch(URL_LIMPIAR, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: sessionId })
    }).catch(function () {});
    sessionId = "s_" + Date.now() + "_" + Math.random().toString(36).slice(2, 10);
    sessionStorage.setItem(STORAGE_PREFIX + "session_id", sessionId);
    messagesEl.innerHTML = "";
    bienvenidaMostrada = false;
    mostrarBienvenida();
  }

  function scrollToBottom() {
    requestAnimationFrame(function () { messagesEl.scrollTop = messagesEl.scrollHeight; });
  }

  /* ── Eventos ────────────────────────────────────────────────────────────── */
  if (clearBtn) clearBtn.addEventListener("click", limpiar);
  sendBtn.addEventListener("click", function () { enviarPregunta(inputEl.value); });
  inputEl.addEventListener("keydown", function (e) {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); enviarPregunta(inputEl.value); }
  });

  /* ── Inicializar sesión ─────────────────────────────────────────────────── */
  if (!sessionId) {
    sessionId = "s_" + Date.now() + "_" + Math.random().toString(36).slice(2, 10);
    sessionStorage.setItem(STORAGE_PREFIX + "session_id", sessionId);
  }
  fetchInfo();
  mostrarBienvenida();
  cargarHistorial();
})();
