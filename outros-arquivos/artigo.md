# Reconhecimento de padrões de falhas em etiquetas de códigos de barras: um sistema de visão computacional com orquestração multiagente

> **Rascunho de conteúdo (Markdown).** Depois convertemos para o projeto abnTeX2 no Overleaf.
> Convenções deste rascunho:
> - Texto em **[colchetes]** = decisão sua ou dado a preencher.
> - Citações estão como `(Autor, Ano)` e mapeadas para as chaves do `referencias.bib` na seção *Referências*.
> - A Seção 6 é **modelo** (sem números inventados) até você rodar os experimentos.

---

## 1. Introdução

### 1.1 Contextualização

Códigos de barras são a espinha dorsal da identificação automática de itens em varejo, logística, saúde e manufatura. Uma etiqueta é lida dezenas de vezes ao longo da cadeia — na expedição, no transporte, no recebimento e no ponto de venda — e cada leitura pressupõe que a impressão preserve as proporções de barras e espaços dentro de tolerâncias estreitas. Quando a impressão degrada, o custo não é apenas uma releitura: há reprocessamento manual, atraso operacional, devolução de cargas e, em setores regulados, não conformidade.

Por essa criticidade, a qualidade de impressão é normatizada. A norma ISO/IEC 15416 define, para símbolos lineares (1D), um conjunto de parâmetros objetivos derivados do *perfil de refletância de varredura* — entre eles contraste do símbolo, modulação, decodificabilidade e defeitos — que são convertidos em notas de A a F (ISO/IEC 15416, 2016). Para símbolos bidimensionais (2D), a ISO/IEC 15415 cumpre papel análogo (ISO/IEC 15415, 2024), e a conformidade dos aparelhos verificadores é regida pela ISO/IEC 15426 (ISO/IEC 15426-1, 2006). Na prática industrial, essa avaliação é feita por *verificadores ópticos* dedicados, equipamentos calibrados e de custo elevado.

Paralelamente, no chão de fábrica, os defeitos de impressão têm origem física bem conhecida e documentada pelos fabricantes. No caso da Zebra Technologies — referência deste trabalho —, os guias das impressoras industriais da série ZT (ZT411/ZT421) e a base de conhecimento associam sintomas visuais a causas mecânicas concretas: nível de *darkness* (temperatura) incorreto, pressão desigual da cabeça de impressão, enrugamento ou rompimento do *ribbon*, cabeça de impressão suja ou com elemento queimado, rolete (*platen*) desgastado ou sujo, e incompatibilidade entre mídia e ribbon (Zebra Technologies, 2024). Ou seja, existe um corpo de conhecimento que liga **aparência do defeito → componente responsável → ação corretiva**.

### 1.2 Problema de pesquisa

Há uma lacuna entre esses dois mundos. Os verificadores certificados são caros, pouco portáteis e, sobretudo, **reportam uma nota, não a causa-raiz**: informam que o símbolo é grau "C" ou "D", mas não dizem ao operador *por que* — se é ribbon enrugado, pressão desigual ou cabeça queimada — nem *o que fazer*. Do outro lado, o conhecimento de causa-raiz existe, mas está disperso em manuais e depende da experiência de um técnico para ser aplicado.

Este trabalho investiga a seguinte questão de pesquisa:

> **É possível, a partir de uma imagem capturada por um dispositivo comum, identificar defeitos típicos de impressão de códigos de barras e sugerir sua causa provável, combinando visão computacional e um sistema multiagente orquestrado, com precisão suficiente para apoiar a decisão de um operador?**

**Escopo do diagnóstico (definido):** o sistema **não é um verificador certificado** e não substitui a medição conforme ISO/IEC 15416. Ele atua como **apoio à decisão**: (i) classifica defeitos físicos de impressão e (ii) estima *indicadores inspirados* nos parâmetros da norma (contraste, uniformidade), sempre rotulados como aproximação, nunca como grau oficial.

### 1.3 Objetivos

**Objetivo geral.** Desenvolver e avaliar um sistema, exposto por uma API única e consumido por um aplicativo Android e por uma interface web, capaz de detectar defeitos comuns de impressão em etiquetas de códigos de barras e sugerir a causa provável, empregando visão computacional e orquestração multiagente com o Agent Development Kit (ADK).

