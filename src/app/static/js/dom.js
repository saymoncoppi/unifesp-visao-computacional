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
  // Camera modal
  cameraModal: document.getElementById("camera-modal"),
  cameraVideo: document.getElementById("camera-video"),
  cameraError: document.getElementById("camera-error"),
  cameraCapture: document.getElementById("camera-capture"),
  cameraCancel: document.getElementById("camera-cancel")
};
