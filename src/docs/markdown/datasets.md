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
python config/generate_dataset.py --out config/datasets/dataset_sintetico --per-class 90 --seed 42
```

Argumentos:

| Flag | Padrão | Descrição |
| --- | --- | --- |
| `--out` | `dataset` | Pasta de saída do dataset. |
| `--per-class` | `90` | Imagens por classe. |
| `--seed` | `42` | Semente aleatória (reprodutibilidade). |
| `--only-1d` | *(desligado)* | Ignora QR/DataMatrix (só simbologias 1D). |

**Saída** gerada:

```
<out>/
├── images/<split>/<class>/<symbology>_<idx>.png
├── labels.csv           # filename, split, class, symbology, payload, params
└── previews/<class>.png # montagem para o artigo
```

- **Classes** (7): `no_defect`, `damaged_printhead_element`, `wrinkled_ribbon`,
  `burnt_spot`, `light_print`, `uneven_pressure`, `dirty_printhead`.
- **Simbologias**: 1D (`code128`, `code39`, `ean13`, `ean8`, `itf`) e
  2D (`qr`, `datamatrix`).

O caminho padrão esperado pelo treino é `config/datasets/dataset_sintetico/` (configurável
pela variável de ambiente `DATASET_DIR`).

## Datasets externos (Roboflow)

Para treinar/avaliar com **imagens reais** de códigos de barras danificados, o
Roboflow Universe reúne vários datasets públicos. Busque por códigos de barras
com dano/qualidade de impressão:

- **https://universe.roboflow.com/search?q=barcode+damage**

Após baixar, ajuste o layout para o formato esperado (`images/<split>/<class>/...`
+ `labels.csv`) ou aponte `DATASET_DIR` para a pasta do dataset externo antes de
[treinar a CNN](/treinamento/).
