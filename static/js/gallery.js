/**
 * Gallery enhancements (E1): a zoom that follows the pointer, a lightbox, and thumbnails that
 * mark whichever shot is in view.
 *
 * None of it is load-bearing. The thumbnails are anchors into a scroll-snap track, the frame
 * links to the full-size file, and the CSS zooms from the centre on hover, so a visitor with
 * no JavaScript loses only the polish (P6).
 *
 * The listeners are delegated from the document rather than bound to the gallery, because
 * variant-picker.js replaces that node on a colour swap and anything bound to it would be
 * left listening to an element no longer on the page.
 */

const trackPointer = (event) => {
  const frame = event.target.closest?.(".gallery__frame");
  if (!frame) return;
  const box = frame.getBoundingClientRect();
  frame.style.setProperty("--zoom-x", `${((event.clientX - box.left) / box.width) * 100}%`);
  frame.style.setProperty("--zoom-y", `${((event.clientY - box.top) / box.height) * 100}%`);
};

/** One <dialog>, built on demand: the markup should not carry a control nothing can open. */
const lightbox = () => {
  let dialog = document.getElementById("lightbox");
  if (dialog) return dialog;
  dialog = document.createElement("dialog");
  dialog.id = "lightbox";
  dialog.className = "modal lightbox";
  dialog.innerHTML = '<img alt="" class="lightbox__art">';
  // A click anywhere lands on the dialog itself rather than the image, which is the whole
  // dismissal gesture. Escape is the element's own.
  dialog.addEventListener("click", () => dialog.close());
  document.body.append(dialog);
  return dialog;
};

/** Marks the thumbnail for whichever slide the track is scrolled to, swipe included. */
const watchThumbs = () => {
  const gallery = document.querySelector("[data-gallery]");
  const track = gallery?.querySelector(".gallery__track");
  const thumbs = [...(gallery?.querySelectorAll("[data-gallery-thumb]") ?? [])];
  if (!track || !thumbs.length) return;

  const slides = [...gallery.querySelectorAll(".gallery__slide")];
  const watcher = new IntersectionObserver(
    (entries) => {
      for (const entry of entries) {
        if (!entry.isIntersecting) continue;
        const index = slides.indexOf(entry.target);
        for (const thumb of thumbs) {
          thumb.classList.toggle(
            "gallery__thumb--current",
            Number(thumb.dataset.galleryThumb) === index,
          );
        }
      }
    },
    { root: track, threshold: 0.6 },
  );
  for (const slide of slides) watcher.observe(slide);
};

if (document.querySelector("[data-gallery]")) {
  document.addEventListener("pointermove", trackPointer);

  document.addEventListener("click", (event) => {
    const frame = event.target.closest("[data-gallery-open]");
    const plain = event.button === 0 && !event.metaKey && !event.ctrlKey && !event.shiftKey;
    if (!frame || !plain) return;
    event.preventDefault();
    const dialog = lightbox();
    const shot = dialog.querySelector("img");
    shot.src = frame.href;
    shot.alt = frame.querySelector("img")?.alt ?? "";
    dialog.showModal();
  });

  watchThumbs();
  // variant-picker.js announces a colour swap, which brings a new gallery with it.
  document.addEventListener("cf:swap", watchThumbs);
}
