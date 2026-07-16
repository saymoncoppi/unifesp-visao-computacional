# Inspetor de Etiquetas — visão computacional + multiagente (ADK)

Projeto da disciplina **Visão Computacional (cód. 2587)** — PPG em Ciência da
Computação, ICT/UNIFESP.

Dada a **foto de uma etiqueta** com código de barras, o sistema detecta defeitos
típicos de impressão térmica e sugere a **causa provável** e a **correção**,
combinando OpenCV, pyzbar, Tesseract, uma **CNN (PyTorch)** e o **Gemini**,
orquestrados pelo **Agent Development Kit (ADK)**. A entrega é um **chat**: envie a
imagem, receba o laudo.

## Arquitetura (multiagente)

```
                         imagem da etiqueta
                                │
                 ┌──────────────┴───────────────┐
                 │        ParallelAgent          │   (análises independentes)
                 │  ┌─────────┬──────────┬─────┐ │
                 │  │ leitura │indicadores│defeito│ │
                 │  │pyzbar+  │ OpenCV    │ CNN   │ │
                 │  │Tesseract│(contraste)│PyTorch│ │
                 │  └─────────┴──────────┴─────┘ │
                 └──────────────┬───────────────┘
                                ▼
                    agente de diagnóstico (Gemini + KB Zebra)   → causa + correção
                                ▼
                    agente de laudo (JSON) ─────────────────────► resposta no chat
```

- **Pipeline direto** (`config.inspector.tools.analyze_image`): encadeia as funções
  sem o ADK. Funciona **mesmo sem chave do Gemini** (diagnóstico por regras da base
  Zebra). É o *baseline* monolítico da avaliação.
- **Pipeline orquestrado** (`config.inspector.agents`): o grafo ADK acima.

## Estrutura

```
src/
├── config/
│   ├── inspector/            # pacote principal
│   │   ├── settings.py       # classes, caminhos, constantes
│   │   ├── vision.py         # OpenCV (segmentação), pyzbar (decode), Tesseract (OCR), indicadores
│   │   ├── network.py        # CNN MobileNetV3-Small (construir/carregar/prever)
│   │   ├── dataset.py        # Dataset PyTorch (lê dataset_sintetico/labels.csv)
│   │   ├── training.py       # treino por transferência de aprendizado
│   │   ├── kb.py             # base de conhecimento Zebra (defeito→causa→ação)
│   │   ├── diagnosis.py      # Gemini com fallback por regras
│   │   ├── tools.py          # ferramentas do ADK + analyze_image (pipeline direto)
│   │   ├── agents.py         # grafo ADK (paralelo → diagnóstico → laudo)
│   │   └── report.py         # esquema do laudo
│   └── data/kb_zebra.json    # KB extraída da documentação Zebra
├── app/
│   ├── cli.py              # linha de comando
│   ├── api.py              # FastAPI (/analyze) + serve o chat
│   └── chat.html           # chat web (envio de imagem)
├── requirements.txt
├── .env.example
└── ESPECIFICACAO.md        # contrato de interfaces
```

O dataset sintético fica em `config/datasets/dataset_sintetico/` (gerado por `config/generate_dataset.py`).

## Instalação

Sugerido **Python 3.10–3.12** (em 3.14 alguns wheels de `torch`/`opencv` podem faltar).

Dependências de sistema (ZBar e Tesseract):
```bash
# Debian/Ubuntu
sudo apt install libzbar0 tesseract-ocr tesseract-ocr-por
# Fedora
sudo dnf install zbar tesseract tesseract-langpack-por
```

Ambiente Python:
```bash
cd solucao
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env      # opcional: preencha GOOGLE_API_KEY para usar o Gemini
```

## Uso

**1) (Opcional) Gerar/atualizar o dataset sintético**
```bash
python config/generate_dataset.py --out config/datasets/dataset_sintetico --per-class 90 --seed 42
```

**2) Treinar a CNN**
```bash
python -m config.inspector.training --epochs 10
# salva o modelo em config/models/classificador_defeitos.pt
```

**3) Analisar uma imagem (CLI)**
```bash
python -m app.cli config/datasets/dataset_sintetico/images/test/wrinkled_ribbon/ean13_075.png
python -m app.cli minha_etiqueta.jpg --json      # laudo completo em JSON
python -m app.cli minha_etiqueta.jpg --adk       # via grafo ADK (requer Gemini)
```

**4) Chat web (enviar imagem → laudo)**
```bash
uvicorn app.api:app --reload
# abra http://localhost:8000  → envie a foto da etiqueta
```

**5) Chat nativo do ADK (opcional)**
```bash
adk web        # interface de chat do ADK sobre config/inspector/agents.py
```

## Degradação graciosa

O sistema nunca "quebra" por falta de biblioteca: se `pyzbar`/Tesseract/torch/Gemini
não estiverem disponíveis, a etapa correspondente retorna um aviso no campo `errors`
do laudo e as demais continuam. Sem `GOOGLE_API_KEY`, o diagnóstico usa as **regras
da base Zebra** (`config/inspector/kb.py` + `config/data/kb_zebra.json`) em vez do Gemini.

## Base de conhecimento

`config/data/kb_zebra.json` consolida o mapeamento **defeito → causa → ação** da
documentação oficial da Zebra (ZT411/ZT421 e base de conhecimento *Resolving Print
Quality Issues*), usado pelo agente de diagnóstico.

## Classes de defeito (CNN)

`no_defect`, `damaged_printhead_element`, `wrinkled_ribbon`, `burnt_spot`,
`light_print`, `uneven_pressure`, `dirty_printhead` (ver `config/inspector/settings.py`).
