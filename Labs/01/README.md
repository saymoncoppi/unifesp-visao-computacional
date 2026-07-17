# Exercícios de OpenCV em C++

Projeto didático com 8 exercícios independentes de Visão Computacional em C++ usando OpenCV no Fedora.

## Pré-requisitos

No Fedora 43 KDE, instale as dependências do sistema:

- `gcc`
- `gcc-c++`
- `make`
- `cmake`
- `pkg-config` *(normalmente fornecido pelo pacote `pkgconf-pkg-config` no Fedora)*
- `opencv-devel`

Sequência recomendada:

1. Atualizar o sistema.
2. Instalar os pacotes acima.
3. Confirmar as versões com `g++ --version`, `cmake --version`, `pkg-config --version` e `pkg-config --modversion opencv4`.

## Instalação manual do `opencv-devel`

Se o ambiente já tiver `gcc`, `gcc-c++`, `make`, `cmake` e `pkg-config`, a instalação manual do pacote de desenvolvimento do OpenCV no Fedora pode ser feita diretamente no terminal com:

```bash
sudo dnf install -y opencv-devel
```

Se preferir instalar todas as dependências do projeto de uma vez, use:

```bash
sudo dnf install -y gcc gcc-c++ make cmake pkgconf-pkg-config opencv-devel
```

### Verificação após a instalação

Depois da instalação, confirme se o pacote foi instalado corretamente com:

```bash
rpm -q opencv-devel
pkg-config --modversion opencv4
```

O resultado esperado é:

- `rpm -q opencv-devel` mostrando a versão instalada do pacote;
- `pkg-config --modversion opencv4` retornando a versão do OpenCV, por exemplo `4.11.0`.

Se `pkg-config --modversion opencv4` ainda falhar, revise se a instalação terminou sem erros e se o pacote `opencv-devel` foi realmente adicionado ao sistema.

> Neste ambiente de trabalho, `gcc`, `gcc-c++`, `make`, `cmake` e o comando `pkg-config` já estão disponíveis. Os binários do OpenCV também já estão presentes, mas os headers e o arquivo `opencv4.pc` ainda não estão instalados. Por isso, o build local só ficará disponível após instalar `opencv-devel`.

## Estrutura

- `src/common/`: utilitários mínimos para leitura, validação, exibição e gravação.
- `src/ex01_leitura_exibicao/`: leitura da imagem, exibição e metadados.
- `src/ex02_escala_cinza/`: conversão para tons de cinza.
- `src/ex03_valor_pixel/`: leitura do valor de um pixel em `(x, y)`.
- `src/ex04_negativo/`: transformação negativa em imagem em cinza.
- `src/ex05_binarizacao/`: limiarização com limiar configurável.
- `src/ex06_quantizacao/`: quantização com 128, 64, 16 e 4 níveis.
- `src/ex07_reducao_resolucao/`: redução de resolução e reampliação.
- `src/ex08_comparacao_amostragem_quantizacao/`: comparação visual e textual entre perdas tonais e espaciais.
- `output/`: saídas geradas pelos exercícios.

## Build

Da raiz do projeto:

1. Configure o build com CMake.
2. Compile todos os executáveis.

Arquivos gerados irão para `build/`.

### Como fazer o build na prática

Se você nunca compilou um projeto C++ com CMake, pode seguir exatamente esta sequência a partir da pasta do projeto:

```bash
cd .
cmake -S . -B build
cmake --build build -j
```

### O que cada comando faz

- `cd .` assume que você já abriu o terminal na pasta raiz do projeto;
- `cmake -S . -B build` prepara os arquivos de compilação dentro da pasta `build/`;
- `cmake --build build -j` compila todos os executáveis do projeto.

### Resultado esperado

Se tudo der certo, os binários serão gerados dentro da pasta `build/`, por exemplo:

- `build/ex01_leitura_exibicao`
- `build/ex02_escala_cinza`
- `build/ex03_valor_pixel`
- `build/ex04_negativo`
- `build/ex05_binarizacao`
- `build/ex06_quantizacao`
- `build/ex07_reducao_resolucao`
- `build/ex08_comparacao_amostragem_quantizacao`

### Se der erro no build

Os problemas mais comuns neste projeto são:

- `opencv-devel` ainda não instalado;
- `pkg-config --modversion opencv4` falhando;
- tentativa de executar `./build/ex01_leitura_exibicao` antes de rodar o build.

Se o terminal disser que o arquivo não existe, normalmente significa que a compilação ainda não foi feita ou falhou antes de gerar os executáveis.

## Execução

Os programas aceitam o caminho da imagem por linha de comando. Exemplos típicos a partir da raiz do projeto:

- `./build/ex01_leitura_exibicao imagem.jpg`
- `./build/ex02_escala_cinza imagem.jpg`
- `./build/ex03_valor_pixel imagem.jpg 120 80`
- `./build/ex04_negativo imagem.jpg`
- `./build/ex05_binarizacao imagem.jpg 128`
- `./build/ex06_quantizacao imagem.jpg`
- `./build/ex07_reducao_resolucao imagem.jpg 4`
- `./build/ex08_comparacao_amostragem_quantizacao imagem.jpg 4 4`

Se nenhum caminho for passado, os programas tentam localizar `imagem.jpg` automaticamente a partir do diretório atual e da raiz do projeto.

## Resumo dos exercícios

### ex01 — leitura e exibição

Carrega a imagem colorida, imprime largura, altura, número de canais e exibe a janela principal.

### ex02 — escala de cinza

Converte a imagem colorida para tons de cinza, salva o resultado e exibe original + cinza.

### ex03 — valor de pixel

Lê um pixel em coordenadas `(x, y)` com validação de faixa. A convenção usada é `(coluna, linha)`.

### ex04 — negativo

Aplica a transformação pontual $255 - p(x, y)$ em uma imagem em escala de cinza.

### ex05 — binarização

Aplica limiarização fixa com limiar configurável por linha de comando.

### ex06 — quantização

Gera quatro imagens quantizadas com 128, 64, 16 e 4 níveis e salva cada saída em `output/`.

### ex07 — redução de resolução

Reduz a imagem por um fator inteiro, depois reamplia para o tamanho original. A implementação registra no terminal a interpolação usada.

### ex08 — comparação entre amostragem e quantização

Gera três variações processadas — quantizada, reamostrada e reamostrada + quantizada — e imprime uma análise visual curta no terminal.

## Observações de validação

- Falha ao abrir janela com `cv::imshow` normalmente indica problema de sessão gráfica e não de compilação.
- O `ex03` valida coordenadas antes do acesso ao pixel.
- O `ex05` limita o limiar ao intervalo `[0, 255]`.
- O `ex06` usa uma fórmula explícita baseada no número de níveis desejado.
- O `ex07` usa `INTER_AREA` na redução e `INTER_NEAREST` na reampliação para realçar o efeito de perda espacial.
- O `ex08` imprime uma comparação curta entre perda tonal e perda espacial.