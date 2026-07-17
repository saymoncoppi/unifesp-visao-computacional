# Inspetor de Etiquetas — visão computacional + multiagente (ADK)

Projeto da disciplina **Visão Computacional (cód. 2587)** — PPG em Ciência da
Computação, ICT/UNIFESP.

Dada a **foto de uma etiqueta** com código de barras, o sistema detecta defeitos
típicos de impressão térmica e sugere a **causa provável** e a **correção**,
combinando OpenCV, ZBar/pyzbar, uma **CNN (PyTorch)** e o **Gemini**, com um caminho
orquestrado pelo **Agent Development Kit (ADK)**. A entrega é um **chat**: envie a
imagem, receba o laudo.

> **Não é um verificador certificado.** Os indicadores de qualidade são aproximações
> inspiradas na ISO/IEC 15416 — o foco é apontar a **causa física** e a **ação
> corretiva**, não emitir uma nota A–F.

## Como o diagnóstico é produzido

Há três motores, selecionáveis no chat (menu ⋮ → *Inspetor*) ou por flags:

```
                         imagem da etiqueta
                                │
        ┌───────────────────────┴───────────────────────┐
        │  percepção determinística (sempre)             │
        │  leitura (pyzbar) · indicadores (OpenCV) · CNN │
        └───────────────────────┬───────────────────────┘
                                ▼
              ┌─────────────── motor de diagnóstico ───────────────┐
              │  KB    → regras da base Zebra (defeito→causa→ação)   │
              │  LLM   → Gemini fundamentado na KB (fallback: regras)│
              │  Auto  → árbitro visual multimodal (par confundível) │
              │          + diagnóstico Gemini fundamentado           │
              └───────────────────────┬────────────────────────────┘
                                ▼
                    laudo JSON ─────────────────────► resposta no chat
```

- **Pipeline direto** (`config.inspector.tools.analyze_image`): encadeia as funções
  sem o ADK. Funciona **mesmo sem chave do Gemini** (diagnóstico por regras). É o
  *baseline* monolítico e o núcleo usado por CLI e API (motores **KB** e **LLM**).
- **Pipeline orquestrado / Auto** (`config.inspector.agents.analyze_via_adk`): faz a
  percepção de forma determinística (sem gastar LLM) e usa o ADK só onde há raciocínio
  real — um **árbitro visual** que só dispara no par confundível
  `no_defect` ↔ `damaged_printhead_element` e o diagnóstico fundamentado. Isso mantém
  ~1–2 chamadas Gemini por análise, cabendo no free-tier (5 req/min). O grafo ADK
  completo (`ParallelAgent` → árbitro → diagnóstico → laudo) também é exposto para
  `adk web`.

## Estrutura

```
src/
├── config/
│   ├── inspector/            # pacote principal
│   │   ├── settings.py       # classes, caminhos, constantes, has_gemini()
│   │   ├── vision.py         # OpenCV (segmentação), pyzbar (decode), indicadores
│   │   ├── network.py        # CNN MobileNetV3-Small (construir/carregar/prever)
│   │   ├── dataset.py        # Dataset PyTorch (lê dataset_sintetico/labels.csv)
│   │   ├── training.py       # treino por transferência de aprendizado
│   │   ├── kb.py             # base de conhecimento Zebra (defeito→causa→ação)
│   │   ├── diagnosis.py      # Gemini com fallback por regras
│   │   ├── tools.py          # ferramentas do ADK + analyze_image (pipeline direto)
│   │   ├── agents.py         # grafo ADK + analyze_via_adk (árbitro visual)
│   │   ├── report.py         # esquema do laudo
│   │   └── ratelimit.py      # contador de cota do Gemini (free-tier, 5 req/min)
│   ├── data/kb_zebra.json    # KB extraída da documentação Zebra
│   ├── datasets/             # dataset sintético (+ bases reais opcionais)
│   ├── models/               # modelos treinados (.pt)
│   ├── results/              # saída dos experimentos do artigo
│   ├── generate_dataset.py   # gerador do dataset sintético
│   ├── experiments.py        # harness: split fixo, baselines, k-fold, McNemar
│   └── format_tables.py      # converte resultados em tabelas LaTeX (pt-BR)
├── app/
│   ├── cli.py                # linha de comando
│   ├── api.py                # FastAPI (/analyze, /analyze-htmx, /quota, /health) + serve o chat
│   ├── chat.html             # chat web (envio de imagem, câmera, scanner)
│   └── static/               # css/ + js/ (i18n, tema, menu, scanner ZXing, cota…)
├── docs/                     # documentação (index.html + markdown/)
├── pyproject.toml            # dependências (gerenciadas por uv)
├── requirements.txt          # espelho para instalação via pip
└── ESPECIFICACAO.md          # contrato de interfaces
```

O dataset sintético fica em `config/datasets/dataset_sintetico/` (gerado por
`config/generate_dataset.py`). O modelo padrão carregado é
`config/models/classificador_defeitos.pt` (sobreponível pela variável `MODEL_PATH`).

## Instalação

