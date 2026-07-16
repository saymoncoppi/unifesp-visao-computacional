---
title: Configurar o Gemini
description: Como configurar a GOOGLE_API_KEY para o diagnóstico via Gemini/ADK e como rodar sem chave (fallback por regras).
---

O passo de **diagnóstico** (causa provável + correção) pode usar o **Gemini**, mas
é totalmente **opcional**: sem chave de API, o sistema usa o *fallback* por regras
sobre a base de conhecimento Zebra.

:::note
Um guia detalhado fica em **`src/CONFIGURAR_GEMINI.md`**. Esta página é um resumo.
:::

## Com o Gemini (chave de API)

1. **Obtenha uma chave** no Google AI Studio (`GOOGLE_API_KEY`).
2. **Configure a chave** — copie o exemplo e preencha:

   ```bash
   cp .env.example .env
   ```

   No `.env`:

   ```dotenv
   GOOGLE_API_KEY=sua_chave_aqui

   # Opcionais:
   # GEMINI_MODEL=gemini-flash-latest
   # DATASET_DIR=/caminho/para/dataset_sintetico
   # MODEL_PATH=/caminho/para/classificador_defeitos.pt
   ```

   Alternativamente, exporte a variável no ambiente:

   ```bash
   export GOOGLE_API_KEY="sua_chave_aqui"
   ```

3. **Modelo**: o padrão é `gemini-flash-latest` (constante `GEMINI_MODEL` em
   `config/inspector/settings.py`), sobreponível pela variável de ambiente `GEMINI_MODEL`.

Com a chave presente, o diagnóstico (`config/inspector/diagnosis.py`) monta um *prompt*
com o contexto da base Zebra (`kb.context_for_llm`) e pede ao Gemini uma resposta
**estritamente em JSON** (`probable_cause`, `corrective_action`, `reasoning`).
O campo `diagnosis_method` do laudo fica `"gemini"`.

:::note
Na interface de [chat web](/uso/), a seção **Inspetor** do menu (⋮) mostra o
**modelo ativo** (ex.: `gemini-flash-latest`) ao lado da opção **LLM**. A opção
**Auto** (LLM com *fallback* para a KB Zebra) só aparece quando há um LLM
configurado no `.env`; sem chave, o menu oferece apenas a **KB Zebra Technologies**
(regras).
:::

:::tip
A função `settings.has_gemini()` considera configurada a chave se **`GOOGLE_API_KEY`
ou `GEMINI_API_KEY`** estiver definida no ambiente.
:::

## Sem chave (fallback por regras)

Se **não houver** chave configurada — ou se a chamada ao Gemini falhar por qualquer
motivo (lib ausente, rede, cota, JSON inválido) — o diagnóstico recorre
**graciosamente** às **regras** da base de conhecimento Zebra
(`config/inspector/kb.py` + `config/data/kb_zebra.json`): para a classe do defeito, retorna a
causa provável e a ação corretiva mapeadas na documentação. Nesse caso o campo
`diagnosis_method` fica `"rules"`.

Ou seja: **o sistema funciona sem chave** — apenas o texto do diagnóstico deixa de
ser gerado pelo LLM e passa a vir das regras.

## ADK (grafo multiagente)

O modo `--adk` (CLI) / `adk=true` (API) e o `adk web` usam o **Agent Development
Kit** com o Gemini como modelo dos agentes — portanto **requerem** a chave
configurada e o pacote `google-adk` instalado. Sem isso, a CLI e a API caem
automaticamente no **pipeline direto** (que, por sua vez, usa Gemini se houver
chave ou as regras caso contrário).
