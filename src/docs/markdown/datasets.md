---
title: Datasets
description: Dataset sintético (gerar_dataset.py) e datasets externos de códigos de barras danificados (Roboflow) com o downloader baixar_roboflow.py.
---

O treinamento do classificador usa, por padrão, um **dataset sintético** gerado
localmente. Também é possível complementar/substituir por **datasets externos**
(Roboflow) de códigos de barras danificados.

## Dataset sintético (`gerar_dataset.py`)

O script `gerar_dataset.py` produz um dataset **sintético, balanceado e rotulado**
de defeitos de impressão de códigos de barras (1D e 2D). Cada defeito reproduz a
assinatura visual descrita na documentação Zebra ZT411/ZT421 (*troubleshooting* de
qualidade de impressão) — é o dataset que treina o "agente de defeitos físicos".

```bash
python gerar_dataset.py --out datasets/dataset_sintetico --per-class 90 --seed 42
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
├── images/<split>/<classe>/<simbologia>_<idx>.png
├── labels.csv           # filename, split, classe, simbologia, payload, params
└── previews/<classe>.png # montagem para o artigo
```

- **Classes** (7): `sem_defeito`, `cabeca_queimada`, `ribbon_enrugado`,
  `ponto_queimado`, `impressao_clara`, `pressao_desigual`, `cabeca_suja`.
- **Simbologias**: 1D (`code128`, `code39`, `ean13`, `ean8`, `itf`) e
  2D (`qr`, `datamatrix`).

O caminho padrão esperado pelo treino é `datasets/dataset_sintetico/` (configurável
pela variável de ambiente `DATASET_DIR`).

## Datasets externos (Roboflow)

Para treinar/avaliar com **imagens reais** de códigos de barras danificados, o
Roboflow Universe reúne vários datasets públicos. Busque por códigos de barras
com dano/qualidade de impressão:

- **https://universe.roboflow.com/search?q=barcode+damage**

### Downloader `baixar_roboflow.py`

O download é automatizado pelo script `baixar_roboflow.py`, que usa o SDK do
Roboflow (dependência opcional do projeto). Instale o extra e forneça sua chave
gratuita de API:

```bash
uv sync --extra datasets          # instala o pacote `roboflow`
export ROBOFLOW_API_KEY="sua_chave_aqui"
python baixar_roboflow.py
```

:::note
O acesso ao Roboflow requer uma **chave de API gratuita** (crie uma conta em
roboflow.com). O extra `datasets` (que traz o pacote `roboflow`) está declarado no
`pyproject.toml` e **não** é instalado pelo `uv sync` padrão.
:::

Após baixar, ajuste o layout para o formato esperado (`images/<split>/<classe>/...`
+ `labels.csv`) ou aponte `DATASET_DIR` para a pasta do dataset externo antes de
[treinar a CNN](/treinamento/).