**Objetivos específicos.**
1. Caracterizar os defeitos de impressão mais frequentes em impressoras térmicas industriais (referência: Zebra série ZT) e mapeá-los para suas causas físicas.
2. Construir/organizar um conjunto de imagens rotuladas contemplando as classes de defeito e a classe "sem defeito".
3. Projetar uma arquitetura multiagente que decomponha a tarefa em leitura/decodificação, estimativa de indicadores de qualidade, detecção de defeitos físicos e diagnóstico de causa-raiz fundamentado na documentação do fabricante.
4. Implementar a solução e disponibilizá-la por uma API consumível por aplicativo e web.
5. Avaliar o desempenho do sistema e verificar se a decomposição multiagente traz ganho mensurável frente a uma abordagem monolítica.

**Escopo de símbolos (definido):** o trabalho contempla **1D** (Code 128, Code 39, EAN-13/EAN-8, Interleaved 2 of 5, Pharmacode) e **2D** (Data Matrix, QR Code). A ênfase de qualidade recai sobre a ISO/IEC 15416 (1D) e a ISO/IEC 15415 (2D). *Observação sobre dados (ver Seção 4.2): o conjunto de imagens reais atualmente disponível cobre apenas 1D; as amostras 2D e as amostras de defeito de impressão serão obtidas por geração sintética controlada.*

### 1.4 Contribuições do trabalho

As principais contribuições são:
1. Um **mapeamento sistematizado** de defeitos visuais de impressão para causas físicas e ações corretivas, consolidado a partir da documentação técnica da Zebra (guia da ZT411/ZT421, manual de manutenção e base de conhecimento).
2. Uma **arquitetura multiagente** (ADK) que separa leitura, estimativa de indicadores, detecção de defeitos e diagnóstico de causa-raiz, servida por uma **API única** para aplicativo Android e web.
3. Um **agente de diagnóstico fundamentado** (com recuperação sobre a documentação do fabricante) que vai além da nota e sugere causa provável e correção — diferencial frente a verificadores tradicionais.
4. Uma **avaliação comparativa** entre a arquitetura multiagente e um baseline monolítico, quantificando o benefício da decomposição.
5. Um **conjunto de imagens híbrido**: imagens reais de códigos de barras capturados em condições variadas (52 amostras 1D organizadas por simbologia) combinadas a um **conjunto de defeitos de impressão gerados sinteticamente** de forma controlada e reprodutível, cobrindo as classes derivadas da documentação Zebra.

### 1.5 Organização do artigo

A Seção 2 apresenta a fundamentação teórica. A Seção 3 revisa trabalhos relacionados e delimita a lacuna. A Seção 4 descreve a metodologia. A Seção 5 detalha a solução proposta. A Seção 6 apresenta e discute os resultados. A Seção 7 conclui e aponta trabalhos futuros.

---

## 2. Fundamentação Teórica

### 2.1 Códigos de barras e simbologias

Um código de barras codifica dados na largura e no arranjo de elementos claros e escuros. Nos símbolos **lineares (1D)**, como Code 128, EAN-13 e GS1-128, a informação está na sequência horizontal de barras e espaços de larguras variáveis; a menor largura nominal é chamada **dimensão X** (ou módulo) e serve de referência para todas as tolerâncias. O símbolo é delimitado por **zonas de silêncio** (áreas claras) obrigatórias antes e depois das barras, sem as quais o leitor não isola o código. Nos símbolos **bidimensionais (2D)**, como Data Matrix e QR Code, os dados se distribuem em uma matriz de células, permitindo maior densidade e correção de erros.

A leitura pressupõe que as proporções impressas correspondam às nominais. Pequenos desvios sistemáticos — barras mais largas (ganho) ou mais estreitas (perda) que o previsto — comprometem a decodificação. É exatamente esse tipo de desvio que a impressão térmica pode introduzir.

### 2.2 Qualidade de impressão e verificação (ISO/IEC 15416 e 15415)

A avaliação normativa parte do **perfil de refletância de varredura** (*scan reflectance profile*, SRP): uma linha de varredura atravessa o símbolo medindo a refletância ao longo do percurso, produzindo uma curva de picos (espaços claros) e vales (barras escuras). Todos os parâmetros de nota derivam desse perfil (ISO/IEC 15416, 2016).

Para símbolos lineares, a ISO/IEC 15416 avalia nove atributos por varredura, entre os quais se destacam:

| Parâmetro | O que mede | Relação com o defeito de impressão |
|---|---|---|
| Contraste do símbolo (SC) | Diferença entre a maior e a menor refletância | Impressão clara / mídia-ribbon incompatível reduzem o contraste |
| Contraste de borda (EC) | Contraste entre barra e espaço adjacentes | Bordas "borradas" por pressão/velocidade inadequadas |
| Modulação (MOD) | Uniformidade dos elementos ao longo do símbolo | Pressão desigual e sujeira geram variação |
| Defeitos (ERN) | Maior não uniformidade de refletância de um elemento | Manchas, voids e pontos queimados |
| Decodificabilidade | Margem do símbolo frente ao algoritmo de referência | Ganho/perda de largura das barras |

