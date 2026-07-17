# Notas experimentais — pipeline de dataset (10 classes) e justificativa empírica do E3

> Registro metodológico do piloto de reconstrução do dataset. Serve de base para
> as seções de Método/Resultados/Discussão do artigo e, sobretudo, como
> **evidência empírica que justifica o experimento E3** (árbitro multimodal).

## 1. Contexto e motivação

O dataset da v1 (630 imagens sintéticas, 7 classes) era **cru** (defeitos por
manipulação de pixel simples) e **totalmente in-distribution** — o que expunha o
trabalho à crítica de *domain gap* sintético→real e de baixa quantidade/realismo.

Reconstruímos o gerador com três eixos simultâneos:

1. **Realismo** — cada defeito calibrado contra as fotos reais Zebra
   (`src/config/data/imgs_zebra/`).
2. **Bases reais** — os defeitos passam a ser aplicados também sobre **códigos de
   barras reais** (recortes do Roboflow; BarBeR a seguir), reduzindo o domain gap.
3. **Taxonomia expandida** — de 7 para **10 classes**, incluindo defeitos com
   referência real que faltavam: `smear`, `cutoff`, `registration_shift`.

## 2. Configuração experimental (piloto)

- **Gerador**: `src/config/generate_dataset.py` — 400 imgs/classe → **4.000 imagens**,
  10 classes, split 2800/600/600 (70/15/15), seed 42.
- **Bases reais**: 2.196 recortes do projeto Roboflow `o-xfs34/barcode-detection-tvdug`
  (export VOC, bbox recortada com margem de *quiet zone* de 8%), `--real-fraction 0.5`.
- **CNN**: MobileNetV3-Small (transfer learning, ImageNet), entrada 224px.
- **Treino**: 40 épocas, Adam, lr 5e-4, batch 32, **fine-tuning completo** (`--no-freeze`).

## 3. Resultados — progressão v1 → v2 → v3

| Métrica / classe | v1 | v2 | v3 |
|---|---|---|---|
| **Acurácia global (teste)** | **0,750** | **0,840** | **0,870** |
| Acurácia (validação) | 0,787 | 0,863 | 0,885 |
| no_defect | 0,633 | 0,350 | 0,750 |
| damaged_printhead_element | **0,083** | 0,783 | 0,683 |
| wrinkled_ribbon | 0,683 | 0,783 | 0,750 |
| burnt_spot | 1,000 | 1,000 | 0,983 |
| light_print | 1,000 | 0,983 | 1,000 |
| uneven_pressure | 0,933 | 0,933 | 0,900 |
| dirty_printhead | 0,517 | 0,900 | 0,983 |
| smear | 0,950 | 0,967 | 0,950 |
| cutoff | 0,850 | 0,800 | 0,800 |
| registration_shift | 0,850 | 0,900 | 0,900 |

**O que mudou em cada iteração:**

- **v1 → v2**: fortalecimento dos defeitos sutis para **sobreviverem ao downscale
  para 224px** — linhas de `damaged_printhead_element` mais grossas (2–5px) e
  posicionadas nas colunas de maior tinta; voids de `dirty_printhead` maiores e
  restritos a pixels de tinta; vinco de `wrinkled_ribbon` mais nítido/brilhante.
  Efeito: `damaged_printhead` 0,083 → 0,783; `dirty_printhead` 0,517 → 0,900;
  global 0,750 → 0,840. **Custo:** `no_defect` caiu (0,633 → 0,350).
- **v2 → v3**: `no_defect` passa a usar **apenas bases sintéticas garantidamente
  limpas** (`SYNTHETIC_ONLY_CLASSES`), pois um recorte real qualquer **não é
  garantidamente livre de defeito** e, usado como "no_defect", **mislabela** um
  código defeituoso como limpo. Efeito: `no_defect` 0,350 → 0,750; global
  0,840 → 0,870. **Custo:** `damaged_printhead` recua (0,783 → 0,683).

## 4. Achado central — a fronteira confundível justifica o E3

Matriz de confusão da classe `no_defect` (rótulo verdadeiro → predição):

| | v2 | v3 |
|---|---|---|
| → damaged_printhead_element | **40,0%** | 6,7% |
| → no_defect (correto) | 35,0% | **75,0%** |
| → wrinkled_ribbon | 18,3% | 16,7% |

O erro do par **`no_defect` ↔ `damaged_printhead_element`** **atravessa a fronteira
em direções opostas** conforme o balanço dos dados: em v2 o modelo super-diagnostica
imagens limpas como defeito (40% de `no_defect` → `damaged`); em v3, ao "limpar" a
classe de controle, ele passa a **perder** defeitos (16 amostras `damaged` reais
previstas como `no_defect`).

