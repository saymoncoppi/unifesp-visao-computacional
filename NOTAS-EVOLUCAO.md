# Notas de evolução do projeto

Documento de trabalho para retomar melhorias no artigo e na aplicação. Reúne os
resultados experimentais já obtidos, as decisões tomadas e os pontos em aberto.

_Última atualização: 2026-07-16._

---

## Rigor experimental (rodado de verdade)

Números reais e reprodutíveis, gerados por [`src/experimentos.py`](src/experimentos.py)
(split fixo 434/91/105, 40 épocas, Adam lr 5e-4, fine-tuning completo, sementes fixas).

### Comparação de arquiteturas (teste fixo, protocolo idêntico)

| Modelo | Acurácia | Macro-F1 | Params | Latência |
|---|---|---|---|---|
| **MobileNetV3-Small (nosso)** | 0,84 | 0,84 | 1,5M | 4,5 ms |
| ResNet18 | 0,79 | 0,80 | 11,2M | 17,8 ms |
| EfficientNet-B0 | 0,90 | 0,89 | 4,0M | 16,5 ms |

- **McNemar (significância estatística):** nenhuma diferença é significativa a 5% —
  MobileNetV3-Small vs. EfficientNet-B0 (b=4, c=10, p=0,18) e vs. ResNet18 (b=10,
  c=5, p=0,30). Ou seja, no conjunto de teste disponível **não há evidência** de que
  o EfficientNet-B0 seja superior; somado à eficiência muito maior, isso sustenta a
  escolha do MobileNetV3-Small para o cenário de baixo custo.
- **Validação cruzada (5 dobras estratificadas)** do MobileNetV3-Small: acurácia
  0,82 ± 0,01 e Macro-F1 0,82 ± 0,02 → desempenho estável, pouco sensível à partição.
- **Ponto fraco:** confusão mútua entre `sem_defeito` e `cabeca_queimada` (F1 ≈ 0,56);
  as zonas claras entre barras imitam as linhas brancas verticais do dano na cabeça.

> Essa tabela de comparação é candidata a entrar no artigo (já está na §6.3 da versão
> atual, mas vale destacá-la / reusá-la em apresentações).

---

## Decisões honestas tomadas (revisar no futuro)

1. **Multiagente × monolítico: a decomposição HABILITA arbitragem visual multimodal.**
   Tese nova (não é mais "mesma CNN ⇒ métricas idênticas"): o caminho ADK agora
   **arbitra visualmente** — o agente de diagnóstico é LLM multimodal (Gemini vê a
   imagem) e pode **corrigir a classe da CNN** no par confundível
   `sem_defeito` ↔ `cabeca_queimada` (F1 ≈ 0,56), recurso que o pipeline direto
   (monolítico/baseline) não tem. Isso vira o experimento **E3**: CNN-pura ×
   pós-arbitragem, McNemar restrito às 30 etiquetas desse par. A matriz de confusão do
   artigo (`tab-confusao`) é **CNN-pura**; o laudo final do caminho ADK é
   **pós-arbitragem**. Os números de E3 dependem da chave `GOOGLE_API_KEY` (Gemini),
   ausente no ambiente → ficam como **placeholder** no artigo (§6.4); protocolo já
   definido e executável. Os três eixos qualitativos (modularidade,
   interpretabilidade, robustez) seguem valendo.
2. **k-fold só no nosso modelo.** Os baselines (ResNet18, EfficientNet-B0) foram
   comparados no teste fixo + McNemar. Para 5-fold nos três (~3 h em CPU), rodar:
   `python -m experimentos --kfold-todos`.
3. **"52 imagens reais" (Trilha A / `tab-trilhaA`):** mantidas no texto conforme
   confirmado que existem, mas **fora do git**. → **Pendência: commitar as imagens**
   e, idealmente, usá-las na avaliação de generalização (sintético → real).

---

## Arquivos novos (reprodutibilidade)

