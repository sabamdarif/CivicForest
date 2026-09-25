// Drag-to-reorder for the product image list (M8.7). Pure progressive enhancement: the
// display_order number inputs already reorder the gallery with JavaScript off, and this only
// rewrites those numbers to match the row order after a drag, so the saved sequence is the
// visible one.
function renumber(tbody) {
  tbody.querySelectorAll("tr").forEach((row, index) => {
    const order = row.querySelector('input[name$="-display_order"]');
    if (order) order.value = index;
  });
}

function wire(table) {
  const tbody = table.querySelector("tbody");
  if (!tbody) return;
  let dragging = null;

  tbody.addEventListener("dragstart", (event) => {
    dragging = event.target.closest("tr");
  });

  tbody.addEventListener("dragover", (event) => {
    event.preventDefault();
    const over = event.target.closest("tr");
    if (!dragging || !over || over === dragging) return;
    const rows = [...tbody.querySelectorAll("tr")];
    const after = rows.indexOf(over) > rows.indexOf(dragging);
    tbody.insertBefore(dragging, after ? over.nextSibling : over);
  });

  tbody.addEventListener("drop", () => renumber(tbody));
}

document.querySelectorAll("table[data-reorder]").forEach(wire);
