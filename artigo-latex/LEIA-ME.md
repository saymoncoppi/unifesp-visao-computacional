# Artigo (abnTeX2 / ABNT) — pronto para o Overleaf

Projeto LaTeX do artigo **"Reconhecimento de padrões de falhas em etiquetas de
códigos de barras: um sistema de visão computacional com orquestração
multiagente"**, no formato de **artigo científico** do abnTeX2 (conforme ABNT).

> **✅ Compilação já testada** (pdfLaTeX + BibTeX, TeX Live 2026): **19 páginas, sem
> erros**, com sumário, citações e referências resolvidos e fontes embutidas. Um PDF
> de exemplo está em `artigo.pdf`. No Overleaf o resultado é o mesmo.
>
> *Aviso inofensivo:* pode aparecer `Package babel Warning: Name 'brazil' is
> deprecated`. Ele vem de dentro da própria classe abnTeX2, **não do seu texto**, e
> não afeta o PDF — pode ignorar.

## Arquivos deste projeto

| Arquivo | O que é | Você edita? |
|---|---|---|
| `artigo.tex` | Texto completo do artigo (todo o conteúdo está aqui) | **Sim** |
| `referencias.bib` | Bibliografia (14 referências verificadas) | **Sim** |
| `figuras/dataset_preview.png` | Figura de amostras do dataset sintético | troque se quiser |
| `LEIA-ME.md` | Este guia | não |

> **Importante:** este projeto **NÃO inclui** os arquivos de classe
> (`abntex2.cls`, `abntex2cite.sty`, `abntex2-alf.bst`). Isso é **de propósito**:
> o Overleaf já traz o abnTeX2 instalado, e usar a versão padrão dele garante que
> a formatação das referências saia correta. (Os arquivos que vinham no modelo do
> MPPL eram uma versão *customizada* para a Câmara dos Deputados e quebrariam as
> referências padrão.)

## Como importar no Overleaf (passo a passo)

1. Crie/entre na sua conta em <https://pt.overleaf.com>.
2. Faça o *upload* do arquivo **`artigo-overleaf.zip`** (que está na pasta acima
   deste projeto): botão **"Novo Projeto" → "Carregar Projeto" (Upload Project)**
   e selecione o `.zip`.
   *Alternativa:* crie um projeto em branco e arraste para dentro dele os arquivos
   `artigo.tex`, `referencias.bib` e a pasta `figuras/`.
3. Abra **Menu** (canto superior esquerdo) e configure:
   - **Compiler / Compilador:** `pdfLaTeX`
   - **TeX Live version:** `2024` (ou a mais recente)
   - **Main document:** `artigo.tex`
   - **Spell check:** `Portuguese (Brazil)`
4. Clique em **Recompilar**.
5. **As citações estão como `[?]` ou `(???)`?** É normal na 1ª vez. Clique em
   **Recompilar mais uma ou duas vezes** — o Overleaf roda o BibTeX e resolve as
   referências (ciclo pdfLaTeX → BibTeX → pdfLaTeX → pdfLaTeX).

## O que você precisa preencher (procure por `[...]` no `artigo.tex`)

- **Título** (topo do `artigo.tex`): `\titulo{...}` (português) e
  `\tituloestrangeiro{...}` (inglês — é impresso abaixo do título e é **obrigatório**
  neste modelo). Já estão preenchidos; ajuste se mudar o título.
- **Autoria** (comando `\autor{...}`): **já preenchida** com seus dados (Saymon
  Coppi de Oliveira Silva), a disciplina Visão Computacional (cód. 2587) e o
  Prof. Dr. Fabio Augusto Menocci Cappabianco. A **logo da Unifesp**
  (`figuras/unifesp.png`) já aparece no topo da 1ª página, via `\maketitlehooka`.
- **Ambiente experimental** (Seção *Metodologia*): hardware, versões, captura.
- **Seção *Resultados e discussão*:** é um **modelo**. As tabelas têm `---` no
  lugar dos números — substitua pelos resultados dos seus experimentos. Não há
  nenhum número inventado.
- **Conclusão:** trechos entre `[...]` a completar após os resultados.
- **Figuras de arquitetura e fluxograma** (Seção *Proposta*): há dois blocos
  comentados (`% \begin{figure}...`). Quando tiver as imagens, salve-as em
  `figuras/` (ex.: `arquitetura.png`, `fluxograma.png`) e **descomente** o bloco.

## Duas decisões suas nas referências (`referencias.bib`)

1. **ISO/IEC 15415:** deixei a edição **vigente (2024)**. Se o seu texto usa a
   metodologia da edição de **2011**, troque o `year` e a `url` na entrada
   `iso15415`.
2. **Chave `fff2024thermal`:** o artigo é real e correto, mas usa imagens ópticas
   (não térmicas). O nome da chave é só um rótulo interno — não aparece no PDF e
   não precisa mudar.

Todas as 14 referências foram conferidas em fontes oficiais (ISO, Pearson,
Springer, IEEE, Frontiers, Google, Google Patents, Zebra).

## Checklist ABNT rápido (o que o modelo já cuida e o que depende de você)

**Já resolvido pelo modelo abnTeX2:** fonte, tamanho, margens, espaçamento,
numeração de páginas, sumário, formato de citações autor-data (NBR 10520) e de
referências (NBR 6023), títulos de seção (NBR 6024).

**Depende de você:**
- **Resumo (NBR 6028):** 150–500 palavras, **parágrafo único**, impessoal, **sem
  citações**. Palavras-chave (máx. 6) separadas por `;` e terminadas por `.` — já
  está assim, é só adaptar o conteúdo.
- **Figuras/Tabelas/Quadros:** **título ACIMA** (começa com maiúscula, **sem ponto
  final**) e **fonte ABAIXO** (termina com ponto). Já estão nesse padrão. Todo
  elemento deve ser **citado no texto** (ex.: "a Tabela 1 mostra...").
- **Tabela × Quadro:** *tabela* = dado numérico, sem bordas verticais externas;
  *quadro* = texto/ilustração, com bordas. Neste modelo, os mapeamentos
  qualitativos estão como tabelas simples — se o(a) professor(a) exigir a distinção
  formal "Quadro", me avise que eu adapto.
- **Números:** ponto para milhar, **vírgula para decimal** (ex.: 0,82).
- **Siglas:** 1ª vez por extenso + sigla entre parênteses; depois só a sigla.
- **Sem `et al.` na lista de referências:** já configurado (`abnt-etal-list=0`).

## Ilustrações reais da Zebra já incluídas

O artigo já traz três figuras de qualidade de impressão, com citação à Zebra:
- **Figura 1** (Seção 2.2): comparação de *darkness* (*too light* → *too dark*),
  extraída do manual de manutenção da ZT411/ZT421.
- **Figura 2** (Seção 2.3): painel com seis defeitos reais (impressão clara, *ribbon*
  enrugado, elemento danificado, mancha, pressão desigual, perda de registro), da
  base de conhecimento Zebra.

Arquivos em `figuras/` (`zebra_*.jpg`/`zebra_darkness_comparison.png`). São usados
como **citação acadêmica** (poucas figuras, com fonte indicada) — uso legítimo na
fundamentação.

## Observação sobre o código Python

O `artigo.tex` traz o código de referência (agentes ADK + FastAPI) em blocos de
listagem, exatamente como no seu rascunho. Você disse que ainda vai mexer no
código — quando estabilizar, é só atualizar esses blocos.
