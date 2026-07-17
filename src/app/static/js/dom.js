// ===================================================== Cached DOM references
export const el = {
  root: document.documentElement,
  form: document.getElementById("form"),
  input: document.getElementById("image"),
  cameraInput: document.getElementById("camera-input"),
  submit: document.getElementById("submit"),
  chat: document.getElementById("chat"),
  main: document.getElementById("main"),
  // Header (settings) menu
  menu: document.getElementById("menu"),
  menuButton: document.getElementById("menu-button"),
  menuPanel: document.getElementById("menu-panel"),
  modelLabel: document.getElementById("llm-model-label"),
  // Free-tier quota status (inline, in the composer)
  quotaInline: document.getElementById("quota-inline"),
  // Attach ("+") menu
  attach: document.getElementById("attach"),
  attachButton: document.getElementById("attach-button"),
  attachMenu: document.getElementById("attach-menu"),
  // Preview modal
  previewModal: document.getElementById("preview-modal"),
  previewImg: document.getElementById("preview-img"),
  previewCancel: document.getElementById("preview-cancel"),
  previewAnalyze: document.getElementById("preview-analyze"),
  // Scan modal (ZXing barcode)
  scanModal: document.getElementById("scan-modal"),
  scanVideo: document.getElementById("scan-video"),
  scanHint: document.getElementById("scan-hint"),
  scanSourceRow: document.getElementById("scan-source-row"),
  scanSource: document.getElementById("scan-source"),
  scanZoomRow: document.getElementById("scan-zoom-row"),
  scanZoom: document.getElementById("scan-zoom"),
  scanResultRow: document.getElementById("scan-result-row"),
  scanResult: document.getElementById("scan-result"),
  scanError: document.getElementById("scan-error"),
  scanCopy: document.getElementById("scan-copy"),
  scanClose: document.getElementById("scan-close"),
  // Lightbox (click a chat image)
  lightboxModal: document.getElementById("lightbox-modal"),
  lightboxImg: document.getElementById("lightbox-img"),
  lightboxClose: document.getElementById("lightbox-close")
};
