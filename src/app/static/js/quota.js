// ===================================================== Free-tier quota status
// Shows a muted, right-aligned "LLM · used/limit req/min" counter inline in the
// composer whenever an LLM is configured, and blocks a new analysis while the
// minute quota is exhausted (so a burst of clicks does not fail with a 429
// mid-request). The reset countdown is appended only once the limit is reached.
// The server (/quota) is polled only on load and after each analysis; the
// `reset_in` countdown ticks locally.
import { el } from "./dom.js";
import { state } from "./state.js";
import { t } from "./i18n.js";
import { scrollBottom } from "./composer.js";

// Local mirror of the last server snapshot. `reset_in` is counted down from
// `syncedAt` on the client so we do not hit the server every second.
var q = { enabled: false, seen_429: false, blocked: false, reset_in: 0, used: 0, limit: 0, model: "", syncedAt: 0 };

function nowSec() { return Date.now() / 1000; }

function fmt(key, vars) {
  var s = t(key);
  for (var k in vars) s = s.replace("{" + k + "}", vars[k]);
  return s;
}

// Seconds left until the quota state improves, decremented since the last sync.
function liveReset() {
  return Math.max(0, Math.ceil(q.reset_in - (nowSec() - q.syncedAt)));
}

// True while a new analysis should be withheld.
export function isBlocked() {
  return q.enabled && q.blocked && liveReset() > 0;
}

function render() {
  if (!el.quotaInline) return;
  // Only relevant when the chosen inspector actually calls the LLM (llm/auto);
  // the KB (rules-only) inspector makes no Gemini calls, so hide the counter.
  var usesLlm = state.inspector === "llm" || state.inspector === "auto";
  if (!q.enabled || !usesLlm) { el.quotaInline.hidden = true; return; }
  // The reset countdown is appended ONLY once the minute limit is reached.
  el.quotaInline.hidden = false;
  el.quotaInline.setAttribute("title", fmt("quota_title", { limit: q.limit }));

  var left = liveReset();
  var blocked = q.blocked && left > 0;
  var text = "LLM · " + fmt("quota_usage", { used: q.used, limit: q.limit });
  if (blocked) {
    text += " · " + t("quota_blocked") + " " + fmt("quota_reset", { s: left });
  }
  el.quotaInline.textContent = text;
}

async function sync() {
  try {
    var r = await fetch("/quota", { cache: "no-store" });
    var d = await r.json();
    if (!d || !d.enabled) { q.enabled = false; render(); return; }
    q.enabled = true;
    q.seen_429 = !!d.seen_429;
    q.blocked = !!d.blocked;
    q.reset_in = d.reset_in || 0;
    q.used = d.used || 0;
    q.limit = d.limit || 0;
    q.model = d.model || "";
    q.syncedAt = nowSec();
    render();
  } catch (e) {
    // Network hiccup: keep the last known state rather than blanking the status.
  }
}

// Bot bubble explaining why a blocked analysis did not run.
function appendBlockedBubble() {
  if (!el.chat) return;
  var row = document.createElement("div");
  row.className = "msg msg-bot";
  var avatar = document.createElement("div");
  avatar.className = "avatar";
  avatar.setAttribute("aria-hidden", "true");
  avatar.textContent = "IE";
  var bubble = document.createElement("div");
  bubble.className = "bubble is-error";
  bubble.textContent = "⚠️ " + t("quota_blocked") + " " + fmt("quota_reset", { s: liveReset() });
  row.appendChild(avatar);
  row.appendChild(bubble);
  el.chat.appendChild(row);
  scrollBottom();
}

export function initQuota() {
  var cfg = window.INSPECTOR_CONFIG || {};
  if (!cfg.hasGemini) { if (el.quotaInline) el.quotaInline.hidden = true; return; }

  sync();

  // Re-render immediately when the inspector changes (KB hides it, llm/auto shows it).
  document.addEventListener("inspector-change", render);

  // Re-sync after every analysis (each fires 1-2 Gemini calls server-side).
  document.body.addEventListener("htmx:afterRequest", function (evt) {
    if (evt.target === el.form) sync();
  });

  // Withhold a new analysis while the minute quota is exhausted. Runs after
  // composer.js's beforeRequest (which already added the user's image bubble),
  // so the blocked bubble reads as the reply to that attempt.
  document.body.addEventListener("htmx:beforeRequest", function (evt) {
    if (evt.target === el.form && isBlocked()) {
      evt.preventDefault();          // cancels the htmx request.
      appendBlockedBubble();
      render();
    }
  });

  // Local 1 s tick: count the reset down; re-sync once it reaches zero so the
  // freed-up slot count comes from the server rather than a client guess.
  var wasCounting = false;
  setInterval(function () {
    if (!q.enabled) return;
    var left = liveReset();
    render();
    if (wasCounting && left === 0) sync();
    wasCounting = left > 0;
  }, 1000);
}
