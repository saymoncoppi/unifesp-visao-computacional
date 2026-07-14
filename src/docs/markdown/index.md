---
title: Inspetor de Etiquetas
description: Visão geral do inspetor de etiquetas de código de barras — visão computacional, CNN (PyTorch) e pipeline multiagente (Gemini + ADK).
---

Dada a **foto de uma etiqueta** com código de barras, o sistema detecta defeitos
típicos de impressão térmica e sugere a **causa provável** e a **correção**,
combinando **OpenCV**, **pyzbar**, **Tesseract**, uma **CNN (PyTorch)** e o
**Gemini**, orquestrados pelo **Agent Development Kit (ADK)**. A entrega é um
**chat**: envie a imagem, receba o laudo.

> Projeto da disciplina **Visão Computacional (cód. 2587)** — PPG em Ciência da
> Computação, ICT/UNIFESP.

## O que o sistema faz

Dada a imagem de uma etiqueta com código de barras, o sistema:

1. **decodifica** o código (simbologia + conteúdo) e diz se é legível — OpenCV + pyzbar;
2. faz **OCR** do texto humano-legível — Tesseract;
3. estima **indicadores de qualidade** (contraste, uniformidade, nitidez) — OpenCV;
4. **classifica o defeito** de impressão entre 7 classes — CNN MobileNetV3-Small (PyTorch);
5. **diagnostica a causa provável e a correção** — Gemini (ADK) com *fallback* por
   regras sobre a base de conhecimento Zebra;
6. consolida tudo em um **laudo** JSON, servido por uma **API/chat**.

## Arquitetura (pipeline multiagente)

A orquestração usa o **ADK**: as análises 1–4 rodam **em paralelo**, seguidas do
diagnóstico e da montagem do laudo.

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

### Dois modos de execução

- **Pipeline direto** (`inspetor.ferramentas.analisar_imagem`): encadeia as funções
  sem o ADK. Funciona **mesmo sem chave do Gemini** (diagnóstico por regras da base
  Zebra). É o *baseline* monolítico da avaliação e o núcleo usado por CLI e API.
- **Pipeline orquestrado** (`inspetor.agentes`): o grafo ADK acima
  (`ParallelAgent` → diagnóstico → laudo), acionado com `--adk` na CLI ou
  `adk=true` na API.

## Degradação graciosa

O sistema nunca "quebra" por falta de biblioteca: se `pyzbar`/Tesseract/`torch`/Gemini
não estiverem disponíveis, a etapa correspondente retorna um aviso no campo `erros`
do laudo e as demais continuam. Sem `GOOGLE_API_KEY`, o diagnóstico usa as **regras
da base Zebra** (`inspetor/kb.py` + `dados/kb_zebra.json`) em vez do Gemini.

## Classes de defeito (CNN)

A CNN classifica a etiqueta entre **7 classes** (a ordem define o índice usado pela
rede — ver `inspetor/config.py`):

| Classe (`CLASSES`) | Rótulo (`CLASSE_PT`) |
| --- | --- |
| `sem_defeito` | Sem defeito |
| `cabeca_queimada` | Elemento da cabeça danificado |
| `ribbon_enrugado` | Ribbon enrugado |
| `ponto_queimado` | Ponto queimado (darkness alto) |
| `impressao_clara` | Impressão clara (darkness baixo) |
| `pressao_desigual` | Pressão desigual da cabeça |
| `cabeca_suja` | Cabeça de impressão suja (voids) |

## Estrutura do projeto

```
src/
├── inspetor/               # pacote principal
│   ├── config.py           # classes, caminhos, constantes
│   ├── visao.py            # OpenCV (segmentação), pyzbar (decode), Tesseract (OCR), indicadores
│   ├── rede.py             # CNN MobileNetV3-Small (construir/carregar/prever)
│   ├── dataset.py          # Dataset PyTorch (lê dataset_sintetico/labels.csv)
│   ├── treino.py           # treino por transferência de aprendizado
│   ├── kb.py               # base de conhecimento Zebra (defeito→causa→ação)
│   ├── diagnostico.py      # Gemini com fallback por regras
│   ├── ferramentas.py      # ferramentas do ADK + analisar_imagem (pipeline direto)
│   ├── agentes.py          # grafo ADK (paralelo → diagnóstico → laudo)
│   └── laudo.py            # esquema do laudo
├── app/
│   ├── cli.py              # linha de comando
│   ├── api.py              # FastAPI (/analisar) + serve o chat
│   └── chat.html           # chat web (envio de imagem)
├── dados/kb_zebra.json     # KB extraída da documentação Zebra
├── gerar_dataset.py        # gerador do dataset sintético
├── pyproject.toml          # dependências (gerenciadas por uv)
└── ESPECIFICACAO.md        # contrato de interfaces
```

## Base de conhecimento

`dados/kb_zebra.json` consolida o mapeamento **defeito → causa → ação** da
documentação oficial da Zebra (ZT411/ZT421 e a base *Resolving Print Quality
Issues*), usado pelo agente de diagnóstico. O campo `fonte` referencia
"Zebra Technologies (2024)".

## Próximos passos

- [Instalação](/instalacao/) — pré-requisitos, `uv sync` e dependências de sistema.
- [Uso](/uso/) — CLI, chat web e chat nativo do ADK.
- [Treinamento da CNN](/treinamento/) — treinar o classificador de defeitos.
- [Datasets](/datasets/) — dataset sintético e datasets externos do Roboflow.
- [API HTTP](/api/) — endpoints e formato do laudo.
- [Configurar o Gemini](/configurar-gemini/) — chave de API e o modo por regras.