A nota de uma varredura é a **menor** entre os parâmetros; a nota do símbolo é a **média de dez varreduras** distribuídas ao longo da altura. Para 2D, a ISO/IEC 15415 cumpre papel equivalente com parâmetros adaptados à matriz (ISO/IEC 15415, 2024), e a marcação direta de peça (DPM) é tratada pela ISO/IEC 29158 (ISO/IEC 29158, 2020).

**Ponto metodológico importante.** A verificação *conformante* exige condições ópticas controladas — fonte de luz definida, abertura de medição, geometria e calibração de refletância — providas por verificadores certificados (ISO/IEC 15426-1, 2006). Uma imagem de câmera comum não reproduz essas condições. Por isso, neste trabalho os parâmetros da norma são usados como **referencial conceitual e como indicadores aproximados**, não como grau oficial — o que delimita honestamente o escopo (ver Seção 1.2).

### 2.3 Defeitos típicos de impressão térmica e suas causas

Impressoras térmicas de transferência (como a Zebra ZT411/ZT421) formam a imagem aquecendo seletivamente uma cabeça de impressão que transfere tinta do *ribbon* para a mídia, prensada pelo **rolete (platen)**. Cada componente falha de um modo com assinatura visual característica. A partir do guia do usuário da ZT411/ZT421, do procedimento de manutenção e da base de conhecimento da Zebra (Zebra Technologies, 2024), consolidamos o mapeamento abaixo — que é, em si, uma das contribuições do trabalho (Seção 1.4).

| Defeito (aparência) | Causa provável | Ação corretiva típica |
|---|---|---|
| Código não escaneia; imagem "suja" | *Darkness* alto demais ou pressão da cabeça incorreta | Reduzir o *darkness* ao menor valor com boa qualidade; reduzir velocidade; ajustar pressão/toggle |
| Impressão clara (faded) em toda a etiqueta | *Darkness* baixo, mídia/ribbon incompatível ou de alta velocidade | Elevar *darkness* moderadamente; trocar para combinação mídia-ribbon adequada |
| Impressão clara/escura em **um lado** da etiqueta | Pressão **desigual** da cabeça | Ajustar a pressão da cabeça (toggles) |
| Linhas cinza finas e angulares em etiquetas em branco | *Ribbon* enrugado | Corrigir tensão/alinhamento do ribbon |
| Trilhas longas de impressão faltando em várias etiquetas | **Elemento da cabeça danificado** (linhas brancas verticais) | Acionar assistência técnica (troca de cabeça) |
| Voids no código/gráficos; qualidade inconsistente | Cabeça de impressão **suja** | Limpar cabeça e rolete com álcool isopropílico 99,7% |
| Manchas (smudge) | Mídia/ribbon inadequados para alta velocidade | Trocar por insumos recomendados |
| Perda de registro / deslocamento vertical da imagem | Rolete sujo, mídia mal carregada, sensor descalibrado | Limpar rolete; recarregar mídia; calibrar sensores |
| *Ghosting* (imagem repetida) | **[confirmar via KB]** desgaste/aderência no ribbon-rolete | **[preencher]** |

A manutenção preventiva atua sobre as causas de origem: a limpeza periódica da **cabeça** e do **rolete** com álcool isopropílico 99,7% (ou kit de manutenção Zebra) é indicada quando surgem voids, e a documentação alerta que *darkness* excessivo desgasta a cabeça prematuramente e pode "queimar" o ribbon (Zebra Technologies, 2024). Esse conhecimento é o que alimenta o agente de diagnóstico proposto na Seção 5.

### 2.4 Processamento de imagens e visão computacional para inspeção

O reconhecimento dos defeitos acima é um problema de **inspeção visual automatizada**. As etapas clássicas envolvem:

- **Pré-processamento** — conversão de cor, correção de iluminação e realce de contraste para atenuar variações de captura (Gonzalez; Woods, 2018).
- **Localização/segmentação do símbolo** — isolar a região do código na etiqueta, condição para medir refletância e detectar defeitos localizados (Szeliski, 2022).
- **Detecção de objetos/defeitos** — localizar e classificar regiões defeituosas; abordagens supervisionadas de um estágio (por exemplo, da família YOLO) são amplamente usadas em inspeção industrial.
- **Classificação por redes convolucionais (CNN)** — atribuir a classe de defeito a partir de características aprendidas, dispensando extração manual de atributos.
- **Detecção de anomalias** — quando amostras de defeito real são escassas, métodos não supervisionados aprendem o "normal" e sinalizam desvios, contornando o desbalanceamento de dados.

