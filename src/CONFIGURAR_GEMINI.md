# Configurar o LLM (Gemini via ADK) — ou usar alternativas gratuitas

Guia rápido para habilitar o **diagnóstico via LLM (Gemini)** no Inspetor de
Etiquetas — ou continuar usando o sistema **de graça**, sem chave nenhuma.

---

## 1) Preciso mesmo de uma chave?

**Não.** O sistema **já funciona sem chave de API**, com **custo zero**.

Quando não há `GOOGLE_API_KEY` configurada, o diagnóstico usa o **fallback por
regras** sobre a **base de conhecimento Zebra** (`config/inspector/kb.py` +
`config/data/kb_zebra.json`). Ele é determinístico, roda 100% localmente e nunca
"quebra": toda a etapa de causa/correção continua funcionando normalmente.

Nesse modo, o laudo sai com o campo **`diagnosis_method="rules"`**.

A chave do Gemini é **opcional** e serve só para **enriquecer o diagnóstico**:
em vez das regras fixas, o texto de causa provável e correção passa a ser
gerado pelo LLM, e o laudo sai com **`diagnosis_method="gemini"`**.

> Resumo: **sem chave → funciona por regras (grátis)**; **com chave → funciona
> por Gemini**. Em ambos os casos você recebe um laudo completo. E qualquer
> falha do Gemini (lib ausente, rede, cota estourada, JSON inválido) cai
> automaticamente de volta para as regras — a análise nunca deixa de acontecer.

---

## 2) Obter a chave gratuita (Google AI Studio)

O Google AI Studio oferece um **nível gratuito** do Gemini, com **limites de uso**
(por minuto/por dia, que variam conforme o modelo e a política vigente do Google
— **consulte a documentação oficial** para os números atuais, pois eles mudam).

Passo a passo:

1. Acesse **https://aistudio.google.com/app/apikey**
2. **Entre com sua conta Google** (a mesma do Gmail já serve).
3. Clique em **"Create API key"** (Criar chave de API).
4. **Copie** a chave gerada (algo como `AIza...`). Guarde-a em local seguro —
   trate-a como uma senha e **não** a envie para repositórios públicos.

> A criação da chave costuma ser gratuita. O uso dentro do **free tier** também,
> respeitando os limites. Verifique sempre os termos atuais no próprio AI Studio.

---

## 3) Configurar no projeto

Você pode fornecer a chave de duas formas. Ambas são lidas por
`config/inspector/settings.py`, cuja função **`settings.has_gemini()`** detecta
automaticamente se há chave presente (aceita `GOOGLE_API_KEY` **ou**
`GEMINI_API_KEY`).

### Opção A — arquivo `.env` (recomendado)

Dentro de `src/`:

```bash
cp .env.example .env
```

Edite o `.env` e preencha:

```dotenv
GOOGLE_API_KEY=AIza...sua_chave_aqui
```

### Opção B — variável de ambiente

Sem criar arquivo, exporte na sessão do terminal:

```bash
export GOOGLE_API_KEY=AIza...sua_chave_aqui
```

### Escolher o modelo — `GEMINI_MODEL`

O modelo usado é controlado pela variável **`GEMINI_MODEL`**, cujo **padrão é
`gemini-flash-latest`** (variante "flash", rápida e de baixo custo — boa para o
free tier). Só mexa aqui se quiser trocar de modelo:

```dotenv
# .env  (opcional)
GEMINI_MODEL=gemini-flash-latest
```

Detalhe técnico: com a chave presente, `diagnosis.py` faz um import **lazy** de
`google.genai`, cria `genai.Client()` e chama o modelo definido em
`settings.GEMINI_MODEL`. Se faltar a biblioteca ou a chamada falhar, volta para as
regras sem interromper a análise.

---

## 4) Alternativas gratuitas

Para **diagnóstico com LLM** é preciso **algum modelo** — seja o Gemini no free
tier, seja um modelo **local**. Sendo honesto: **não existe LLM sem um modelo
por trás**. Sem nenhum deles, o sistema usa o **fallback por regras** (que já é
totalmente funcional e gratuito). Suas opções:

### (a) Rodar sem chave — fallback por regras (custo zero)

É o padrão. Não configure nada e o diagnóstico virá da base de conhecimento
Zebra, com `diagnosis_method="rules"`. Ideal para reproduzir o baseline, rodar
em máquina offline ou evitar qualquer dependência de nuvem.

### (b) Modelo local/gratuito com Ollama + LiteLLM no ADK

O **Agent Development Kit (ADK)** suporta modelos externos por meio do
**LiteLLM**, o que permite apontar para um modelo **local** rodando via
[**Ollama**](https://ollama.com) — sem chave paga e sem enviar dados para a
nuvem. No código de agentes do ADK, o modelo é declarado assim:

```python
from google.adk.models.lite_llm import LiteLlm

# Modelo local servido pelo Ollama (ex.: llama3)
model = LiteLlm(model="ollama/llama3")
```

Passos gerais: instale o Ollama, baixe um modelo (`ollama pull llama3`), garanta
que o serviço esteja no ar e configure o agente do ADK com `LiteLlm(...)`.
Para os detalhes de integração (LiteLLM, Ollama, variáveis e formatos de
`model`), consulte a **documentação oficial do ADK**:
**https://google.github.io/adk-docs/**

> Observação: essa via é para o **pipeline orquestrado do ADK** (`--adk`). O
> diagnóstico do pipeline direto (`config/inspector/diagnosis.py`) usa o cliente do
> Gemini; para um LLM 100% local sem Gemini, o caminho é o grafo ADK com
> LiteLlm/Ollama.

### (c) Usar um modelo "flash" (baixo custo)

Se optar pelo Gemini, prefira uma variante **"flash"** — é justamente o padrão
do projeto (`gemini-flash-latest`). Modelos "flash" são mais rápidos e baratos,
encaixando melhor nos limites do free tier do que variantes maiores ("pro").

---

## 5) Testar

Rode a CLI apontando para uma imagem de etiqueta:

```bash
python -m app.cli caminho/da/imagem.jpg
```

Como interpretar o resultado (campo `diagnosis_method`):

- **Sem chave** → o rodapé mostra `via: rules` (e no JSON,
  `"diagnosis_method": "rules"`). Diagnóstico veio da base Zebra.
- **Com chave válida** → mostra `via: gemini` (JSON:
  `"diagnosis_method": "gemini"`). Diagnóstico veio do LLM.

Para inspecionar o laudo completo, incluindo o campo `diagnosis_method`, use o
formato JSON:

```bash
python -m app.cli caminho/da/imagem.jpg --json
```

> Dica: se você configurou a chave mas continua vendo `via: rules`, verifique
> se o `.env` está em `src/`, se a variável foi de fato exportada na sessão
> atual, e se a biblioteca do Gemini (`google-genai`) está instalada. Qualquer
> falha faz o sistema cair, de forma silenciosa e graciosa, para as regras.
