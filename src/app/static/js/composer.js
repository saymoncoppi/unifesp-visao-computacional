import { el } from "./dom.js";
import { state } from "./state.js";
import { t } from "./i18n.js";

// ===================================================== Scrolling
export function scrollBottom() {
  el.main.scrollTop = el.main.scrollHeight;
}

// ===================================================== Selected-file plumbing
// The htmx form always submits the file held by the #image input. The photo
// path sets it natively; the camera path (captured Blob) sets it here so both
// flows share the same submission path.
export function setImageFile(file) {
  try {
    var dt = new DataTransfer();
    if (file) dt.items.add(file);
    el.input.files = dt.files;
  } catch (e) {
    // Very old browsers without DataTransfer: the photo-pick path already
    // sets #image natively; only the camera path would be affected.
  }
}

// Clears the composer inputs (both file inputs) after an analysis or on cancel.
export function resetComposer() {
  el.form.reset();      // clears #image and #camera-input
  setImageFile(null);   // guarantees #image is empty even if reset() no-ops
}

export function initHtmx() {
  // -------------------- Sends the chosen language + inspector with the analysis
  document.body.addEventListener("htmx:configRequest", function (evt) {
    if (evt.target !== el.form) return;
    evt.detail.parameters["language"] = state.language;
    evt.detail.parameters["inspector"] = state.inspector;
  });

  // -------------------------------- Sent-image bubble (user)
  document.body.addEventListener("htmx:beforeRequest", function (evt) {
    if (evt.target !== el.form) return;
    var f = el.input.files && el.input.files[0];
    if (!f) return;
    var reader = new FileReader();
    reader.onload = function (e) {
      var row = document.createElement("div");
      row.className = "msg msg-user";
      var bubble = document.createElement("div");
      bubble.className = "bubble bubble-user";
      var img = document.createElement("img");
      img.className = "sent-image";
      img.src = e.target.result;
      img.alt = t("sent_image_alt");
      bubble.appendChild(img);
      row.appendChild(bubble);
      el.chat.appendChild(row);
      scrollBottom();
    };
    reader.readAsDataURL(f);
  });

  // After the response arrives and is appended, scroll to the bottom.
  document.body.addEventListener("htmx:afterSwap", function () {
    scrollBottom();
  });

  // Clears the composer when the request finishes (success or error).
  document.body.addEventListener("htmx:afterRequest", function (evt) {
    if (evt.target !== el.form) return;
    resetComposer();
    scrollBottom();
  });
}