A literatura recente de inspeção industrial converge nesses pilares e destaca um desafio recorrente diretamente relevante a este trabalho: a **escassez de imagens de defeito real**, que motiva aumento de dados e abordagens semi/não supervisionadas (survey Frontiers, 2025; survey arXiv, 2022).

### 2.5 Sistemas multiagentes e o Agent Development Kit (ADK)

Um **sistema multiagente** é um conjunto de agentes autônomos que colaboram para uma meta comum, cada um responsável por uma subtarefa. O **Agent Development Kit (ADK)**, apresentado pelo Google no Cloud NEXT 2025, é um framework open-source para construir e orquestrar esses sistemas (Google, 2025). Ele organiza os agentes em três tipos:

- **Agentes LLM** — o "raciocínio", que interpreta entradas e decide ações;
- **Agentes de workflow** — orquestradores de fluxo (sequencial, paralelo, em laço);
- **Agentes customizados** — especialistas que encapsulam lógica ou modelos próprios (por exemplo, um modelo de visão).

Os agentes se organizam em uma **hierarquia** e se comunicam por **estado compartilhado, delegação e invocação explícita** (Google, 2025). A justificativa central do paradigma — e o argumento que este trabalho pretende testar empiricamente — é que decompor um problema em agentes especializados tende a ser **mais confiável, modular e manutenível** do que um único modelo/prompt monolítico, porque cada agente resolve uma tarefa mais simples e bem delimitada.

---

## 3. Trabalhos Relacionados

### 3.1 Verificação normativa e diagnóstico de defeitos

A base da verificação de qualidade são as normas ISO/IEC 15416 e 15415, implementadas por verificadores comerciais que reportam notas A–F (ISO/IEC 15416, 2016; ISO/IEC 15415, 2024). Há também soluções que inferem falhas do mecanismo de impressão a partir da própria leitura — por exemplo, detectando linhas não impressas para gerar um relatório de manutenção do cabeçote e alertar antes da falha total (patente US 9.826.106, 2017). **Limitação comum:** dependem de hardware dedicado e/ou entregam a nota/alerta, sem um diagnóstico de causa-raiz acionável e contextualizado pela documentação do fabricante.

### 3.2 Inspeção visual de defeitos com aprendizado profundo

A inspeção industrial baseada em aprendizado profundo é sistematizada em levantamentos recentes que cobrem CNNs, detecção de objetos e detecção de anomalias, com ênfase no problema de dados escassos (survey Frontiers, 2025; survey arXiv, 2022). Aplicações diretas ao domínio de impressão incluem a detecção de defeitos em tecidos estampados com CNN (fabric CNN, 2021) e a detecção/localização de anomalias em manufatura aditiva por transferência de aprendizado (FFF, 2024). **Limitação comum:** focam a classificação/localização do defeito visual, sem ligá-lo à causa física do processo nem a uma ação corretiva.

### 3.3 Sistemas multiagentes aplicados a tarefas de visão

A orquestração multiagente com ADK e frameworks correlatos vem sendo aplicada a tarefas complexas que se beneficiam de decomposição, tratando agentes especializados como ferramentas de um agente raiz (Google, 2025). **Lacuna observada:** a combinação de orquestração multiagente com inspeção de **qualidade de impressão de códigos de barras** — em especial acoplando detecção visual a diagnóstico fundamentado em documentação técnica — é pouco explorada.

### 3.4 Lacuna que este trabalho preenche

Reunindo os três eixos: os verificadores dão nota mas não causa; os métodos de visão detectam o defeito mas não a causa nem a correção; e a orquestração multiagente é madura porém raramente aplicada a este domínio. Este trabalho se posiciona nessa interseção, propondo um sistema de **baixo custo, servido por API**, que combina estimativa de indicadores de qualidade, detecção visual de defeitos físicos e **diagnóstico de causa-raiz fundamentado na documentação da Zebra**, orquestrados por agentes especializados.

> **Sugestão:** fechar a seção com uma tabela comparativa (trabalho × recursos: nota ISO / defeito físico / causa-raiz / sem hardware dedicado). Já deixei o molde no `.tex` da Seção 3.

