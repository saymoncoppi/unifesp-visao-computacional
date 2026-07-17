import { el } from "./dom.js";

// ===================================================== Lightbox
// Clicking an image in the chat (the labels the user sent) opens it at full
// size in an overlay. Uses event delegation on #chat so images added later
// (each new submission) work without re-wiring.

function openLightbox(src, alt) {
  el.lightboxImg.src = src;
  el.lightboxImg.alt = alt || "";
  el.lightboxModal.hidden = false;
}

function closeLightbox() {
  el.lightboxModal.hidden = true;
  el.lightboxImg.removeAttribute("src");
}

export function initLightbox() {
  el.chat.addEventListener("click", function (e) {
    var img = e.target.closest && e.target.closest("img.sent-image");
    if (!img) return;
    openLightbox(img.src, img.alt);
  });
  el.lightboxClose.addEventListener("click", closeLightbox);
  el.lightboxModal.addEventListener("click", function (e) {
    if (e.target === el.lightboxModal) closeLightbox();   // backdrop = close
  });
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape" && !el.lightboxModal.hidden) closeLightbox();
  });
}
