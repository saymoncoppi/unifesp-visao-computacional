import { el } from "./dom.js";
import { state } from "./state.js";
import { t } from "./i18n.js";

// ===================================================== Scrolling / preview
export function scrollBottom() {
  el.main.scrollTop = el.main.scrollHeight;
}

export function resetFileName() {
  el.fileName.setAttribute("data-i18n", "file_none");
  el.fileName.textContent = t("file_none");
}
export function showFileName(name) {
  el.fileName.removeAttribute("data-i18n");   // prevents translation from overwriting the name
  el.fileName.textContent = name;
}

export function initFileInput() {
  el.input.addEventListener("change", function () {
    var f = el.input.files && el.input.files[0];
    if (!f) {
      el.thumb.classList.remove("show");
      resetFileName();
      el.submit.disabled = true;
      return;
    }
    showFileName(f.name);
    el.submit.disabled = false;
    var reader = new FileReader();
    reader.onload = function (e) {
      el.thumb.src = e.target.result;
      el.thumb.classList.add("show");
    };
    reader.readAsDataURL(f);
  });
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
    el.form.reset();
    el.thumb.classList.remove("show");
    el.thumb.removeAttribute("src");
    resetFileName();
    el.submit.disabled = true;
    scrollBottom();
  });
}