---

## 4. Metodologia

### 4.1 Tipo de pesquisa

Pesquisa de natureza **aplicada**, abordagem **quantitativa** e objetivo **exploratório-experimental**: constrói-se um artefato (o sistema) e mede-se seu desempenho em condições controladas, com procedimento experimental.

### 4.2 Conjunto de dados

O problema tem duas naturezas distintas — a **legibilidade da captura** (a imagem do código está boa o suficiente para ler?) e o **defeito de impressão** (que falha do processo produziu a marca?) — e cada uma exige um tipo de dado. Por isso, adota-se uma estratégia de **duas trilhas**.

**Trilha A — imagens reais de captura (base disponível).** Conjunto de 52 imagens reais de códigos de barras fotografados em produtos e embalagens, em tons de cinza, sob ângulo, reflexo, curvatura e fundos variados, já organizadas por simbologia:

| Simbologia | Nº de imagens |
|---|---|
| EAN-13 | 19 |
| Code39 | 6 |
| Code128 | 5 |
| EAN-8 | 5 |
| Interleaved 2 of 5 | 5 |
| EAN-13 (add-on 2) | 4 |
| EAN-13 (add-on 5) | 4 |
| Pharmacode | 4 |
| **Total** | **52** |

Esse conjunto é usado para treinar/avaliar o **agente de leitura/decodificação** (localização e identificação da simbologia — os rótulos de simbologia já existem) e o **agente de indicadores de legibilidade** (contraste, nitidez, inclinação). Como são todas 1D, as amostras 2D são complementadas na Trilha B.

**Trilha B — defeitos de impressão sintéticos (gerados).** Para treinar o **agente de defeitos físicos** não há um conjunto público rotulado de defeitos de impressão térmica, e as fotos da base de conhecimento da Zebra são material protegido por direitos autorais (ver nota adiante). Adota-se, então, **geração sintética controlada**: a partir de códigos limpos (1D e 2D), aplicam-se transformações que reproduzem a assinatura visual de cada defeito descrito na documentação Zebra (Zebra Technologies, 2024):

| Classe de defeito | Transformação sintética | Sintoma reproduzido |
|---|---|---|
| Cabeça queimada (elemento danificado) | Linhas brancas verticais contínuas | Trilhas longas de impressão faltando |
| Ribbon enrugado | Faixas claras finas e diagonais | Linhas cinza angulares |
| Ponto queimado / darkness alto | Manchas escuras localizadas | Excesso de temperatura |
| Impressão clara (darkness baixo) | Redução de contraste global | Faded / mídia-ribbon incompatível |
| Pressão desigual | Borrão direcional (gradiente em um lado) | Densidade não uniforme |
| Cabeça suja (voids) | Falhas brancas pontuais nas barras | Voids no código |
| Sem defeito | (código limpo) | Classe de controle |

Essa abordagem é **reprodutível, balanceável e livre de restrições autorais**, e é prática consolidada na literatura de inspeção quando amostras reais são escassas (survey Frontiers, 2025; survey arXiv, 2022). Um gerador de prova de conceito já foi implementado e valida a geração das seis classes acima (ver `synth_defects.py` e a figura de demonstração).

**Divisão e aumento de dados.** Cada trilha é dividida em treino/validação/teste (sugerido 70/15/15), estratificando por classe. Sobre a Trilha A aplica-se aumento de dados clássico (rotação, variação de brilho/contraste, recortes) para ampliar a variabilidade de captura. Os parâmetros dos defeitos sintéticos (intensidade, quantidade, posição) são amostrados aleatoriamente em faixas definidas, para evitar que o modelo aprenda um padrão fixo.

> **Nota de direitos autorais (importante).** As fotos de defeitos da Knowledge Base da Zebra são protegidas. Recomenda-se usá-las, no máximo, como **poucas figuras ilustrativas devidamente citadas** na Fundamentação — nunca como base de treinamento redistribuível. O treinamento deve se apoiar nos dados sintéticos e nas imagens reais próprias.

> **[A confirmar com você]** (i) a taxonomia final de classes de defeito (a tabela acima é a proposta); (ii) se você pretende também **capturar imagens reais próprias** de etiquetas impressas com defeito (mesmo poucas) para um teste de generalização "sintético → real", o que fortaleceria muito a avaliação.

### 4.3 Ferramentas utilizadas

