// ===================================================== Translations (i18n)
export const I18N = {
  "pt-BR": {
    doc_title: "Inspetor de Etiquetas",
    app_title: "Inspetor de Etiquetas",
    app_subtitle: "Analise a impressão de etiquetas de código de barras.",
    menu_settings: "Configurações",
    menu_language: "Selecionar idioma",
    menu_theme: "Tema",
    menu_inspector: "Inspetor",
    inspector_auto_title: "Prefere o LLM; usa a KB Zebra como fallback.",
    menu_actions: "Ações",
    action_export_pdf: "Exportar em PDF",
    action_clear: "Limpar",
    theme_light: "Claro",
    theme_dark: "Escuro",
    theme_auto: "Auto",
    attach_aria: "Anexar",
    attach_photos: "Fotos",
    attach_camera: "Câmera",
    preview_title: "Pré-visualização",
    cancel: "Cancelar",
    camera_title: "Tirar foto",
    camera_capture: "Capturar",
    camera_error: "Não foi possível acessar a câmera.",
    analyzing: "analisando…",
    analyze: "Analisar",
    preview_alt: "Pré-visualização",
    sent_image_alt: "Etiqueta enviada",
    quota_usage: "{used}/{limit} req/min",
    quota_reset: "libera em {s}s",
    quota_blocked: "cota do minuto esgotada,",
    quota_title: "Chave gratuita do Gemini: {limit} requisições por minuto (janela deslizante).",
    greeting: "Olá! Toque no botão <strong>+</strong> para anexar a imagem de uma " +
      "etiqueta (dos seus arquivos ou pela câmera) e clique em <strong>Analisar</strong>. " +
      "Vou decodificar o código, avaliar a qualidade da impressão e sugerir a causa " +
      "e a correção de eventuais defeitos."
  },
  "en-US": {
    doc_title: "Label Inspector",
    app_title: "Label Inspector",
    app_subtitle: "Analyze the print quality of barcode labels.",
    menu_settings: "Settings",
    menu_language: "Select language",
    menu_theme: "Theme",
    menu_inspector: "Inspector",
    inspector_auto_title: "Prefers the LLM; falls back to the Zebra KB.",
    menu_actions: "Actions",
    action_export_pdf: "Export to PDF",
    action_clear: "Clear",
    theme_light: "Light",
    theme_dark: "Dark",
    theme_auto: "Auto",
    attach_aria: "Attach",
    attach_photos: "Photos",
    attach_camera: "Camera",
    preview_title: "Preview",
    cancel: "Cancel",
    camera_title: "Take a photo",
    camera_capture: "Capture",
    camera_error: "Could not access the camera.",
    analyzing: "analyzing…",
    analyze: "Analyze",
    preview_alt: "Preview",
    sent_image_alt: "Sent label",
    quota_usage: "{used}/{limit} req/min",
    quota_reset: "frees in {s}s",
    quota_blocked: "minute quota reached,",
    quota_title: "Free Gemini key: {limit} requests per minute (rolling window).",
    greeting: "Hello! Tap the <strong>+</strong> button to attach a label image " +
      "(from your files or via the camera) and click <strong>Analyze</strong>. " +
      "I'll decode the code, assess the print quality, and suggest the cause and " +
      "correction of any defects."
  }
};

export const LANGUAGES = ["pt-BR", "en-US"];
export const THEMES = ["light", "dark", "auto"];
