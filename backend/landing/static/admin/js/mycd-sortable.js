"use strict";

(function () {
  function csrfToken() {
    const part = document.cookie.split(";").map(function (item) { return item.trim(); })
      .find(function (item) { return item.startsWith("csrftoken="); });
    return part ? part.split("=")[1] : "";
  }

  document.addEventListener("DOMContentLoaded", function () {
    const tbody = document.querySelector("#result_list tbody");
    const config = document.querySelector("#mycd-reorder-config");
    const status = document.querySelector("#mycd-reorder-status");
    if (!tbody || !config) return;
    let dragged = null;

    function idFor(row) {
      const checkbox = row.querySelector(".action-select");
      return checkbox ? checkbox.value : null;
    }

    async function move(row, target, after) {
      const response = await fetch(config.dataset.url, {
        method: "POST",
        credentials: "same-origin",
        headers: {"Content-Type": "application/json", "X-CSRFToken": csrfToken()},
        body: JSON.stringify({item_id: idFor(row), target_id: idFor(target), position: after ? "after" : "before"})
      });
      if (!response.ok) {
        status.textContent = "No se pudo guardar el orden. Recargá la página.";
        return;
      }
      tbody.insertBefore(row, after ? target.nextSibling : target);
      const position = Array.from(tbody.rows).indexOf(row) + 1;
      status.textContent = `Elemento movido a la posición visible ${position}; orden global guardado.`;
      row.setAttribute("aria-label", `Elemento reordenable, posición visible ${position}. Alt y flechas para mover.`);
      row.focus();
    }

    Array.from(tbody.rows).forEach(function (row) {
      if (!idFor(row)) return;
      row.draggable = true;
      row.tabIndex = 0;
      row.dataset.mycdSortable = "true";
      row.setAttribute("aria-label", "Elemento reordenable. Usá Alt y flecha arriba o abajo para moverlo.");
      row.addEventListener("dragstart", function () { dragged = row; row.dataset.mycdDragging = "true"; });
      row.addEventListener("dragend", function () { delete row.dataset.mycdDragging; dragged = null; });
      row.addEventListener("dragover", function (event) { if (dragged && dragged !== row) event.preventDefault(); });
      row.addEventListener("drop", function (event) {
        event.preventDefault();
        if (!dragged || dragged === row) return;
        move(dragged, row, event.clientY > row.getBoundingClientRect().top + row.offsetHeight / 2);
      });
      row.addEventListener("keydown", function (event) {
        if (!event.altKey || !["ArrowUp", "ArrowDown"].includes(event.key)) return;
        const target = event.key === "ArrowUp" ? row.previousElementSibling : row.nextElementSibling;
        if (!target) return;
        event.preventDefault();
        move(row, target, event.key === "ArrowDown");
      });
    });
  });
})();
