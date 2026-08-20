"use strict";

(function () {
  function orderInput(row) {
    return row.querySelector('input[name$="-order"]');
  }

  function synchronize(tbody) {
    Array.from(tbody.rows).forEach(function (row, index) {
      const input = orderInput(row);
      if (input) {
        input.value = String(index);
        input.dispatchEvent(new Event("change", { bubbles: true }));
      }
    });
  }

  function move(row, target, after) {
    const tbody = row.parentElement;
    tbody.insertBefore(row, after ? target.nextSibling : target);
    synchronize(tbody);
    row.focus();
  }

  document.addEventListener("DOMContentLoaded", function () {
    const tbody = document.querySelector("#result_list tbody");
    if (!tbody) return;

    let dragged = null;
    Array.from(tbody.rows).forEach(function (row) {
      if (!orderInput(row)) return;
      row.draggable = true;
      row.tabIndex = 0;
      row.dataset.mycdSortable = "true";
      row.setAttribute(
        "aria-label",
        "Elemento reordenable. Usá Alt y flecha arriba o abajo para moverlo."
      );

      row.addEventListener("dragstart", function () {
        dragged = row;
        row.dataset.mycdDragging = "true";
      });
      row.addEventListener("dragend", function () {
        delete row.dataset.mycdDragging;
        dragged = null;
      });
      row.addEventListener("dragover", function (event) {
        if (dragged && dragged !== row) event.preventDefault();
      });
      row.addEventListener("drop", function (event) {
        event.preventDefault();
        if (!dragged || dragged === row) return;
        const below = event.clientY > row.getBoundingClientRect().top + row.offsetHeight / 2;
        move(dragged, row, below);
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