- **Visão computacional:** Python, OpenCV e **PyTorch**. Justificativa: PyTorch é hoje o framework predominante na comunidade acadêmica e científica (maior presença em publicações e reprodutibilidade de artigos), o que favorece a comparação com trabalhos correlatos. Para atender a **máquinas modestas**, adota-se transferência de aprendizado com um backbone leve (**MobileNetV3-Small** ou **EfficientNet-B0**), que treina bem em GPU de entrada ou mesmo CPU e tem baixa pegada de memória. Como a inferência é servida pela API (lado servidor), o dispositivo do usuário não precisa executar o modelo; se futuramente for desejável inferência no aparelho, o modelo pode ser exportado para ONNX/TFLite ou ExecuTorch.
- **Decodificação de código de barras:** `pyzbar` (ZBar) e/ou `ZXing` para leitura/validação e verificação de legibilidade.
- **Orquestração multiagente:** Agent Development Kit (ADK) (Google, 2025), com **Gemini** como modelo LLM dos agentes de raciocínio (leitura contextual e diagnóstico), aproveitando a integração nativa do ADK com o ecossistema Google.
- **Entrega:** API única (**[FastAPI recomendado]**) consumida pelo aplicativo Android e pela interface web.
- **Escrita e gestão bibliográfica:** LaTeX (abnTeX2/Overleaf) e Zotero.

### 4.4 Ambiente experimental

**[Preencher]** hardware (CPU/GPU e memória), versões de bibliotecas, dispositivo de captura e condições de iluminação/distância padronizadas. *Observação:* como o contraste medido depende fortemente da captura, padronizar iluminação e distância é parte do rigor experimental.

### 4.5 Métricas de avaliação

- **Classificação de defeitos:** acurácia, precisão, revocação e F1 por classe, além da matriz de confusão.
- **Detecção/localização (se houver):** mAP e IoU.
- **Indicadores de qualidade:** concordância entre o indicador estimado e **[a referência disponível — verificador, se houver, ou rótulo especialista]**.
- **Benefício do multiagente:** comparação das métricas acima entre a arquitetura multiagente e o baseline monolítico (ver Seção 6.3), além de latência e interpretabilidade do laudo.

---

## 5. Proposta da Solução

### 5.1 Arquitetura da solução

A solução adota o padrão **hierárquico** do ADK (Google, 2025), no qual um agente raiz coordena agentes especializados. A tarefa "avaliar uma etiqueta" é decomposta em quatro análises especializadas e uma etapa de síntese, explorando dois recursos de orquestração do ADK: **execução paralela** para as análises independentes e **execução sequencial** para as etapas que dependem das anteriores.

O sistema é composto por:

1. **Agente de leitura/decodificação** — localiza o símbolo, identifica a simbologia e tenta decodificar; retorna legível/ilegível e o conteúdo. Determina se o defeito já impede a leitura.
2. **Agente de indicadores de qualidade** — sobre a região segmentada, estima indicadores inspirados na ISO/IEC 15416 (contraste, uniformidade), sempre como aproximação (Seção 2.2).
3. **Agente de defeitos físicos** — classifica o defeito de impressão (as sete classes da Seção 4.2) usando a CNN treinada, exposta ao ADK como ferramenta.
4. **Agente de diagnóstico** — agente LLM (Gemini) que, com os resultados anteriores e uma ferramenta de recuperação sobre a documentação Zebra (RAG), infere a **causa provável** e a **ação corretiva**.
5. **Agente de laudo** — consolida tudo em um JSON estruturado devolvido pela API.

Os agentes 1–3 são **independentes** e rodam em paralelo (`ParallelAgent`); o agente 4 depende das saídas dos três e o agente 5 depende do 4, formando uma cadeia (`SequentialAgent`). A comunicação entre agentes usa o **estado compartilhado** da sessão: cada agente grava seu resultado em uma chave (`output_key`) e os seguintes leem essas chaves.

*(Inserir aqui a Figura da arquitetura — a árvore de agentes.)*

### 5.2 Fluxograma do processamento

Fluxo ponta a ponta: **captura no app/web → `POST /analisar` na API → pré-processamento e segmentação → `ParallelAgent` executa leitura, indicadores e defeito simultaneamente → `agente_diagnostico` consome as três saídas e consulta a documentação Zebra → `agente_laudo` agrega em JSON → resposta única → renderização no app/web.**

*(Inserir aqui o fluxograma destacando o bloco paralelo e a cadeia sequencial.)*

### 5.3 Algoritmos empregados

