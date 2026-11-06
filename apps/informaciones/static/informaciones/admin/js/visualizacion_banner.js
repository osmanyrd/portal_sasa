/* Visualización del banner — asistente del editor de Novedades.
 *
 * Ayuda menor en el panel de Wagtail: cuando el modo de banner es
 * "Completo" (que llena todo el banner), el selector de tamaño de la
 * miniatura deja de tener efecto, así que se oculta para no confundir.
 * En "Miniatura" o "Automático" se vuelve a mostrar.
 */
(function () {
  "use strict";

  function actualizar() {
    var modo = document.getElementById("id_modo_banner");
    var tamano = document.getElementById("id_tamano_miniatura");
    if (!modo || !tamano) {
      return; // esta página no tiene los campos (no es Novedad)
    }
    var contenedor = tamano.closest(".field, .field-row");
    if (!contenedor) {
      return;
    }
    var oculto = modo.value === "completo";
    if (oculto) {
      contenedor.style.display = "none";
    } else {
      contenedor.style.display = "";
    }
  }

  document.addEventListener("DOMContentLoaded", function () {
    var modo = document.getElementById("id_modo_banner");
    if (!modo) {
      return;
    }
    actualizar();
    modo.addEventListener("change", actualizar);
  });
})();