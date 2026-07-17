# Laboratório 02 — Detecção de Pratos com Transformada de Hough

**UC de Visão Computacional**  
**Prof. Dr. Fábio Cappabianco**  
**Aluno:** Saymon Coppi

---

## 1. Objetivo

Implementar a Transformada de Hough para detecção de círculos em imagens de pratos de alimentos. O programa deve localizar automaticamente os pratos presentes nas 100 imagens fornecidas.

---

## 2. Implementação

O programa foi desenvolvido em **C++17** com **OpenCV 4.13.0**, compilado via CMake.

### Estrutura do Programa

O programa realiza os seguintes passos para cada imagem:

1. Leitura da imagem colorida (`cv::imread`)
2. Pré-processamento (detalhado na seção 3)
3. Detecção de círculos com `cv::HoughCircles` usando múltiplos conjuntos de parâmetros
4. Seleção do melhor círculo por função de pontuação
5. Desenho do círculo detectado sobre a imagem original
6. Salvamento em `output/`

### Seleção do Melhor Círculo

Todos os círculos candidatos de todos os conjuntos de parâmetros são coletados. Cada candidato recebe uma pontuação:

```
score = raio × centralidade
```

Onde `centralidade = 1 - 0.5 × (distância_ao_centro / distância_máxima)`, penalizando círculos com centro muito afastado do centro da imagem. Círculos cujo centro esteja dentro de 10% da borda da imagem são rejeitados como artefato.

### Raios Mínimo e Máximo

Os raios são definidos proporcionalmente ao menor lado da imagem, para acomodar os diferentes tamanhos presentes no dataset:

- `minRadius = menorLado / 5`
- `maxRadius = menorLado × 0.55`
- `minDist = menorLado / 3`

---

## 3. Pré-processamento

### 3.1 Pipeline Final (Eficaz)

| Etapa | Técnica | Efeito |
|---|---|---|
| 1 | Conversão BGR → Escala de Cinza | Elimina informação de cor irrelevante |
| 2 | CLAHE (clipLimit=2.0, tile 8×8) | Melhora contraste local sem saturar bordas |
| 3 | Filtro Gaussiano (kernel 9×9, σ=2.0) | Suaviza ruído antes do Hough |

### 3.2 Pré-processamentos Testados e Não Utilizados

- **Equalização global de histograma**: saturava regiões claras (pratos brancos), prejudicando a detecção da borda do prato. Não utilizado.
- **Filtro da Mediana**: preservou bem bordas mas foi mais lento que o Gaussiano sem melhora perceptível. Não utilizado.
- **Canny explícito antes do HoughCircles**: o `HOUGH_GRADIENT` já aplica Canny internamente; aplicá-lo antes resultou em detecções redundantes e mais falsos positivos.

---

## 4. Parâmetros Testados

O programa testa cinco conjuntos de parâmetros em cascata. Se um conjunto não encontra círculos (ou círculos válidos pelo critério de borda), tenta o próximo.

| Conjunto | `dp` | `param1` | `param2` | Descrição |
|---|---|---|---|---|
| A | 1.2 | 100 | 30 | Baseline — equilíbrio entre precisão e sensibilidade |
| B | 1.0 | 80 | 25 | Mais sensível — detecta bordas mais fracas |
| C | 1.5 | 120 | 45 | Mais restrito — reduz falsos positivos |
| D | 1.2 | 60 | 18 | Alta sensibilidade — fallback |
| E | 1.0 | 50 | 15 | Máxima sensibilidade — último recurso |

- **`dp`**: razão entre resolução da imagem e do acumulador. Valor maior = acumulador menor = mais rápido, menos preciso.
- **`param1`**: threshold superior do Canny interno. Valor maior = apenas bordas mais fortes.
- **`param2`**: threshold do acumulador. Valor menor = mais círculos detectados (mais falsos positivos).

### Melhores Parâmetros

O conjunto **A** (`dp=1.2, param1=100, param2=30`) foi responsável pela detecção em mais de 95% das imagens com boa detecção. A estratégia de múltiplos conjuntos em cascata garantiu que imagens com bordas de contraste baixo fossem detectadas pelos conjuntos D ou E.

---

## 5. Resultados

### 5.1 Tabela de Resultados

| Categoria | Quantidade |
|---|---|
| Detectado corretamente | 73 |
| Detectado parcialmente | 21 |
| Não detectado ou detectado incorretamente | 6 |
| **Total** | **100** |

---

### 5.2 Exemplos: Detectado Corretamente

Casos em que o círculo detectado coincide bem com a borda do prato principal.

**Imagem 5** — Tigela com padrão azul e limão:  
Centro (328, 230), raio 218. Círculo ajustado perfeitamente à borda externa da tigela.

**Imagem 26** — Tigela com padrão azul e biscoito:  
Centro (296, 250), raio 201. Antes da melhoria do scoring, o centro estava em (2, 73) — artefato de borda. Após a pontuação por centralidade, a detecção foi corrigida.

**Imagem 52** — Prato com salada verde:  
Centro (278, 238), raio 239. Círculo envolve o prato completamente.