- **Segmentação do símbolo:** localização da região do código e das zonas de silêncio (limiarização adaptativa + operações morfológicas, ou um detector leve treinado).
- **Estimativa de indicadores:** a partir da imagem em tons de cinza, extração de perfis de refletância aproximados e cálculo de contraste e de medidas de uniformidade por elemento — apresentados como indicadores, não como grau ISO oficial.
- **Classificação de defeitos:** CNN com backbone leve (**MobileNetV3-Small** ou **EfficientNet-B0**) e transferência de aprendizado, treinada no conjunto sintético da Seção 4.2 e testada na generalização para imagens reais (Seção 6.5).
- **Diagnóstico:** recuperação (RAG) sobre a base de conhecimento estruturada (Seção 2.3) e raciocínio do agente LLM para ordenar as causas prováveis.

### 5.4 Detalhes da implementação

Cada especialista é definido como um agente do ADK; os modelos e rotinas de visão computacional são expostos como **ferramentas** (funções Python) que o ADK encapsula automaticamente. O trecho a seguir é uma implementação de referência (a API do ADK evolui — consultar `adk.dev`):

```python
# agentes.py — implementação de referência (Google ADK + Gemini)
from google.adk.agents import LlmAgent, ParallelAgent, SequentialAgent

MODEL = "gemini-2.5-flash"

# ---- Ferramentas: rotinas de visão computacional (locais) ----
def decodificar_codigo(caminho_imagem: str) -> dict:
    """Localiza e decodifica o codigo. Retorna simbologia, conteudo e se e legivel."""
    from leitura import decodificar          # usa pyzbar/ZXing
    return decodificar(caminho_imagem)        # {"legivel": bool, "simbologia": str, "conteudo": str}

def estimar_indicadores(caminho_imagem: str) -> dict:
    """Estima indicadores aproximados inspirados na ISO/IEC 15416 (nao e grau oficial)."""
    from qualidade import indicadores
    return indicadores(caminho_imagem)        # {"contraste": float, "uniformidade": float}

def classificar_defeito(caminho_imagem: str) -> dict:
    """Classifica o defeito de impressao com a CNN treinada (7 classes)."""
    from modelo import prever                  # carrega o checkpoint MobileNetV3/EfficientNet
    return prever(caminho_imagem)             # {"classe": str, "confianca": float}

def buscar_documentacao_zebra(sintomas: str) -> str:
    """Recupera trechos relevantes da base de conhecimento estruturada (RAG)."""
    from kb import buscar
    return buscar(sintomas)

# ---- Agentes especialistas (analises independentes -> paralelo) ----
agente_leitura = LlmAgent(
    name="leitura", model=MODEL, tools=[decodificar_codigo],
    instruction="Chame decodificar_codigo com a imagem e reporte se o codigo e legivel.",
    output_key="leitura",
)
agente_indicadores = LlmAgent(
    name="indicadores", model=MODEL, tools=[estimar_indicadores],
    instruction="Chame estimar_indicadores e reporte contraste e uniformidade.",
    output_key="indicadores",
)
agente_defeito = LlmAgent(
    name="defeito", model=MODEL, tools=[classificar_defeito],
    instruction="Chame classificar_defeito e reporte a classe e a confianca.",
    output_key="defeito",
)
analise_paralela = ParallelAgent(
    name="analise_paralela",
    sub_agents=[agente_leitura, agente_indicadores, agente_defeito],
)

# ---- Diagnostico (depende das analises) ----
agente_diagnostico = LlmAgent(
    name="diagnostico", model=MODEL, tools=[buscar_documentacao_zebra],
    instruction=(
        "Dado o defeito detectado ({defeito}), a legibilidade ({leitura}) e os "
        "indicadores ({indicadores}), use buscar_documentacao_zebra para fundamentar "
        "e proponha a CAUSA PROVAVEL e a ACAO CORRETIVA, citando o trecho de origem."
    ),
    output_key="diagnostico",
)

# ---- Laudo final (JSON estruturado) ----
agente_laudo = LlmAgent(
    name="laudo", model=MODEL,
    instruction=(
        "Consolide {leitura}, {indicadores}, {defeito} e {diagnostico} em um JSON com as "
        "chaves: legivel, simbologia, indicadores, defeito, causa_provavel, "
        "correcao_sugerida, confianca_geral. Responda SOMENTE o JSON."
    ),
    output_key="laudo",
)

# ---- Orquestrador raiz: paralelo -> diagnostico -> laudo ----
root_agent = SequentialAgent(
    name="inspetor_etiqueta",
    sub_agents=[analise_paralela, agente_diagnostico, agente_laudo],
)
```

