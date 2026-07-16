import { el } from "./dom.js";
import { state, ls } from "./state.js";
import { LANGUAGES, THEMES } from "./translations.js";
import { applyTheme, applyLanguage, applyInspector, initModelLabel } from "./preferences.js";
import { initFileInput, initHtmx } from "./composer.js";
import { initMenu } from "./menu.js";

// ===================================================== Initialization
(function initState() {
  var si = ls("language");
  state.language = LANGUAGES.indexOf(si) >= 0 ? si : (el.root.getAttribute("lang") || "pt-BR");
  if (LANGUAGES.indexOf(state.language) < 0) state.language = "pt-BR";

  var st = ls("theme");
  state.theme = THEMES.indexOf(st) >= 0 ? st : "auto";

  // "Auto" only exists when an LLM is configured on the server (.env).
  var hasGemini = !!(window.INSPECTOR_CONFIG && window.INSPECTOR_CONFIG.hasGemini);
  var autoItem = document.getElementById("inspector-auto");
  if (!hasGemini && autoItem) autoItem.style.display = "none";
  var validInspectors = hasGemini ? ["llm", "kb", "auto"] : ["llm", "kb"];

  var sp = ls("inspector");
  state.inspector = validInspectors.indexOf(sp) >= 0 ? sp : "llm";

  applyTheme(state.theme);           // theme first (avoids a color flash)
  initModelLabel();
  applyLanguage(state.language);     // translates the page and marks the language
  applyInspector(state.inspector);   // marks the chosen inspector
})();

initFileInput();
initHtmx();
initMenu();
