---
title: Instalação
description: Pré-requisitos e instalação do inspetor de etiquetas — Python 3.12 via uv e dependências de sistema (libzbar0, Tesseract).
---

Esta página cobre a preparação do ambiente para rodar o **inspetor de etiquetas**
(o pacote Python em `src/`). A documentação (este site) tem instalação própria,
descrita ao final.

## Pré-requisitos

- **Python 3.12** — o projeto exige `>=3.10,<3.13` (em 3.13/3.14 alguns wheels de
  `torch`/`opencv` ainda podem faltar). Recomenda-se gerenciar via
  [`uv`](https://docs.astral.sh/uv/).
- **[uv](https://docs.astral.sh/uv/)** — gerenciador de pacotes e ambientes Python
  usado pelo projeto (`pyproject.toml` + `uv.lock`).
- **Dependências de sistema**: ZBar e Tesseract (ver abaixo).

## 1. Dependências de sistema (ZBar e Tesseract)

O `pyzbar` precisa da biblioteca **ZBar** e o OCR precisa do **Tesseract**
(com o pacote de idioma português):

```bash
# Debian/Ubuntu
sudo apt install libzbar0 tesseract-ocr tesseract-ocr-por

# Fedora
sudo dnf install zbar tesseract tesseract-langpack-por
```

:::note
Sem essas bibliotecas o sistema **não quebra**: as etapas de leitura/OCR apenas
retornam um aviso no campo `erros` do laudo (degradação graciosa).
:::

## 2. Ambiente Python com uv

A partir da pasta `src/` (onde estão `pyproject.toml` e `uv.lock`):

```bash
cd src
uv sync
```

O `uv sync` cria o ambiente virtual (`.venv/`) e instala as dependências fixadas
no `uv.lock`. O projeto já configura o índice **CPU** do PyTorch (torch/torchvision
sem CUDA), então a instalação é leve.

Para instalar também o grupo opcional de **download de datasets** (Roboflow):

```bash
uv sync --extra datasets
```

Para rodar comandos dentro do ambiente, use `uv run`:

```bash
uv run python -m app.cli --help
```

:::tip
Onde a documentação usar `python -m ...`, você pode prefixar com `uv run`
(ex.: `uv run python -m app.cli foto.jpg`) para garantir o ambiente correto.
:::

## 3. Chave do Gemini (opcional)

Copie o arquivo de exemplo e preencha a chave, se quiser usar o Gemini:

```bash
cp .env.example .env      # opcional: preencha GOOGLE_API_KEY
```

Sem a chave, o diagnóstico usa o **fallback por regras** sobre a base de
conhecimento Zebra. Veja [Configurar o Gemini](/configurar-gemini/).

## Abrir a documentação (este site)

A documentação é uma **página única** (`src/docs/index.html`) com estilo via CDN —
não precisa de build. Abra o arquivo `src/docs/index.html` no navegador (duplo-clique).
