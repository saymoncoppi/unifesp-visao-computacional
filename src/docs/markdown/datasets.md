---
title: Datasets
description: Dataset sintético (generate_dataset.py) e datasets externos de códigos de barras danificados (Roboflow).
---

O treinamento do classificador usa, por padrão, um **dataset sintético** gerado
localmente. Também é possível complementar/substituir por **datasets externos**
(Roboflow) de códigos de barras danificados.

## Dataset sintético (`generate_dataset.py`)

O script `generate_dataset.py` produz um dataset **sintético, balanceado e rotulado**
de defeitos de impressão de códigos de barras (1D e 2D). Cada defeito reproduz a
assinatura visual descrita na documentação Zebra ZT411/ZT421 (*troubleshooting* de
qualidade de impressão) — é o dataset que treina o "agente de defeitos físicos".

```bash
# só sintético (comportamento clássico, agora com defeitos realistas)
python config/generate_dataset.py --out config/datasets/dataset_sintetico --per-class 200 --seed 42

# misturando bases REAIS (BarBeR/Roboflow) para reduzir o domain gap
python config/generate_dataset.py --per-class 400 \
    --bases-dir config/datasets/real_bases --real-fraction 0.5
```

Argumentos:

| Flag | Padrão | Descrição |
| --- | --- | --- |
| `--out` | `dataset_sintetico` | Pasta de saída do dataset. |
| `--per-class` | `200` | Imagens por classe. |
| `--seed` | `42` | Semente aleatória (reprodutibilidade). |
| `--only-1d` | *(desligado)* | Ignora QR/DataMatrix (só simbologias 1D). |
| `--bases-dir` | *(nenhum)* | Pasta de códigos **reais limpos** usados como base (subpasta = simbologia). |
| `--real-fraction` | `0.5` | Fração de amostras sorteadas de bases reais (quando houver). |
| `--severity` | *(aleatório)* | Fixa uma severidade (`low`/`medium`/`high`). |

**Saída** gerada:

```
<out>/
├── images/<split>/<class>/<symbology>_<idx>.png
├── labels.csv           # filename, split, classe, simbologia, payload, params, source, severity, is_scannable
└── previews/<class>.png # montagem para o artigo
```

Colunas novas do `labels.csv` (as antigas continuam iguais, então o loader não quebra):
`source` (`synthetic`|`real`), `severity` (`none`|`low`|`medium`|`high`), `is_scannable` (`yes`|`no`).

- **Classes** (10): `no_defect`, `damaged_printhead_element`, `wrinkled_ribbon`,
  `burnt_spot`, `light_print`, `uneven_pressure`, `dirty_printhead`, `smear`,
  `cutoff`, `registration_shift`. Cada defeito é calibrado contra as fotos reais
  em `outros-arquivos/imgs_zebra/`.
- **Simbologias**: 1D (`code128`, `code39`, `ean13`, `ean8`, `itf`) e
  2D (`qr`, `datamatrix`).

> **Atenção — a taxonomia mudou de 7 → 10 classes.** O checkpoint antigo
> `config/models/classificador_defeitos.pt` (cabeça de 7 saídas) fica
> **incompatível**: é preciso **regerar o dataset e re-treinar** antes de usar o
> app/rodar os experimentos. `settings.CLASSES` e `generate_dataset.CLASSES`
> precisam permanecer idênticos e na mesma ordem.

## Bases reais (BarBeR / Roboflow)

Aplicar os defeitos sintéticos sobre **barcodes reais limpos** é o que reduz o
*domain gap* sintético→real (a principal crítica ao dataset atual). Coloque os
recortes limpos em `config/datasets/real_bases/<simbologia>/*.png` e use
`--bases-dir`.

- **BarBeR** (ditto.ing.unimore.it/barber): ~8.748 imagens reais, 18 simbologias
  (1D+2D). **Só têm anotação de localização — não têm rótulo de defeito**, então
  servem como *bases limpas* a corromper, não como treino de defeito pronto.
  Exige registro e **citação obrigatória** (ICPR 2024 + EAAI 2025). O código é
  AGPL-3.0 (não linkar no app) e o dataset agrega ~12 datasets com licença
  própria — **não redistribuir as imagens dentro do app**; usar só em pesquisa.
- **Roboflow Universe** (universe.roboflow.com/search?q=class:barcode): baixar via
  `download_roboflow.py`. Licença **por projeto** — anotar cada uma. Use projetos
  limpos como base e um projeto com defeitos reais como **conjunto de teste**
  (experimento de generalização), nunca de treino direto.
