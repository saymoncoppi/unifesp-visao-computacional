# Laboratório 03 — Granulometria Morfológica

Caracterização de texturas da base **KTH-TIPS** por **assinaturas granulométricas**
(pattern spectrum) obtidas por aberturas morfológicas em tons de cinza em múltiplas
escalas. Disciplina de **Visão Computacional**, PPG em Ciência da Computação, ICT/UNIFESP.

## Ideia

Cada imagem é representada por uma assinatura `PS(r)` — a fração da "massa" de
intensidade removida por uma abertura com elemento estruturante de raio `r`:

```
V(r) = soma da imagem aberta por um disco de raio r      (V(0) = soma da original)
PS(r) = ( V(r-1) - V(r) ) / V(0)      # histograma de escalas, normalizado
```

`PS(r)` é um histograma das escalas das estruturas da textura. Ver dedução completa
em [relatorio/relatorio.tex](relatorio/relatorio.tex).

## Classes e configuração

| Item | Valor |
|------|-------|
| Base | KTH-TIPS (tons de cinza, 200×200) |
| Classes | `corduroy`, `cotton`, `linen` |
| Imagens/classe | 20 (60 no total) |
| Elemento estruturante | disco (`MORPH_ELLIPSE`), raios 1–25 |

As classes foram escolhidas para dar um cenário "2 semelhantes + 1 distinta":
`cotton` e `linen` são tramas finas (assinaturas quase sobrepostas, pico em `r≈2`)
e `corduroy` tem ranhuras grossas (pico secundário em `r≈10`).

## Resultados principais

- Distância L1 entre médias: `cotton`–`linen` = **0,129** (mais semelhantes);
  `corduroy` a **0,31–0,33** das demais (mais separável).
- Classificador **1-NN leave-one-out** sobre as assinaturas: **93,3%** de acurácia;
  a confusão concentra-se no par `cotton`/`linen`.

Figuras e tabelas em [resultados/](resultados/); análise completa no
[relatório em PDF](relatorio/relatorio.pdf).

## Estrutura

```
Labs/03/
├── src/
│   ├── granulometria.py   # núcleo: cálculo da assinatura (pattern spectrum)
│   ├── executar.py        # pipeline: assinaturas, figuras, CSV, análise 1-NN
│   └── pyproject.toml      # dependências (gerenciadas com uv)
├── dados/                  # subconjunto KTH-TIPS (3 classes × 20 imagens)
├── resultados/             # figuras (.png) + assinaturas/distâncias (.csv)
├── relatorio/              # relatorio.tex + relatorio.pdf
└── lab03_granulometria_atualizado.pdf   # enunciado
```

## Como rodar

```bash
cd src
uv sync                    # cria o ambiente e instala as dependências
uv run python executar.py  # gera CSVs e figuras em ../resultados/
```

Para recompilar o relatório: `cd relatorio && pdflatex relatorio.tex` (2 passadas).

## Saídas geradas em `resultados/`

- `assinaturas.csv` — uma linha por imagem, colunas `r1..r25` (assinatura completa).
- `distancias_L1.csv`, `resumo_classes.csv` — dados quantitativos da comparação.
- `exemplos_base.png` — exemplos das três classes.
- `assinaturas_individuais.png` — individuais + média por classe.
- `assinaturas_comparacao.png` — médias sobrepostas (±1 desvio).
- `curvas_cumulativas.png` — curvas granulométricas cumulativas Φ(r).
- `matriz_confusao.png` — confusão do classificador 1-NN leave-one-out.