- [`src/experimentos.py`](src/experimentos.py) — harness completo: split fixo,
  baselines, métricas por classe, matriz de confusão, k-fold estratificado e McNemar.
  Flags úteis: `--epocas`, `--kfolds`, `--kfold-todos`, `--rapido`.
- [`src/formatar_tabelas.py`](src/formatar_tabelas.py) — converte
  `resultados/resultados.json` em fragmentos de tabela LaTeX (pt-BR).
- [`src/resultados/resultados.json`](src/resultados/resultados.json) — saída bruta da
  execução (config, split fixo, McNemar, k-fold).

Como reproduzir:

```bash
cd src
uv sync
.venv/bin/python -m experimentos --epocas 40 --lr 5e-4 --batch 32 --kfolds 5 --seed 42
.venv/bin/python formatar_tabelas.py        # imprime as tabelas LaTeX
```

---

## Backlog / próximos passos sugeridos

- [ ] Commitar as 52 imagens reais e rodar avaliação de generalização (domain gap).
- [ ] Rodar `--kfold-todos` para k-fold nos três modelos, se quiser rigor máximo.
- [ ] Comparação quantitativa multiagente × monolítico (requer chave Gemini + laudos
      com causa de referência rotulada).
- [ ] Estender a símbolos 2D (Data Matrix / QR) via ISO/IEC 15415.
- [ ] Calibrar os indicadores estimados contra um verificador certificado.
- [ ] (Opcional) Converter o artigo para o formato de 6 páginas de congresso (WVC/SIBGRAPI).




⚠️ A chave é free-tier: limite de 5 requisições/minuto, e o gemini-flash-latest resolve para gemini-3.5-flash. O grafo ADK faz ~5-6 chamadas LLM por análise (um agente por etapa), então uma única análise Auto estoura o limite → 429.


Resultado dos passos 1 e 2
✅ O que provamos (o essencial): o Gemini multimodal está funcionando e o árbitro visual corrige a confusão exata que motivou todo o trabalho — CNN dizia damaged_printhead_element (0.559), o árbitro olhou a imagem e devolveu no_defect (0.98) com justificativa visual correta. A classe corrigida é gravada no estado e flui para o laudo com o selo de arbitragem.

🐛 Bug corrigido no caminho: sua chave era válida mas has_gemini() dava False — o settings.py só lia src/.env, e sua chave está no .env da raiz. Agora ele carrega dos dois lugares (settings.py:27).

⚠️ A limitação que apareceu (não é bug nosso): a chave é free-tier, 5 req/min, e o gemini-flash-latest resolve para gemini-3.5-flash. O caminho Auto completo dispara ~5-6 chamadas LLM por análise (um agente por etapa) → estoura os 5/min e retorna 429. Por isso o card completo no navegador em modo Auto ainda não roda de forma confiável nesta cota.

Como destravar o Auto no navegador — recomendação
O caminho mais valioso (resolve a cota e melhora o design) é tornar os 3 especialistas de percepção determinísticos: leitura, indicadores e defeito só chamam ferramentas determinísticas — hoje cada um é um round-trip ao Gemini só para chamar uma função e repetir o resultado. Se eu chamar essas tools direto dentro de analyze_via_adk e semear o estado, o grafo passa a gastar Gemini só onde há raciocínio real (árbitro + diagnóstico + laudo): cai de ~6 para ~2-3 chamadas por análise, fica mais rápido, mais barato e cabe no free-tier. E continua sendo multiagente/ADK — só com percepção determinística (o que, aliás, reforça o argumento de robustez do artigo).

Alternativa: usar um tier pago do Gemini (remove o limite de 5/min sem mexer no código).

Quer que eu faça essa otimização (percepção determinística) para o modo Auto rodar de ponta a ponta no navegador dentro da cota grátis? Se sim, eu implemento e a gente valida o card completo (com o selo CNN → revisão visual) subindo o uvicorn.