Requer **Python 3.10–3.12** (`>=3.10,<3.13`). Recomenda-se o [`uv`](https://docs.astral.sh/uv/).

Dependência de sistema (ZBar, para o `pyzbar`):
```bash
# Debian/Ubuntu
sudo apt install libzbar0
# Fedora
sudo dnf install zbar
```

Ambiente Python (a partir de `src/`):
```bash
cd src
uv sync                     # cria o .venv e instala tudo (torch/torchvision no índice CPU)
cp .env.example .env        # opcional: preencha GOOGLE_API_KEY para usar o Gemini
```

Alternativa via pip: `python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt`.

## Uso

**1) (Opcional) Gerar/atualizar o dataset sintético**
```bash
python config/generate_dataset.py --out config/datasets/dataset_sintetico --per-class 200 --seed 42
```

**2) Treinar a CNN**
```bash
python -m config.inspector.training --epochs 10
# salva o melhor modelo (por val_acc) em config/models/classificador_defeitos.pt
```

**3) Analisar uma imagem (CLI)**
```bash
python -m app.cli config/datasets/dataset_sintetico/images/test/wrinkled_ribbon/ean13_075.png
python -m app.cli minha_etiqueta.jpg --json      # laudo completo em JSON
python -m app.cli minha_etiqueta.jpg --adk       # via grafo ADK (cai no pipeline direto se falhar)
```

**4) Chat web (enviar imagem → laudo)**
```bash
# Desenvolvimento (auto-reload, só na máquina local) — rode a partir de src/:
uv run uvicorn app.api:app --reload
# abra http://localhost:8000  → envie a foto da etiqueta

# Rede/produção (acessível de outras máquinas) — rode a partir de src/:
uv run gunicorn -c config/gunicorn.conf.py app.api:app
# depois acesse http://<sua-ip-na-rede>:8000

# Ou, da raiz do repo, o lançador único em HTTPS (gera cert autoassinado):
./run_server.sh
```

O modo de rede usa **gunicorn** com worker Uvicorn e `workers=1`: um único processo
mantém o contador de cota (`config/inspector/ratelimit.py`, Gemini free = 5 req/min)
globalmente correto. A configuração está em `config/gunicorn.conf.py`.

**5) Chat nativo do ADK (opcional)**
```bash
adk web        # interface do ADK sobre o grafo em config/inspector/agents.py (requer Gemini)
```

## API HTTP

Servida por FastAPI (`app/api.py`). Swagger em `http://localhost:8000/docs`.

| Método | Rota | Descrição |
| --- | --- | --- |
| `GET` | `/` | Serve o chat (`chat.html`). |
| `GET` | `/health` | *Health check* → `{"status": "ok"}`. |
| `GET` | `/quota` | Estado da cota do Gemini (`ratelimit.snapshot()`). |
| `POST` | `/analyze` | Campo `image` (arquivo) + query `adk` (bool). Devolve o laudo em **JSON**. |
| `POST` | `/analyze-htmx` | Campos `image`, `language`, `inspector`. Devolve o **cartão HTML** do laudo (usado pelo chat via htmx). |

```bash
curl -F "image=@minha_etiqueta.jpg" http://localhost:8000/analyze
curl -F "image=@minha_etiqueta.jpg" "http://localhost:8000/analyze?adk=true"
```

## Degradação graciosa

O sistema nunca "quebra" por falta de biblioteca: se `pyzbar`/torch/Gemini não
estiverem disponíveis, a etapa correspondente registra um aviso em `errors` e as
demais continuam. Sem `GOOGLE_API_KEY`/`GEMINI_API_KEY`, o diagnóstico usa as **regras
da base Zebra** (`config/inspector/kb.py` + `config/data/kb_zebra.json`).

## Base de conhecimento

`config/data/kb_zebra.json` consolida o mapeamento **defeito → causa → ação** da
documentação oficial da Zebra (ZT411/ZT421 e a base *Resolving Print Quality Issues*),
usado pelo motor de regras e como contexto do LLM.

## Classes de defeito (CNN)

`no_defect`, `damaged_printhead_element`, `wrinkled_ribbon`, `burnt_spot`,
`light_print`, `uneven_pressure`, `dirty_printhead` (7 classes; a ordem em
`config/inspector/settings.py` define o índice da rede — não reordene sem retreinar).

## Resultados & reprodutibilidade

No teste sintético (105 imagens), a MobileNetV3-Small atinge **acurácia ≈ 0,84 /
macro-F1 ≈ 0,84** (~1,5 M parâmetros, ~4,5 ms em CPU). A confusão residual está no par
`no_defect` ↔ `damaged_printhead_element` (F1 ≈ 0,55), que o árbitro visual do modo
Auto corrige. Baselines (ResNet18, EfficientNet-B0), 5-fold e McNemar são reproduzíveis
com o harness:

```bash
uv run python -m config.experiments --epochs 40 --lr 5e-4 --batch 32 --kfolds 5 --seed 42
uv run python config/format_tables.py   # imprime as tabelas LaTeX
```

Ver `Research/` (artigo) e `../NOTAS-EVOLUCAO.md` (decisões e pendências).
