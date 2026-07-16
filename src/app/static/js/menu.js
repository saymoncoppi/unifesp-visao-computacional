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
    var item = evt.target.closest("[data-idioma],[data-tema],[data-inspector],[data-acao]");
    if (!item) return;
    if (item.hasAttribute("data-idioma")) applyLanguage(item.getAttribute("data-idioma"));
    else if (item.hasAttribute("data-tema")) applyTheme(item.getAttribute("data-tema"));
    else if (item.hasAttribute("data-inspector")) applyInspector(item.getAttribute("data-inspector"));
    else if (item.hasAttribute("data-acao")) runAction(item.getAttribute("data-acao"));
    closeMenu();
  });
  document.addEventListener("click", function (e) {
    if (!el.menuPanel.hidden && !el.menu.contains(e.target)) closeMenu();
  });
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape" && !el.menuPanel.hidden) { closeMenu(); el.menuButton.focus(); }
  });
}