**Conclusão do piloto:** com **dados em pequena escala**, essa fronteira parecia
**irredutível para a CNN** — o erro não some, só se desloca conforme o balanço.
É o par para o qual o **árbitro visual multimodal do E3** foi projetado
(`ARBITER_PAIRS` em `settings.py`).

> ⚠️ **Esta conclusão é REVISADA pela seção 7.** O dataset definitivo (13.360
> imagens reais) mostra que **escalar dado real resolve o par** (erro cai de 40%
> para ~1,5%). A justificativa do E3 passa de "necessário" para "refinamento
> marginal sobre o resíduo". Não usar a matriz do piloto, isolada, como prova de
> que a CNN "não consegue".

## 5. Limitações desta bateria (a declarar no texto)

- É um **piloto** sobre bases reais do Roboflow; o dataset **definitivo** (e os
  números do artigo) será gerado após incorporar o **BarBeR** como fonte de bases
  reais — inclusive um subconjunto **verificado como limpo/decodificável** para
  servir de `no_defect`, eliminando o ruído de rótulo sem o artifício de teste
  sintético.
- Ao tornar `no_defect` sintético em v3, o **teste** dessa classe também ficou
  sintético (mais fácil): parte do ganho de `no_defect` é esse artefato, não só a
  correção do ruído de rótulo. A queda dos falsos-positivos (40% → 6,7%), porém, é
  sinal genuíno.
- Modelos-piloto (`classificador_defeitos_pilot{1,2,3}.pt`) e o dataset piloto
  **não são versionados** — são reproduzíveis pelo gerador com a mesma seed.

## 6. Próximos passos (definitivo)

1. Incorporar o BarBeR em `config/datasets/real_bases/<simbologia>/`; separar via
   `pyzbar` o subconjunto decodificável para bases limpas do `no_defect`.
2. Regerar (mesma seed) e treinar full → modelo **canônico**.
3. Re-executar **E1 / E-BASE / E-KFOLD** (taxonomia 10 classes) + **E4** (domain gap,
   sintético→real) + **E3** (árbitro no par confundível, agora com evidência).
4. Atualizar tabelas e Discussão do artigo com a progressão acima.

## 7. Resultado DEFINITIVO (13.360 imagens reais, modo exaustivo)

Dataset gerado com `generate_dataset.py --exhaustive`: **cada uma das 12.024 bases
reais** (Roboflow 2.196 + BarBeR 9.828 crops) vira um caso de defeito, distribuído
round-robin entre as 9 classes de defeito; `no_defect` (1.336) sai do pool
**verificado como decodificável** (`pyzbar`) do BarBeR. Total **13.360 imagens,
100% base real** (defeito sintético sobre textura real), balanceado 1.336/classe,
split 9.350/2.000/2.010. Treino: MobileNetV3-Small, 40 épocas, lr 5e-4, batch 32,
fine-tuning completo.

**Métricas (teste, in-distribution):** acurácia global **0,957** (val 0,951).

| Classe | v3 (piloto) | **definitivo** |
|---|---|---|
| no_defect | 0,750 | **0,881** |
| damaged_printhead_element | 0,683 | **0,950** |
| wrinkled_ribbon | 0,750 | 0,935 |
| burnt_spot | — | 1,000 |
| light_print | — | 0,995 |
| uneven_pressure | — | 0,990 |
| dirty_printhead | — | 0,975 |
| smear | — | 0,985 |
| cutoff | 0,800 | 0,891 |
| registration_shift | — | 0,965 |
| **Global** | **0,870** | **0,957** |

**A fronteira confundível se resolve com escala de dado real:**

| `no_defect` (real) previsto como | v2 | v3 | **definitivo** |
|---|---|---|---|
| → damaged_printhead_element | 40,0% | 6,7% | **1,5%** |
| → no_defect (correto) | 35,0% | 75,0% | **88,1%** |

E `damaged_printhead` → `no_defect` = **0,5%** (o modelo praticamente não perde mais
o defeito).

**Reenquadramento do E3 (honesto).** A hipótese do piloto — "a CNN não consegue
separar o par, logo o árbitro é necessário" — **não se sustenta** no definitivo: com
volume/variabilidade real, a CNN separa o par sozinha (~95%/88%). A contribuição
correta do E3 é **refinamento multimodal sobre o resíduo** de casos de baixa
confiança (o `no_defect` ainda é a classe mais fraca, 0,88, com erros pulverizados
no cluster de linhas finas: wrinkled 5%, cutoff 4%). O argumento forte do trabalho
passa a ser a **progressão empírica** (dado sintético pequeno → dado real em escala)
e a **redução medida** do par confundível, não uma necessidade categórica do árbitro.

**Ressalva central (não omitir no texto):** 0,957 é **in-distribution** (bases reais
+ defeito sintético, mesmo gerador). **Não** é evidência de desempenho em defeito
real — isso é o que o **E4** mede. O número alto não substitui o E4.
