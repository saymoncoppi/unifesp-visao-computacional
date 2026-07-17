import { el } from "./dom.js";
import { setImageFile, resetComposer } from "./composer.js";
import { openScan, closeScan } from "./scan.js";

// ===================================================== Attach ("+") menu + capture
// WhatsApp-like attach button: opens a small popover with three options.
//   - "Fotos"  -> opens the image explorer (the hidden #image input)
//   - "Câmera" -> opens the device's native camera app to take a photo (the
//                 #camera-input with capture="environment"); with the .env opt-in
//                 CAMERA_USE_ZXING=true it routes through the ZXing scanner instead
//   - "Scan"   -> always the live ZXing barcode scanner (scan.js)
// A taken/selected photo is shown in a preview modal with Cancel / Analyze.

let previewUrl = null;     // object URL currently shown in the preview modal

// ------------------------------------------------------------- attach menu
function openAttachMenu() {
  el.attachMenu.hidden = false;
  el.attachButton.setAttribute("aria-expanded", "true");
}
function closeAttachMenu() {
  el.attachMenu.hidden = true;
  el.attachButton.setAttribute("aria-expanded", "false");
}

// ------------------------------------------------------------- preview modal
function revokePreview() {
  if (previewUrl) { URL.revokeObjectURL(previewUrl); previewUrl = null; }
}

// Loads a File into the submit input and shows it in the preview modal.
function openPreview(file) {
  if (!file) return;
  setImageFile(file);
  revokePreview();
  previewUrl = URL.createObjectURL(file);
  el.previewImg.src = previewUrl;
  el.previewModal.hidden = false;
}
function closePreview() {
  el.previewModal.hidden = true;
  el.previewImg.removeAttribute("src");
  revokePreview();
}

// Opens the device's native camera app to take a photo. The #camera-input has
// capture="environment", so mobile browsers launch the (back) camera directly;
// the resulting photo lands in the input's change handler -> preview.
function openCamera() {
  el.cameraInput.click();
}

// ------------------------------------------------------------- wiring
export function initAttach() {
  // Attach menu open/close
  el.attachButton.addEventListener("click", function (e) {
    e.stopPropagation();
    if (el.attachMenu.hidden) openAttachMenu(); else closeAttachMenu();
  });
  el.attachMenu.addEventListener("click", function (evt) {
    var item = evt.target.closest("[data-attach]");
    if (!item) return;
    var kind = item.getAttribute("data-attach");
    closeAttachMenu();
    if (kind === "photos") el.input.click();
    else if (kind === "camera") {
      // Default: native capture (openCamera). Only the explicit .env opt-in
      // CAMERA_USE_ZXING=true routes the "Camera" option through the ZXing
      // scanner instead. "Scan" (below) always uses ZXing regardless.
      var useZxing = !!(window.INSPECTOR_CONFIG && window.INSPECTOR_CONFIG.cameraUseZxing === true);
      if (useZxing) openScan(); else openCamera();
    }
    else if (kind === "scan") openScan();   // always the ZXing scanner
  });
  document.addEventListener("click", function (e) {
    if (!el.attachMenu.hidden && !el.attach.contains(e.target)) closeAttachMenu();
  });
  document.addEventListener("keydown", function (e) {
    if (e.key !== "Escape") return;
    if (!el.attachMenu.hidden) { closeAttachMenu(); el.attachButton.focus(); }
    else if (!el.previewModal.hidden) { closePreview(); resetComposer(); }
    else if (!el.scanModal.hidden) { closeScan(); }
  });

  // File selected in the explorer -> preview
  el.input.addEventListener("change", function () {
    var f = el.input.files && el.input.files[0];
    if (f) openPreview(f);
  });
  // Native capture fallback (mobile camera) -> preview
  el.cameraInput.addEventListener("change", function () {
    var f = el.cameraInput.files && el.cameraInput.files[0];
    if (f) openPreview(f);
  });

  // Preview modal actions
  el.previewCancel.addEventListener("click", function () { closePreview(); resetComposer(); });
  el.previewAnalyze.addEventListener("click", function () {
    closePreview();               // keep #image; do NOT reset before submitting
    el.form.requestSubmit();      // htmx intercepts the form submit
  });
  el.previewModal.addEventListener("click", function (e) {
    if (e.target === el.previewModal) { closePreview(); resetComposer(); }  // backdrop = cancel
  });
}
