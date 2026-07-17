import { el } from "./dom.js";
import { scrollBottom, stampTime } from "./composer.js";

// ===================================================== Scan (ZXing barcode)
// Backs the attach ("+") menu's "Scan" option (and "Camera" when the .env opt-in
// CAMERA_USE_ZXING=true is set). Opens a modal with a live camera feed and
// continuously decodes barcodes of ANY symbology via ZXing, loaded from the CDN
// (unpkg) as the global `ZXing`.
//
// It mirrors the proven reference flow: list the cameras, start
// decodeFromVideoDevice() on the chosen one (this handles the video element's
// play() for us — the key to actually getting frames to decode), and prefer the
// back camera plus continuous autofocus / zoom so small codes stay sharp. Each
// newly decoded value is dropped into the chat as a user bubble.

let reader = null;             // active ZXing BrowserMultiFormatReader
let track = null;              // live video track (for zoom / autofocus)
let selectedDeviceId = null;   // camera currently decoding
let lastText = "";             // last decoded value, to avoid repeats in the chat

// Removes only non-printable control characters (e.g. GS1/FNC1 separators seen
// in DataMatrix payloads); keeps normal punctuation so URL/QR content survives.
function clean(text) {
  return String(text || "").replace(/[\x00-\x1f\x7f]/g, "").trim();
}

function showError() {
  el.scanError.hidden = false;
  el.scanHint.hidden = true;
}

// Appends the decoded code to the chat as a user (right-aligned) bubble.
function appendCode(text) {
  var row = document.createElement("div");
  row.className = "msg msg-user";
  var bubble = document.createElement("div");
  bubble.className = "bubble bubble-user bubble-code";
  bubble.textContent = text;
  row.appendChild(bubble);
  el.chat.appendChild(row);
  stampTime(row);
  scrollBottom();
}

function onResult(result, err) {
  if (!result) return;   // err is usually NotFoundException between frames
  var text = clean(result.getText ? result.getText() : result.text);
  if (!text || text === lastText) return;
  lastText = text;
  el.scanResult.value = text;
  el.scanResultRow.hidden = false;
  el.scanCopy.hidden = false;
  appendCode(text);
}

// Reads the live track's capabilities to enable continuous autofocus (sharper
// small codes) and expose a zoom slider bound to the real min/max range.
function setupControls() {
  var stream = el.scanVideo.srcObject;
  track = stream && stream.getVideoTracks ? stream.getVideoTracks()[0] : null;
  el.scanZoomRow.hidden = true;
  if (!track || !track.getCapabilities) return;

  var caps = {};
  try { caps = track.getCapabilities(); } catch (e) { return; }

  // Upgrade the running feed: high resolution (sharper small codes) + continuous
  // autofocus, applied to the live track without restarting the decode.
  var advanced = [];
  if (caps.focusMode && caps.focusMode.indexOf("continuous") >= 0) {
    advanced.push({ focusMode: "continuous" });
  }
  track.applyConstraints({
    width: { ideal: 1920 }, height: { ideal: 1080 }, advanced: advanced
  }).catch(function () {});

  if (caps.zoom) {
    var settings = track.getSettings ? track.getSettings() : {};
    el.scanZoom.min = caps.zoom.min;
    el.scanZoom.max = caps.zoom.max;
    el.scanZoom.step = caps.zoom.step || 0.1;
    el.scanZoom.value = settings.zoom != null ? settings.zoom : caps.zoom.min;
    el.scanZoomRow.hidden = false;
  }
}

// Starts (or restarts) the continuous decode on a given camera. A null deviceId
// lets ZXing pick the default device (and prompts for permission).
async function start(deviceId) {
  if (!reader) return;
  try { reader.reset(); } catch (e) { /* stops any previous decode */ }
  await reader.decodeFromVideoDevice(deviceId || null, el.scanVideo, onResult);
  var stream = el.scanVideo.srcObject;
  var settings = stream && stream.getVideoTracks ? stream.getVideoTracks()[0].getSettings() : null;
  selectedDeviceId = (settings && settings.deviceId) || deviceId || null;
  setupControls();
}

// Fills the camera dropdown (labels are exposed only after permission) and, if
// the default wasn't already a back camera, switches to one.
async function populateAndPreferBack() {
  var devices = await reader.listVideoInputDevices();
  el.scanSource.innerHTML = "";
  devices.forEach(function (d, i) {
    var opt = document.createElement("option");
    opt.value = d.deviceId;
    opt.text = d.label || ("Câmera " + (i + 1));
    el.scanSource.appendChild(opt);
  });
  el.scanSourceRow.hidden = devices.length < 2;

  var back = devices.filter(function (d) {
    return /back|rear|traseira|tras|environment/i.test(d.label || "");
  })[0];
  var pick = (back && back.deviceId) || selectedDeviceId ||
             (devices[0] && devices[0].deviceId) || null;

  el.scanSource.value = pick || "";
  if (pick && pick !== selectedDeviceId) await start(pick);
}

export async function openScan() {
  el.scanError.hidden = true;
  el.scanHint.hidden = false;
  el.scanSourceRow.hidden = true;
  el.scanZoomRow.hidden = true;
  el.scanResultRow.hidden = true;
  el.scanCopy.hidden = true;
  el.scanResult.value = "";
  lastText = "";

  if (typeof ZXing === "undefined") { showError(); el.scanModal.hidden = false; return; }

  // Hints:
  //  - TRY_HARDER: spend more effort per frame — decisive for small / low-
  //    contrast codes held up to a phone camera.
  //  - POSSIBLE_FORMATS: an explicit, broad symbology list. Leaving it fully
  //    unrestricted routes through a reader that logs a noisy (harmless)
  //    "non-ReaderException"; naming the formats keeps coverage while avoiding
  //    that path. Add/remove formats here as needed.
  var F = ZXing.BarcodeFormat;
  var hints = new Map();
  hints.set(ZXing.DecodeHintType.TRY_HARDER, true);
  hints.set(ZXing.DecodeHintType.POSSIBLE_FORMATS, [
    F.DATA_MATRIX, F.QR_CODE, F.AZTEC, F.PDF_417,
    F.CODE_128, F.CODE_39, F.CODE_93, F.CODABAR,
    F.EAN_13, F.EAN_8, F.UPC_A, F.UPC_E, F.ITF
  ]);
  reader = new ZXing.BrowserMultiFormatReader(hints);

  el.scanModal.hidden = false;
  try {
    await start(null);              // default camera + permission prompt
    await populateAndPreferBack();  // list cameras, switch to the back one
  } catch (e) {
    showError();
  }
}

export function closeScan() {
  if (reader) { try { reader.reset(); } catch (e) { /* stops stream & tracks */ } reader = null; }
  track = null;
  el.scanModal.hidden = true;
}

export function initScan() {
  el.scanClose.addEventListener("click", closeScan);
  el.scanModal.addEventListener("click", function (e) {
    if (e.target === el.scanModal) closeScan();   // backdrop = close
  });
  el.scanCopy.addEventListener("click", function () {
    var value = el.scanResult.value;
    if (value && navigator.clipboard) navigator.clipboard.writeText(value);
  });

  el.scanSource.addEventListener("change", function () {
    lastText = "";
    start(el.scanSource.value).catch(showError);
  });

  el.scanZoom.addEventListener("input", function () {
    if (track && track.applyConstraints) {
      track.applyConstraints({ advanced: [{ zoom: Number(el.scanZoom.value) }] }).catch(function () {});
    }
  });
}
