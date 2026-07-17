---
title: Uso
description: Como usar o inspetor de etiquetas — CLI, chat web (FastAPI/uvicorn) e o chat nativo do ADK.
---

Há três formas de usar o inspetor: pela **linha de comando (CLI)**, pelo **chat
web** (FastAPI) e pelo **chat nativo do ADK**. Todas partem da pasta `src/`.

:::tip
Prefixe os comandos `python -m ...` com `uv run` para garantir o ambiente do uv
(ex.: `uv run python -m app.cli foto.jpg`).
:::

## 1. CLI

Analisa a imagem de uma etiqueta e imprime um resumo do laudo:

```bash
python -m app.cli foto.jpg
```

Exemplos com uma imagem do dataset e as opções disponíveis:

```bash
python -m app.cli config/datasets/dataset_sintetico/images/test/wrinkled_ribbon/ean13_075.png
python -m app.cli minha_etiqueta.jpg --json      # laudo completo em JSON (indentado)
python -m app.cli minha_etiqueta.jpg --adk       # via grafo ADK (requer Gemini)
```

Interface: `python -m app.cli CAMINHO [--adk] [--json]`.

- Sem `--adk`: roda o **pipeline direto** (`config.inspector.tools.analyze_image`).
- Com `--adk`: tenta o **grafo multiagente** (`config.inspector.agents.analyze_via_adk`) e,
  se ele falhar por qualquer motivo (lib ausente, erro de execução, sem chave),
  **cai de volta** para o pipeline direto — a análise nunca deixa de acontecer.
- Com `--json`: imprime o laudo completo em JSON além do resumo.

## 2. Chat web (FastAPI + uvicorn)

Sobe o servidor HTTP que serve a interface de chat e o endpoint de análise:

```bash
uvicorn app.api:app --reload
```

Depois abra **http://localhost:8000** e envie a foto da etiqueta — o laudo aparece
como mensagens de chat (legível/simbologia, defeito + confiança, causa, correção).

![Chat do Inspetor de Etiquetas exibindo um laudo completo](img/chat_inspetor.png)

A página (`app/chat.html`) é um frontend modular servido de `app/static/`
(CSS + módulos JS *vanilla* + htmx) e envia a imagem via **htmx** para
`POST /analyze-htmx`, inserindo o cartão do laudo na conversa. Detalhes dos endpoints
em [API HTTP](/api/).

### Anexar imagem (+): Fotos, Câmera e Scan

O botão **`+`** do compositor abre três opções:

- **Fotos** — escolher um arquivo/imagem da galeria.
- **Câmera** — captura nativa do dispositivo (`capture="environment"`).
- **Scan** — **leitor de código de barras ao vivo** (via **ZXing**), com seletor de
  câmera e controle de *zoom*; a câmera e o zoom escolhidos ficam salvos no
  `localStorage`. A biblioteca ZXing é carregada por CDN.

### Menu de configurações (⋮)

O botão de três pontinhos (⋮) no topo abre um menu com quatro seções; as
preferências ficam salvas no `localStorage` do navegador:

- **Idioma** — *Português Brasileiro* ou *English*. A troca é instantânea (i18n real
  PT/EN, via atributos `data-i18n`) e o idioma escolhido acompanha cada análise, de
  modo que **o laudo também sai no idioma selecionado**.
- **Tema** — *Claro*, *Escuro* ou *Auto* (Auto segue o tema do sistema operacional).
- **Inspetor** (motor de diagnóstico) — **LLM** (mostra o modelo ativo, ex.
  `gemini-flash-latest`), **KB Zebra Technologies** (regras) ou **Auto**
  (multiagente/ADK com árbitro visual). A opção **Auto só aparece quando há um LLM
  configurado** no `.env`.
- **Ações** — **Exportar em PDF** (via `window.print` + `@media print`) e **Limpar**
  (em vermelho; apaga a conversa).

![Menu de configurações do chat aberto](img/chat_menu.png)

As preferências (idioma, tema, motor) ficam salvas no `localStorage`; um rodapé
mostra a **cota do Gemini** restante no minuto (polling em `GET /quota`). O idioma e o
motor escolhidos são enviados a cada envio (via `htmx:configRequest`), como os campos
`language` e `inspector` do [`POST /analyze-htmx`](/api/).

### Imagem sem código de barras (curto-circuito)

Se a imagem enviada **não contém um código de barras**, o inspetor faz um
**curto-circuito**: a presença do código é verificada **antes** da inspeção pesada e,
quando não há código, o laudo traz apenas o aviso *"Nenhum código de barras detectado
na imagem."* — **sem rodar a CNN nem chamar o LLM**. Isso economiza processamento e
chamadas de API e evita diagnósticos espúrios.

## 3. Chat nativo do ADK (opcional)

Interface de chat do próprio ADK sobre o grafo de agentes (`config/inspector/agents.py`):

```bash
adk web
```

Requer o **Gemini** configurado (chave de API) e o pacote `google-adk` instalado.
Veja [Configurar o Gemini](/configurar-gemini/).

## Fluxo típico

1. (Opcional) Gerar/atualizar o [dataset sintético](/datasets/).
2. [Treinar a CNN](/treinamento/) para produzir `config/models/classificador_defeitos.pt`.
3. Analisar imagens pela **CLI** ou pelo **chat web**.
