# Inspetor de Etiquetas — Visão Computacional (UNIFESP)

Diagnóstico automático de falhas de impressão em etiquetas de código de barras,
combinando visão computacional clássica (OpenCV, pyzbar, Tesseract), uma CNN
(MobileNetV3 em PyTorch) e um agente LLM (Google Gemini) com base de conhecimento
Zebra por regras como *fallback*. Trabalho da disciplina **Visão Computacional**,
PPG em Ciência da Computação, ICT/UNIFESP.

## Estrutura do repositório

- `artigo-latex/` — artigo científico (abnTeX2): `artigo.tex`, `referencias.bib`, `figuras/`, `artigo.pdf`.
- `src/` — implementação em Python:
  - `app/` — API FastAPI (`api.py`) + interface de chat (`chat.html`).
  - `inspetor/` — pipeline: visão (`visao.py`), CNN (`rede.py`/`treino.py`), diagnóstico
    (`diagnostico.py`, LLM Gemini + base de conhecimento Zebra `kb.py`), laudo e agentes ADK.
  - `docs/` — documentação (página única `index.html` + `markdown/`).
  - `datasets/`, `modelos/` — dataset sintético e modelo treinado.
  - `tests/` — testes (pytest).
- `outros-arquivos/` — materiais de referência.

## Como rodar

```bash
cd src
uv sync                                   # cria o ambiente (.venv) e instala as dependências
.venv/bin/uvicorn app.api:app --reload    # sobe a API + chat em http://127.0.0.1:8000
```

Para o diagnóstico via **Gemini**, defina `GOOGLE_API_KEY` em `src/.env`
(veja `src/.env.example` e `src/CONFIGURAR_GEMINI.md`). Sem a chave, o sistema usa
a base de conhecimento Zebra por regras.

## Interface

Chat web com envio de imagem e laudo estruturado (leitura do código, indicadores de
qualidade, defeito classificado, causa provável e correção sugerida). O menu de
configurações (⋮) oferece:

- **Idioma** — Português / English (interface e laudo internacionalizados).
- **Tema** — claro / escuro / automático.
- **Inspetor** — motor de diagnóstico: LLM (Gemini) / KB Zebra Technologies / Auto.
- **Ações** — exportar em PDF, limpar a conversa.

Se a imagem não contém um código de barras, o inspetor exibe apenas o aviso
correspondente — sem executar a CNN nem chamar o LLM.

## Autoria

Saymon Coppi de Oliveira Silva — disciplina de Visão Computacional, ICT/UNIFESP.