**Imagem 82** — Prato de vidro transparente com carne:  
Centro (268, 277), raio 240. Destaque: prato de vidro sem borda opaca definida — ainda assim detectado com sucesso graças ao CLAHE.

**Imagem 64** — Prato descartável com arroz, feijão e carne:  
Centro (302, 222), raio 216. Detecção precisa mesmo com prato de material plástico opaco.

**Imagem 85** — Prato branco com ossos de carne:  
Centro (272, 242), raio 181. Prato menor que os demais; raio correto.

---

### 5.3 Exemplos: Detectado Parcialmente

Casos em que houve detecção mas com posição ou raio apenas parcialmente satisfatórios.

**Imagem 0** — Prato com carne e feijão (cortado na borda da foto):  
Centro (271, 70), raio 246 (máximo permitido). O prato está parcialmente fora do quadro; o algoritmo encontra apenas o arco visível e encaixa um círculo grande com centro deslocado para fora da imagem.

**Imagem 7** — Prato com tomates fatiados (pés do fotógrafo visíveis):  
Centro (286, 387), raio 246. O prato ocupa a metade superior da foto; o centro detectado está na metade inferior. O arco visível corresponde à borda inferior do prato.

**Imagem 31** — Xícara/pires com padrão floral (cortado no topo):  
Centro (260, 46), raio 238. Similar ao caso 7, mas com o corte na parte superior da imagem.

**Imagem 86** — Prato com arroz, feijão e frango empanado:  
Centro (434, 252), raio 243. O centro detectado está deslocado para a direita; o círculo captura apenas parte da borda do prato. Provavelmente causado por um objeto claro no canto direito que influenciou o acumulador.

**Imagem 99** — Prato octagonal:  
Centro (300, 296), raio 274. O prato não é circular — é octagonal. O HoughCircles tenta aproximar a forma com um círculo inscrito, resultando em ajuste parcial.

---

### 5.4 Exemplos: Não Detectado ou Detectado Incorretamente

**Imagem 77** — Prato branco com composição artística (bandeira brasileira + bola de futebol):  
Centro (148, 332), raio 246. O algoritmo detectou um arco no canto superior esquerdo em vez do grande prato branco que ocupa quase toda a imagem. A bola de futebol amarela e circular no topo do prato, junto com o prato ser maior que o `maxRadius` permitido (247 px para imagem 600×450), levou a uma detecção completamente errada.

**Imagens com prato muito maior que `maxRadius`**: alguns pratos preenchem mais de 55% da menor dimensão da imagem, excedendo o `maxRadius = menorLado × 0.55` imposto. Nesses casos o algoritmo busca o maior círculo dentro do limite e encaixa-o em alguma borda interna do prato.

---

## 6. Dificuldades Encontradas

### 6.1 Dataset com Tamanhos Variados

As 100 imagens não possuem tamanho uniforme: 91 são 600×450, mas há imagens 337×600 (retrato), 259×194 e 589×600. Os parâmetros `minRadius` e `maxRadius` foram definidos proporcionalmente ao menor lado de cada imagem para acomodar essa variação.

### 6.2 Pratos Parcialmente Fora do Quadro

Cerca de 15-20 imagens mostram o prato cortado na borda. O `HoughCircles` com `HOUGH_GRADIENT` busca círculos completos e tem dificuldade com arcos parciais — ele tende a encaixar círculos grandes com centro fora da imagem, que percorrem o arco visível. A função de pontuação por centralidade mitigou alguns desses casos, mas não todos.

### 6.3 Pratos Não Circulares

A imagem 99 possui um prato octagonal. A Transformada de Hough Circular é fundamentalmente inadequada para formas não circulares; a melhor detecção possível é uma aproximação circular da forma.

### 6.4 Confusão com Elementos Circulares no Prato

Alguns pratos contêm elementos muito circulares (rodelas de limão, bola de futebol decorativa, roda de alimento) que competem com o prato no acumulador de Hough. A função de scoring por centralidade e preferência pelo maior raio mitigou esses casos na maioria das imagens.

### 6.5 Seleção do Melhor Círculo

A primeira versão do código selecionava simplesmente o círculo de maior raio, o que levava a detecções equivocadas em bordas da imagem (o algoritmo encaixava círculos com centro fora do quadro e raio máximo). A solução foi a função de pontuação combinada (raio × centralidade com filtro de borda de 10%).

---

## 7. Conclusão

A Transformada de Hough com `HOUGH_GRADIENT` é eficaz para detectar pratos circulares em imagens de alimentos quando:

- O prato está completamente visível no quadro
- O prato é circular
- Não há outros elementos circulares de raio semelhante competindo no acumulador

Os melhores parâmetros foram `dp=1.2, param1=100, param2=30` com pré-processamento CLAHE + Gaussiano. A taxa de detecção correta foi de **73%**, com 21% de detecções parciais e 6% de falhas, totalizando 100 imagens avaliadas.

---

*Código-fonte: `hough_plates.cpp` | Imagens de saída: diretório `output/`*
