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
| `--clean-bases-dir` | *(nenhum)* | Bases **reais verificadas** (decodificáveis) para a classe de controle `no_defect`. |
| `--real-fraction` | `0.5` | Fração de amostras sorteadas de bases reais (quando houver). |
| `--exhaustive` | *(desligado)* | Usa **cada** base real uma vez (um defeito por imagem), balanceado entre as classes. |
| `--frame-aug` | `0.0` | Fração de amostras onde o código é encolhido + posicionado aleatoriamente (invariância a escala/posição — robustez a foto real). |
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

- **Classes** (7): `no_defect`, `damaged_printhead_element`, `wrinkled_ribbon`,
  `burnt_spot`, `light_print`, `uneven_pressure`, `dirty_printhead`. Cada defeito
  é calibrado contra as fotos reais em `config/data/imgs_zebra/`.
- **Simbologias**: 1D (`code128`, `code39`, `ean13`, `ean8`, `itf`) e
  2D (`qr`, `datamatrix`).

> **Taxonomia = 7 classes.** As classes posicionais (`cutoff`,
> `registration_shift`) foram removidas: na inferência em foto real elas agem como
> "sink" (qualquer código que não preenche o quadro vira `registration_shift`).
> `settings.CLASSES` e `generate_dataset.CLASSES` devem ficar idênticos e na mesma
> ordem que o modelo (`config/models/classificador_defeitos.pt`).

## Datasets intercambiáveis

Há três datasets, todos com a MESMA estrutura (`images/{train,val,test}` +
`labels.csv` + `previews/`) e as MESMAS 7 classes — trocáveis via `DATASET_DIR`:

| Dataset | Como gerar | Papel |
| --- | --- | --- |
| `dataset_sintetico` | `--per-class 200 --seed 42` | v1-style (sintético puro) — a config que funciona no app |
| `mixed_dataset_sintetico` | `--exhaustive --bases-dir real_bases --clean-bases-dir real_bases_clean` | 7 classes sobre TODAS as bases reais (BarBeR+Roboflow) |
| `mixed_aug_dataset_sintetico` | idem + `--frame-aug 0.5` | mixed + invariância de enquadramento (candidato a superar o v1 em foto real) |

Treine cada um num modelo separado e compare **nas suas etiquetas reais**:

```bash
DATASET_DIR=config/datasets/mixed_aug_dataset_sintetico \
  python -m config.inspector.training --out config/models/modelo_mixed_aug.pt \
    --epochs 40 --lr 5e-4 --batch 32 --no-freeze
```
Mantenha o vencedor como `config/models/classificador_defeitos.pt` (o que o app usa).

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
