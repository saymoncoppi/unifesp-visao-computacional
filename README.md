# Inspetor de Etiquetas — Visão Computacional (UNIFESP)

Diagnóstico automático de falhas de impressão em etiquetas de código de barras a
partir de uma **foto**: o sistema lê o código, estima indicadores de qualidade,
**classifica o defeito** de impressão térmica e sugere a **causa provável** e a
**correção**. Combina visão computacional clássica (OpenCV + ZBar/pyzbar), uma
**CNN (MobileNetV3-Small, PyTorch)** e um **agente de diagnóstico com LLM (Google
Gemini)** — com a base de conhecimento Zebra por regras como *fallback*.

Trabalho da disciplina **Visão Computacional (cód. 2587)** — PPG em Ciência da
Computação, ICT/UNIFESP.

> **Não é um verificador certificado.** Os indicadores (contraste, uniformidade,
> nitidez) são *aproximações inspiradas* na ISO/IEC 15416 e não substituem a
> medição de um verificador óptico. O objetivo é apontar a **causa física
> provável** e a **ação corretiva** — o que uma nota A–F de verificador não faz.

## Estrutura do repositório

- **`Research/`** — artigo científico (abnTeX2/ABNT): `diagnostico-de-defeitos-de-impressao-em-etiquetas-de-codigos-de-barras.tex`
  (+ `.pdf`), `referencias.bib`, figuras e notas de pesquisa (`LEIA-ME.md`, `notas-piloto-dataset-e3.md`).
- **`src/`** — implementação em Python (ver `src/README.md`):
  - `config/inspector/` — pacote principal: visão (`vision.py`), CNN
    (`network.py`/`training.py`), base de conhecimento Zebra (`kb.py`),
    diagnóstico LLM+regras (`diagnosis.py`), ferramentas e pipeline direto
    (`tools.py`), grafo multiagente ADK (`agents.py`), laudo (`report.py`),
    configuração (`settings.py`) e cota do Gemini (`ratelimit.py`).
  - `app/` — API FastAPI (`api.py`) + chat web (`chat.html` + `static/`) + CLI (`cli.py`).
  - `docs/` — documentação (página única `index.html` + espelho em `markdown/`).
  - `config/datasets/`, `config/models/` — dataset sintético e modelos treinados.
  - `config/data/` — base Zebra (`kb_zebra.json`) e fotos de referência (`imgs_zebra/`).
  - `config/experiments.py`, `config/format_tables.py`, `config/results/` — harness de
    reprodutibilidade do artigo (split fixo, baselines, k-fold, McNemar).
  - `tests/` — testes (pytest).
- **`NOTAS-EVOLUCAO.md`** — decisões experimentais, resultados e pendências.

## Como rodar

Tudo a partir de `src/` (o pacote Python vive lá; **não há pasta `solucao/`**):

```bash
cd src
uv sync                                          # cria o .venv e instala as dependências (inclui gunicorn)

# Desenvolvimento (auto-reload, só na máquina local):
uv run uvicorn app.api:app --reload              # sobe a API + chat em http://127.0.0.1:8000

# Rede/produção (acessível de outras máquinas da rede):
uv run gunicorn -c config/gunicorn.conf.py app.api:app
# depois acesse http://<sua-ip-na-rede>:8000 a partir de outras máquinas
```

Ou use o lançador único **`./run_server.sh`** (na raiz do repo): ele roda `uv sync`,
gera um certificado TLS autoassinado (`config/certs/`) e sobe o gunicorn em **HTTPS**
(`https://0.0.0.0:8000`) — útil porque a câmera do navegador exige contexto seguro.

O modo de rede usa **gunicorn** com worker Uvicorn e `workers=1` — um único processo
mantém o contador de cota do Gemini (free-tier = 5 req/min) correto. Veja
`config/gunicorn.conf.py` e `config/inspector/ratelimit.py`.

Para o diagnóstico via **Gemini**, defina `GOOGLE_API_KEY` (ou `GEMINI_API_KEY`) em
`src/.env` (veja `src/.env.example` e `src/CONFIGURAR_GEMINI.md`). **Sem a chave o
sistema continua funcionando**: o diagnóstico cai para as regras da base Zebra.

## Interface

Chat web com envio de imagem e laudo estruturado (leitura do código, indicadores de
qualidade, defeito classificado com confiança, causa provável e correção sugerida).
Recursos reais da interface:

- **Anexar** (`+`) — **Fotos** (galeria/arquivo), **Câmera** (captura nativa) e
  **Scan** (leitor de código ao vivo via ZXing, com seleção de câmera e zoom).
- **Menu de configurações** (⋮):
  - **Idioma** — Português / English (interface e laudo internacionalizados).
  - **Tema** — claro / escuro / automático.
  - **Inspetor** — motor de diagnóstico: **LLM (Gemini)**, **KB Zebra Technologies**
    (regras) ou **Auto** (multiagente ADK com arbitragem visual; aparece só com LLM
    configurado).
  - **Ações** — exportar em PDF (imprimir) e limpar a conversa.
- Idioma, tema e motor escolhidos ficam salvos no `localStorage`; um rodapé mostra a
  **cota do Gemini** restante no minuto.

Se a imagem não contém um código de barras, o inspetor exibe apenas o aviso
correspondente — **sem executar a CNN nem chamar o LLM** (curto-circuito de presença).

## Sobre os três motores

- **KB (regras)** — determinístico, mapeia a classe da CNN → causa → ação pela base
  Zebra. Não usa rede nem chave.
- **LLM (Gemini)** — pipeline direto: o Gemini redige a causa/correção com o contexto
  da base Zebra; cai para as regras se a chamada falhar. É o padrão.
- **Auto (multiagente/ADK)** — percepção determinística (leitura + indicadores + CNN)
  seguida de um **árbitro visual multimodal** que só é acionado no par confundível
  `no_defect` ↔ `damaged_printhead_element` e de um diagnóstico fundamentado. Essa
  otimização mantém ~1–2 chamadas Gemini por análise para caber no free-tier
  (5 req/min); o grafo ADK completo também é exposto via `adk web`.

## Resultados (resumo)

CNN MobileNetV3-Small (~1,5 M parâmetros, ~4,5 ms em CPU) no conjunto de teste
sintético: **acurácia ≈ 0,84 / macro-F1 ≈ 0,84**. O ponto fraco é a confusão mútua
`no_defect` ↔ `damaged_printhead_element` (F1 ≈ 0,55) — as zonas claras entre barras
imitam as linhas brancas do dano na cabeça; é exatamente esse par que o árbitro visual
do modo Auto corrige. Detalhes, baselines (ResNet18, EfficientNet-B0) e testes de
significância (McNemar, k-fold) no artigo em `Research/` e em `NOTAS-EVOLUCAO.md`.

## Autoria

Saymon Coppi de Oliveira Silva — disciplina de Visão Computacional, ICT/UNIFESP.
