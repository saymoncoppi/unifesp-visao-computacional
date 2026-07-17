import { state, lsSet } from "./state.js";
import { el } from "./dom.js";
import { applyI18n } from "./i18n.js";

// ===================================================== Menu selection
export function markSelected(group, value) {
  var items = el.menuPanel.querySelectorAll("[data-" + group + "]");
  for (var i = 0; i < items.length; i++) {
    var sel = items[i].getAttribute("data-" + group) === value;
    items[i].classList.toggle("is-selected", sel);
    items[i].setAttribute("aria-checked", sel ? "true" : "false");
  }
}

export function applyTheme(v) {
  state.theme = v;
  if (v === "light" || v === "dark") el.root.setAttribute("data-theme", v);
  else el.root.removeAttribute("data-theme");   // "auto" -> follows the system
  lsSet("theme", v);
  markSelected("theme", v);
}

export function applyLanguage(v) {
  state.language = v;
  lsSet("language", v);
  applyI18n(v);
  markSelected("language", v);
}

export function applyInspector(v) {
  state.inspector = v;
  lsSet("inspector", v);
  markSelected("inspector", v);
  // Let the footer quota counter react (hidden for KB, shown for llm/auto).
  document.dispatchEvent(new CustomEvent("inspector-change"));
}

export function initModelLabel() {
  var cfg = window.INSPECTOR_CONFIG || {};
  var name = cfg.activeModel && String(cfg.activeModel).trim();
  el.modelLabel.textContent = name || "Gemini";
}
