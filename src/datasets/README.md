# Datasets

Este diretório reúne os conjuntos de dados usados para treinar e avaliar o
inspetor de defeitos de impressão de códigos de barras.

## `dataset_sintetico/`

Dataset **sintético**, balanceado e rotulado, gerado por
[`../src/gerar_dataset.py`](../src/gerar_dataset.py). Cada imagem reproduz a
assinatura visual de um defeito de impressão controlado (cabeça queimada,
ribbon enrugado, ponto queimado, impressão clara, pressão desigual, cabeça
suja) mais a classe `sem_defeito`, sobre símbolos 1D (Code128, Code39, EAN,
ITF) e 2D (QR, DataMatrix).

Para (re)gerar:

```bash
cd src
python gerar_dataset.py --out datasets/dataset_sintetico --per-class 90 --seed 42
```

Estrutura de saída:

```
dataset_sintetico/
  images/<split>/<classe>/<simbologia>_<idx>.png   # train / val / test
  labels.csv                                        # filename, split, classe, simbologia, payload, params
  previews/<classe>.png                             # montagem por classe (para o artigo)
```

Como os defeitos são **sintéticos e controlados**, esse dataset serve para
**treino e validação** do modelo.

## Dados reais do Roboflow Universe (conjunto de teste de generalização)

As imagens sintéticas cobrem os defeitos de forma controlada, mas não capturam
toda a variabilidade de fotos reais (iluminação, foco, perspectiva, sujeira,
impressoras diferentes). Por isso baixamos **imagens reais** do
[Roboflow Universe](https://universe.roboflow.com/) para usá-las como
**conjunto de TESTE de generalização** — mede-se o quanto o modelo treinado no
sintético transfere para o mundo real (**sintético → real**). Elas **não** são
usadas para treino.

### 1. Obtenha uma chave de API gratuita do Roboflow

1. Crie uma conta gratuita em <https://app.roboflow.com>.
2. Acesse <https://app.roboflow.com/settings/api> e copie sua **Private API Key**.
3. Exporte a chave como variável de ambiente (recomendado):

   ```bash
   export ROBOFLOW_API_KEY=SUA_CHAVE
   ```

   Alternativamente, passe `--api-key SUA_CHAVE` na linha de comando.

### 2. Encontre um dataset

Procure por datasets de defeitos de código de barras no Roboflow Universe:

- <https://universe.roboflow.com/search?q=barcode+damage>
- também tente: **"barcode defect"** e **"label print quality"**

Na página do dataset escolhido:

1. Abra a aba **"Download Dataset"**.
2. Clique em **"show download code"** (mostrar código de download).
3. Copie os valores de **workspace**, **project** e **version** do snippet
   Python exibido, por exemplo:

   ```python
   rf.workspace("MEU-WORKSPACE").project("barcode-damage")   # --workspace / --project
   project.version(1).download("folder")                      # --version / --format
   ```

### 3. Instale a dependência

```bash
cd src
uv pip install roboflow        # apenas o pacote
# ou:
uv sync --extra datasets       # via extra do pyproject.toml
```

### 4. Baixe o dataset

Use o script [`../src/baixar_roboflow.py`](../src/baixar_roboflow.py):

```bash
cd src
python baixar_roboflow.py \
    --workspace EXEMPLO \
    --project barcode-damage \
    --version 1 \
    --out datasets/roboflow_barcode
```

(substitua `EXEMPLO`, `barcode-damage` e `1` pelos valores copiados do código
de download do dataset que você escolheu).

O download ficará em `datasets/roboflow_barcode/`. Trate essas imagens como
**conjunto de teste de generalização**: avalie o modelo nelas, mas não as
inclua no treino.
