/**
 * Opens and closes the <dialog> elements: both the centred modal and the side drawer.
 *
 * The element does the hard parts already, which is why it was chosen: focus is trapped,
 * the page behind is inert, Escape closes, ::backdrop paints, and the entry and exit
 * transitions are declared in CSS. So this file only wires triggers to `showModal` and
 * `close`, and exports the two calls for the modules that open a dialog themselves.
 */

export function openDialog(id) {
  const dialog = document.getElementById(id);
  if (dialog instanceof HTMLDialogElement) dialog.showModal();
  return dialog;
}

export function closeDialog(id) {
  const dialog = document.getElementById(id);
  if (dialog instanceof HTMLDialogElement) dialog.close();
  return dialog;
}

document.addEventListener("click", (event) => {
  const opener = event.target.closest("[data-dialog-open]");
  if (opener) {
    event.preventDefault();
    openDialog(opener.dataset.dialogOpen);
    return;
  }

  const closer = event.target.closest("[data-dialog-close]");
  if (closer) {
    closer.closest("dialog")?.close();
    return;
  }

  // A click on the backdrop lands on the dialog itself, never on its contents, so this
  // dismisses a centred modal without a second scrim element to maintain.
  if (event.target instanceof HTMLDialogElement && event.target.classList.contains("modal")) {
    event.target.close();
  }
});
