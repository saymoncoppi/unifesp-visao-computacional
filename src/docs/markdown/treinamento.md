---
title: Treinamento da CNN
description: Como treinar o classificador de defeitos (MobileNetV3-Small, PyTorch) por transferência de aprendizado sobre o dataset sintético.
---

O classificador de defeitos é uma **CNN MobileNetV3-Small** (PyTorch/torchvision),
treinada por **transferência de aprendizado** sobre o [dataset sintético](/datasets/).

## Pré-requisitos

- Ambiente Python instalado (ver [Instalação](/instalacao/)).
- Um dataset rotulado em `datasets/dataset_sintetico/` com o `labels.csv`
  (splits `train`/`val`/`test`). Gere-o conforme [Datasets](/datasets/) se ainda
  não existir.

## Treinar

```bash
python -m inspetor.treino --epocas 10
# salva o melhor modelo (por val_acc) em inspetor/modelos/classificador_defeitos.pt
```

Argumentos do script (`inspetor/treino.py`):

| Flag | Padrão | Descrição |
| --- | --- | --- |
| `--epocas` | `10` | Número de épocas de treino. |
| `--lr` | `1e-3` | Taxa de aprendizado (otimizador Adam). |
| `--batch` | `32` | Tamanho do *batch*. |
| `--saida` | `inspetor/modelos/classificador_defeitos.pt` | Caminho do modelo salvo. |

## Como funciona

- **Backbone**: `mobilenet_v3_small` pré-treinado (ImageNet); a última camada
  `Linear` é trocada para as **7 classes** do projeto.
- **Transferência de aprendizado**: por padrão o *backbone* é congelado e apenas a
  cabeça é treinada (`congelar_backbone=True`).
- **Pré-processamento**: `Resize(224)`, `Grayscale(3)`, `ToTensor` e `Normalize`
  com média/desvio do ImageNet (`MEAN`/`STD` em `inspetor/config.py`); no treino há
  *augmentation* leve.
- **Otimização**: perda `CrossEntropy`, otimizador `Adam`; salva o **melhor** modelo
  pela acurácia de validação.
- **Retorno**: a função `treinar(...)` devolve métricas finais
  `{"val_acc": ..., "test_acc": ..., "por_classe": {...}}`.

:::caution
A **ordem** das classes em `CLASSES` (em `inspetor/config.py`) define o índice usado
pela rede. Não reordene as classes sem **retreinar** o modelo.
:::

## Dataset

O modelo aprende sobre o **dataset sintético** (padrão) em
`datasets/dataset_sintetico/`, cujas 7 classes reproduzem assinaturas visuais de
defeitos de impressão térmica descritas na documentação Zebra. Para gerar ou
substituir o dataset (inclusive por dados reais do Roboflow), veja
[Datasets](/datasets/).

## Depois de treinar

Com o modelo salvo em `inspetor/modelos/classificador_defeitos.pt`, a etapa de
classificação passa a funcionar na [CLI](/uso/) e na [API](/api/). Se o arquivo do
modelo não existir, a etapa de classificação retorna um aviso no campo `erros` do
laudo (degradação graciosa) — as demais análises continuam.
