// ===================================================== Translations (i18n)
export const I18N = {
  "pt-BR": {
    doc_title: "Inspetor de Etiquetas",
    app_title: "Inspetor de Etiquetas",
    app_subtitle: "Analise a impressão de etiquetas de código de barras.",
    menu_aria: "Configurações",
    menu_idioma: "Selecionar idioma",
    menu_tema: "Tema",
    menu_inspector: "Inspetor",
    inspector_auto_title: "Prefere o LLM; usa a KB Zebra como fallback.",
    menu_acoes: "Ações",
    acao_export_pdf: "Exportar em PDF",
    acao_limpar: "Limpar",
    tema_claro: "Claro",
    tema_escuro: "Escuro",
    tema_auto: "Auto",
    choose_image: "Escolher imagem",
    file_none: "Nenhum arquivo selecionado",
    analyzing: "analisando…",
    analyze: "Analisar",
    preview_alt: "Pré-visualização",
    sent_image_alt: "Etiqueta enviada",
    greeting: "Olá! Selecione a imagem de uma etiqueta de código de barras e " +
      "clique em <strong>Analisar</strong>. Vou decodificar o código, avaliar " +
      "a qualidade da impressão e sugerir a causa e a correção de eventuais defeitos."
  },
  "en-US": {
    doc_title: "Label Inspector",
    app_title: "Label Inspector",
    app_subtitle: "Analyze the print quality of barcode labels.",
    menu_aria: "Settings",
    menu_idioma: "Select language",
    menu_tema: "Theme",
    menu_inspector: "Inspector",
    inspector_auto_title: "Prefers the LLM; falls back to the Zebra KB.",
    menu_acoes: "Actions",
    acao_export_pdf: "Export to PDF",
    acao_limpar: "Clear",
    tema_claro: "Light",
    tema_escuro: "Dark",
    tema_auto: "Auto",
    choose_image: "Choose image",
    file_none: "No file selected",
    analyzing: "analyzing…",
    analyze: "Analyze",
    preview_alt: "Preview",
    sent_image_alt: "Sent label",
    greeting: "Hello! Select an image of a barcode label and click " +
      "<strong>Analyze</strong>. I'll decode the code, assess the print " +
      "quality, and suggest the cause and correction of any defects."
  }
};

export const LANGUAGES = ["pt-BR", "en-US"];
export const THEMES = ["light", "dark", "auto"];
