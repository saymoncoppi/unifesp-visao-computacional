import { I18N } from "./translations.js";
import { state } from "./state.js";
import { el } from "./dom.js";

export function t(key) {
  var dict = I18N[state.language] || I18N["pt-BR"];
  return dict[key] != null ? dict[key] : key;
}

// Applies a translated attribute to every element with data-<attr>.
function applyAttr(dict, selector, setter) {
  var nodes = document.querySelectorAll(selector);
  for (var i = 0; i < nodes.length; i++) {
    var k = nodes[i].getAttribute(selector.slice(1, -1));
    if (dict[k] != null) setter(nodes[i], dict[k]);
  }
}

export function applyI18n(lang) {
  var dict = I18N[lang] || I18N["pt-BR"];
  applyAttr(dict, "[data-i18n]", function (node, v) { node.textContent = v; });
  applyAttr(dict, "[data-i18n-html]", function (node, v) { node.innerHTML = v; });
  applyAttr(dict, "[data-i18n-aria]", function (node, v) { node.setAttribute("aria-label", v); });
  applyAttr(dict, "[data-i18n-title]", function (node, v) { node.setAttribute("title", v); });
  applyAttr(dict, "[data-i18n-alt]", function (node, v) { node.setAttribute("alt", v); });
  document.title = dict.doc_title || document.title;
  el.root.setAttribute("lang", lang);
}
