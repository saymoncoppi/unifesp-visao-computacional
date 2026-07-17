import { el } from "./dom.js";
import { t } from "./i18n.js";
import { scrollBottom, resetComposer } from "./composer.js";

// ===================================================== Menu actions
export function exportToPdf() {
  // Force light theme (readable PDF) and print only the conversation (see @media print).
  var prev = el.root.getAttribute("data-theme");
  el.root.setAttribute("data-theme", "light");
  function restore() {
    if (prev === null) el.root.removeAttribute("data-theme");
    else el.root.setAttribute("data-theme", prev);
    window.removeEventListener("afterprint", restore);
  }
  window.addEventListener("afterprint", restore);
  if (window.print) window.print(); else restore();
}

export function clearChat() {
  // Removes all messages and recreates the initial greeting in the current language.
  el.chat.innerHTML = "";
  var row = document.createElement("div");
  row.className = "msg msg-bot";
  var av = document.createElement("img");
  av.className = "avatar";
  av.src = "/static/img/logo.svg";
  av.alt = "";
  var bub = document.createElement("div");
  bub.className = "bubble";
  bub.setAttribute("data-i18n-html", "greeting");
  bub.innerHTML = t("greeting");
  row.appendChild(av);
  row.appendChild(bub);
  el.chat.appendChild(row);
  // Resets the composer.
  resetComposer();
  scrollBottom();
}

export function runAction(action) {
  if (action === "export-pdf") exportToPdf();
  else if (action === "clear") clearChat();
}
