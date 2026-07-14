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

Serve a interface de **chat** (`app/chat.html`, HTML autossuficiente). Resposta:
`text/html`.

### `POST /analisar`

Recebe uma imagem, roda a análise e devolve o **laudo em JSON**.

- **Corpo**: `multipart/form-data` com o campo **`imagem`** (arquivo).
- **Query opcional**: `adk` (bool, padrão `false`) — usa o **grafo multiagente
  (ADK)** em vez do pipeline direto; se o ADK falhar, cai automaticamente no
  pipeline direto e registra o aviso em `erros`.
- **Resposta**: `application/json` com o [laudo](#formato-do-laudo). Em erro
  interno, retorna `{"erro": "..."}` com status `500`.

```bash
# pipeline direto
curl -F "imagem=@minha_etiqueta.jpg" http://localhost:8000/analisar

# via grafo ADK (requer Gemini)
curl -F "imagem=@minha_etiqueta.jpg" "http://localhost:8000/analisar?adk=true"
```

A imagem é gravada em um arquivo temporário (o pipeline trabalha com caminhos de
arquivo) e removida ao final, independentemente do resultado.

### `POST /analisar-htmx`

Igual ao `POST /analisar`, mas devolve um **fragmento HTML** (o cartão do laudo, no
estilo shadcn) em vez de JSON. É o endpoint usado pela página de chat via **htmx**
(`hx-post="/analisar-htmx"`), para atualizar a conversa sem recarregar a página.

Além da imagem, o corpo (`multipart/form-data`) aceita dois campos de formulário,
enviados pelo chat via `htmx:configRequest`:

- **`imagem`** (arquivo) — a etiqueta a analisar.
- **`idioma`** (`pt-BR` \| `en-US`, padrão `pt-BR`) — idioma dos rótulos do cartão e
  do próprio laudo.
- **`inspetor`** (`llm` \| `kb` \| `auto`, padrão `llm`) — motor de diagnóstico:
  `llm` e `auto` usam o Gemini (com *fallback* por regras); `kb` força as regras da
  base Zebra.

### `GET /static/*`

Arquivos estáticos servidos localmente (ex.: `htmx.min.js`), sem depender de CDN.

:::note
A página de chat (`GET /`) envia a imagem via **htmx** para `POST /analisar-htmx` e
insere na conversa o cartão do laudo retornado. O `POST /analisar` (JSON) continua
disponível para integrações programáticas.
:::

### `GET /saude`

Verificação de saúde do serviço. Resposta: `{"status": "ok"}`.

## Formato do laudo

O `POST /analisar` devolve o laudo consolidado (dataclass `Laudo`,
`inspetor/laudo.py`). Campos:

| Campo | Tipo | Descrição |
| --- | --- | --- |
| `legivel` | `bool \| null` | O código pôde ser decodificado? `null` se a leitura ficou indisponível. |
| `simbologia` | `str \| null` | Ex.: `"CODE128"`, `"EAN13"`, `"QRCODE"`. |
| `conteudo` | `str \| null` | *Payload* decodificado do código. |
| `texto_ocr` | `str` | Texto humano-legível (Tesseract); `""` se indisponível. |
| `indicadores` | `object` | `{contraste, uniformidade, nitidez}` em `[0,1]`. |
| `defeito` | `object` | `{classe, classe_pt, confianca, probs}` da CNN. |
| `causa_provavel` | `str` | Causa provável do defeito. |
| `correcao_sugerida` | `str` | Correção recomendada. |
| `fundamentacao` | `str` | Trecho/raciocínio que embasa o diagnóstico. |
| `fonte` | `str` | Referência (ex.: `"Zebra Technologies (2024)"`). |
| `via_diagnostico` | `str` | `"gemini"` ou `"regras"`. |
| `confianca_geral` | `float` | Confiança global (0–1). |
| `erros` | `array` | Avisos/degradações (libs ausentes, ADK indisponível etc.). |

### Exemplo

```json
{
  "legivel": true,
  "simbologia": "CODE128",
  "conteudo": "CB123",
  "texto_ocr": "CB123",
  "indicadores": { "contraste": 0.82, "uniformidade": 0.74, "nitidez": 0.6 },
  "defeito": {
    "classe": "ribbon_enrugado",
    "classe_pt": "Ribbon enrugado",
    "confianca": 0.91,
    "probs": {}
  },
  "causa_provavel": "Tensão/alinhamento do ribbon",
  "correcao_sugerida": "Ajustar a tensão do ribbon; verificar o percurso",
  "fundamentacao": "...",
  "fonte": "Zebra Technologies (2024)",
  "via_diagnostico": "regras",
  "confianca_geral": 0.91,
  "erros": []
}
```
