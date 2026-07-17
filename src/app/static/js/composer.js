import { el } from "./dom.js";
import { state } from "./state.js";
import { t } from "./i18n.js";

// ===================================================== Scrolling
export function scrollBottom() {
  el.main.scrollTop = el.main.scrollHeight;
}

// ===================================================== Message timestamps
// Small muted "HH:MM" placed above each bubble (WhatsApp-like). Added on the
// client so it stays consistent across greeting, sent images, scanned codes,
// and server-rendered report cards.
function nowLabel() {
  var d = new Date();
  var hh = String(d.getHours()).padStart(2, "0");
  var mm = String(d.getMinutes()).padStart(2, "0");
  return hh + ":" + mm;
}

// Prepends a .msg-time to a message row (no-op if it already has one).
export function stampTime(msgEl) {
  if (!msgEl || msgEl.querySelector(":scope > .msg-time")) return;
  var span = document.createElement("span");
  span.className = "msg-time";
  span.textContent = nowLabel();
  msgEl.insertBefore(span, msgEl.firstChild);
}

// Stamps every message row that doesn't have a time yet (e.g. the greeting and
// server-appended report cards).
export function stampUnstamped() {
  var rows = el.chat.querySelectorAll(".msg");
  for (var i = 0; i < rows.length; i++) stampTime(rows[i]);
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
      stampTime(row);
      scrollBottom();
    };
    reader.readAsDataURL(f);
  });

  // After the response arrives and is appended, stamp it and scroll down.
  document.body.addEventListener("htmx:afterSwap", function () {
    stampUnstamped();
    scrollBottom();
  });

  // Clears the composer when the request finishes (success or error).
  document.body.addEventListener("htmx:afterRequest", function (evt) {
    if (evt.target !== el.form) return;
    resetComposer();
    scrollBottom();
  });
}
