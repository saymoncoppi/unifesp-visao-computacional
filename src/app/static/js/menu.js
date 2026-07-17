import { el } from "./dom.js";
import { applyLanguage, applyTheme, applyInspector } from "./preferences.js";
import { runAction } from "./actions.js";

// ===================================================== Open/close menu
function openMenu() { el.menuPanel.hidden = false; el.menuButton.setAttribute("aria-expanded", "true"); }
function closeMenu() { el.menuPanel.hidden = true; el.menuButton.setAttribute("aria-expanded", "false"); }

export function initMenu() {
  el.menuButton.addEventListener("click", function (e) {
    e.stopPropagation();
    if (el.menuPanel.hidden) openMenu(); else closeMenu();
  });
  el.menuPanel.addEventListener("click", function (evt) {
    var item = evt.target.closest("[data-language],[data-theme],[data-inspector],[data-action]");
    if (!item) return;
    if (item.hasAttribute("data-language")) applyLanguage(item.getAttribute("data-language"));
    else if (item.hasAttribute("data-theme")) applyTheme(item.getAttribute("data-theme"));
    else if (item.hasAttribute("data-inspector")) applyInspector(item.getAttribute("data-inspector"));
    else if (item.hasAttribute("data-action")) runAction(item.getAttribute("data-action"));
    closeMenu();
  });
  document.addEventListener("click", function (e) {
    if (!el.menuPanel.hidden && !el.menu.contains(e.target)) closeMenu();
  });
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape" && !el.menuPanel.hidden) { closeMenu(); el.menuButton.focus(); }
  });
}