A API expõe um **endpoint único** que executa esse grafo e devolve o laudo — a mesma porta atende o aplicativo Android e a interface web:

```python
# api.py — FastAPI (esboço)
from fastapi import FastAPI, UploadFile
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from agentes import root_agent

app = FastAPI()
runner = Runner(agent=root_agent, app_name="inspetor",
                session_service=InMemorySessionService())

@app.post("/analisar")
async def analisar(imagem: UploadFile):
    caminho = await salvar_temp(imagem)          # persiste e pre-processa
    laudo = await executar(runner, caminho)       # roda o grafo de agentes
    return laudo                                   # JSON unico para app e web
```

**Esquema do laudo (resposta da API):**

```json
{
  "legivel": true,
  "simbologia": "code128",
  "indicadores": { "contraste": 0.82, "uniformidade": 0.74 },
  "defeito": { "classe": "ribbon_enrugado", "confianca": 0.91 },
  "causa_provavel": "Tensao/alinhamento do ribbon",
  "correcao_sugerida": "Ajustar a tensao do ribbon; verificar o percurso",
  "confianca_geral": 0.88
}
```

---

## 6. Resultados e Discussão

> **Modelo — a preencher com os seus experimentos. Não contém números fabricados.**

### 6.1 Configuração dos experimentos

Descrever: (E1) classificação de defeitos; (E2) concordância dos indicadores estimados com a referência; (E3) **multiagente vs. baseline monolítico**. Informar número de execuções, sementes e protocolo de divisão dos dados.

### 6.2 Resultados quantitativos

*(Tabela de métricas por classe — precisão, revocação, F1, N — e matriz de confusão. Gráficos de desempenho.)*

### 6.3 Multiagente vs. baseline monolítico

Esta é a comparação que **transforma "usei ADK" em contribuição avaliável**. Reportar as mesmas métricas para a arquitetura decomposta e para uma abordagem única (um só modelo/prompt fazendo tudo), discutindo confiabilidade, acerto por classe, interpretabilidade do laudo e latência.

### 6.4 Análise e discussão

Interpretar acertos e erros, discutir as confusões mais frequentes entre classes e comparar com os trabalhos da Seção 3.

### 6.5 Limitações

Ser explícito: o treino de defeitos apoia-se em **dados sintéticos**, havendo risco de *domain gap* frente a defeitos reais — daí a importância de um conjunto de teste com amostras reais, ainda que pequeno; tamanho e representatividade do dataset de captura (52 imagens, apenas 1D); dependência das condições de captura; o sistema **não é verificador certificado** (Seção 2.2); generalização para outras impressoras/simbologias; latência acumulada dos agentes.

---

## 7. Conclusão

*(Redação provisória — revisar após os resultados.)*

Este trabalho propôs um sistema de detecção de defeitos de impressão em etiquetas de códigos de barras que combina visão computacional e orquestração multiagente (ADK), servido por uma API única para aplicativo e web, e que vai além da nota tradicional ao sugerir a **causa provável** do defeito com base na documentação técnica do fabricante. **[Sintetizar aqui a resposta à questão de pesquisa da Seção 1.2, à luz dos resultados obtidos.]**

**Principais contribuições entregues:** **[retomar da Seção 1.4 as que se confirmaram]**.

**Trabalhos futuros:** ampliar o conjunto de dados com defeitos reais; estender a símbolos 2D (Data Matrix/QR) via ISO/IEC 15415; aproximar os indicadores estimados de um verificador certificado por calibração; otimizar a latência da orquestração; e realizar avaliação em ambiente de produção.

---

## Referências (mapeamento para o `referencias.bib`)

- (ISO/IEC 15416, 2016) → `iso15416`
- (ISO/IEC 15415, 2024) → `iso15415`
- (ISO/IEC 29158, 2020) → `iso29158`
- (ISO/IEC 15426-1, 2006) → `iso15426`
- (Zebra Technologies, 2024) → `zebra_printquality` — **atualizar com título/nº exatos dos docs ZT411/ZT421 (guia do usuário, manual de manutenção) e da base de conhecimento**
- (Google, 2025) → `google_adk_blog`, `adk_docs`
- (survey Frontiers, 2025) → `frontiers2025anomaly`
- (survey arXiv, 2022) → `survey2022unsupervised`
- (fabric CNN, 2021) → `fabric2021cnn`
- (FFF, 2024) → `fff2024thermal`
- (patente US 9.826.106, 2017) → `patent9826106`
- (Gonzalez; Woods, 2018) → `gonzalez2018`
- (Szeliski, 2022) → `szeliski2022`
