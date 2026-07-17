---
title: API HTTP
description: Endpoints da API FastAPI do inspetor de etiquetas e o formato do laudo (tabela de campos).
---

A API é servida por **FastAPI** (`app/api.py`) e sobe com `uvicorn`:

```bash
uvicorn app.api:app --reload
# http://localhost:8000
```

Ela serve a interface de chat e expõe o pipeline de análise. A documentação
interativa (Swagger) fica em **http://localhost:8000/docs**.

## Endpoints

### `GET /`

Serve a interface de **chat** (`app/chat.html`). Resposta: `text/html`. A página
injeta o modelo ativo, se há Gemini configurado e a preferência de scanner.

### `POST /analyze`

Recebe uma imagem, roda a análise e devolve o **laudo em JSON**.

- **Corpo**: `multipart/form-data` com o campo **`image`** (arquivo).
- **Query opcional**: `adk` (bool, padrão `false`) — usa o **caminho multiagente
  (ADK)** em vez do pipeline direto; se o ADK falhar, cai automaticamente no
  pipeline direto e registra o aviso em `errors`.
- **Resposta**: `application/json` com o [laudo](#formato-do-laudo). Em erro
  interno, retorna `{"error": "..."}` com status `500`.

```bash
# pipeline direto
curl -F "image=@minha_etiqueta.jpg" http://localhost:8000/analyze

# via grafo ADK (usa Gemini quando há chave)
curl -F "image=@minha_etiqueta.jpg" "http://localhost:8000/analyze?adk=true"
```

A imagem é gravada em um arquivo temporário (o pipeline trabalha com caminhos de
arquivo) e removida ao final, independentemente do resultado.

### `POST /analyze-htmx`

Igual ao `POST /analyze`, mas devolve um **fragmento HTML** (o cartão do laudo, no
estilo shadcn) em vez de JSON. É o endpoint usado pela página de chat via **htmx**
(`hx-post="/analyze-htmx"`), para atualizar a conversa sem recarregar a página.

O corpo (`multipart/form-data`) aceita três campos de formulário, enviados pelo chat
via `htmx:configRequest`:

- **`image`** (arquivo) — a etiqueta a analisar.
- **`language`** (`pt-BR` \| `en-US`, padrão `pt-BR`) — idioma dos rótulos do cartão e
  do próprio laudo.
- **`inspector`** (`llm` \| `kb` \| `auto`, padrão `llm`) — motor de diagnóstico:
  `llm` usa o Gemini (com *fallback* por regras); `kb` força as regras da base Zebra;
  `auto` usa o caminho multiagente ADK (árbitro visual) quando há Gemini configurado.

### `GET /quota`

Estado da **cota do Gemini** (free-tier = 5 req/min), a partir de
`config/inspector/ratelimit.py`. Retorna `enabled`, `model`, `limit`, `used`,
`remaining`, `reset_in`, `blocked` e `seen_429` — ou `{"enabled": false}` quando não
há chave configurada. É o que alimenta o contador de cota no rodapé do chat.

### `GET /static/*`

Arquivos estáticos servidos de `app/static/` — `css/style.css`, `img/` e os módulos
JS do chat (`main.js`, `i18n.js`, `translations.js`, `menu.js`, `actions.js`,
`quota.js`, `preferences.js`, `composer.js`, `attach.js`, `scan.js`, `lightbox.js`
etc.). A biblioteca de leitura de código ao vivo (**ZXing**) é carregada via CDN.

:::note
A página de chat (`GET /`) envia a imagem via **htmx** para `POST /analyze-htmx` e
insere na conversa o cartão do laudo retornado. O `POST /analyze` (JSON) continua
disponível para integrações programáticas.
:::

### `GET /health`

Verificação de saúde do serviço. Resposta: `{"status": "ok"}`.

## Formato do laudo

O `POST /analyze` devolve o laudo consolidado (dataclass `Report`,
`config/inspector/report.py`). Campos:

| Campo | Tipo | Descrição |
| --- | --- | --- |
| `readable` | `bool \| null` | O código pôde ser decodificado? `null` se a leitura ficou indisponível. |
| `code_detected` | `bool \| null` | Há uma região de código na imagem (mesmo que ilegível)? `null` se a checagem não foi feita. |
| `symbology` | `str \| null` | Ex.: `"CODE128"`, `"EAN13"`, `"QRCODE"`. |
| `content` | `str \| null` | *Payload* decodificado do código. |
| `indicators` | `object` | `{contrast, uniformity, sharpness}` em `[0,1]`. |
| `defect` | `object` | `{class, class_label, confidence, probs}` da CNN. |
| `probable_cause` | `str` | Causa provável do defeito. |
| `corrective_action` | `str` | Correção recomendada. |
| `reasoning` | `str` | Trecho/raciocínio que embasa o diagnóstico. |
| `source` | `str` | Referência (ex.: `"Zebra Technologies (2024)"`). |
| `diagnosis_method` | `str` | `"gemini"` ou `"rules"`. |
| `overall_confidence` | `float` | Confiança global (0–1). |
| `errors` | `array` | Avisos/degradações (libs ausentes, ADK indisponível etc.). |

### Exemplo

```json
{
  "readable": true,
  "code_detected": true,
  "symbology": "CODE128",
  "content": "CB123",
  "indicators": { "contrast": 0.82, "uniformity": 0.74, "sharpness": 0.6 },
  "defect": {
    "class": "wrinkled_ribbon",
    "class_label": "Ribbon enrugado",
    "confidence": 0.91,
    "probs": {}
  },
  "probable_cause": "Tensão/alinhamento do ribbon",
  "corrective_action": "Ajustar a tensão do ribbon; verificar o percurso",
  "reasoning": "...",
  "source": "Zebra Technologies (2024)",
  "diagnosis_method": "rules",
  "overall_confidence": 0.91,
  "errors": []
}
```
