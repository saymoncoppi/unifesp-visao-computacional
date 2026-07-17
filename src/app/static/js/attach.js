import { el } from "./dom.js";
import { setImageFile, resetComposer } from "./composer.js";

// ===================================================== Attach ("+") menu + capture
// WhatsApp-like attach button: opens a small popover with two options.
//   - "Fotos"  -> opens the image explorer (the hidden #image input)
//   - "Câmera" -> opens the live camera (getUserMedia); falls back to the
//                 native capture input when getUserMedia is unavailable/denied.
// The chosen/captured image is shown in a preview modal with Cancel / Analyze.

let cameraStream = null;   // active MediaStream while the camera modal is open
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

// ------------------------------------------------------------- camera modal
function stopCamera() {
  if (cameraStream) {
    cameraStream.getTracks().forEach(function (track) { track.stop(); });
    cameraStream = null;
  }
  el.cameraVideo.srcObject = null;
}
function closeCamera() {
  stopCamera();
  el.cameraModal.hidden = true;
}

async function openCamera() {
  el.cameraError.hidden = true;
  // No live-camera API (older browser / insecure context): use the native
  // capture input, which opens the camera app on mobile.
  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
    el.cameraInput.click();
    return;
  }
  try {
    cameraStream = await navigator.mediaDevices.getUserMedia({
      video: { facingMode: "environment" }
    });
    el.cameraVideo.srcObject = cameraStream;
    el.cameraModal.hidden = false;
  } catch (e) {
    // Permission denied or no device: fall back to the native capture input.
    el.cameraInput.click();
  }
}

function capturePhoto() {
  var v = el.cameraVideo;
  var w = v.videoWidth, h = v.videoHeight;
  if (!w || !h) return;   // stream not ready yet
  var canvas = document.createElement("canvas");
  canvas.width = w;
  canvas.height = h;
  canvas.getContext("2d").drawImage(v, 0, 0, w, h);
  canvas.toBlob(function (blob) {
    if (!blob) return;
    var file = new File([blob], "camera-" + Date.now() + ".png", { type: "image/png" });
    closeCamera();
    openPreview(file);
  }, "image/png");
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
    else if (kind === "camera") openCamera();
  });
  document.addEventListener("click", function (e) {
    if (!el.attachMenu.hidden && !el.attach.contains(e.target)) closeAttachMenu();
  });
  document.addEventListener("keydown", function (e) {
    if (e.key !== "Escape") return;
    if (!el.attachMenu.hidden) { closeAttachMenu(); el.attachButton.focus(); }
    else if (!el.previewModal.hidden) { closePreview(); resetComposer(); }
    else if (!el.cameraModal.hidden) { closeCamera(); }
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

  // Camera modal actions
  el.cameraCapture.addEventListener("click", capturePhoto);
  el.cameraCancel.addEventListener("click", closeCamera);
  el.cameraModal.addEventListener("click", function (e) {
    if (e.target === el.cameraModal) closeCamera();  // backdrop = cancel
  });
}
