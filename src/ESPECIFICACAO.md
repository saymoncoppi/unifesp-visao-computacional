# Especificação do inspetor de etiquetas (contrato de interfaces)

Fonte da verdade para a implementação. **Siga as assinaturas e os formatos de
retorno à risca** — vários módulos são escritos em paralelo e precisam encaixar.

## Objetivo
Dada a imagem de uma etiqueta com código de barras, o sistema:
1. **decodifica** o código (simbologia + conteúdo) e diz se é legível — OpenCV + pyzbar;
2. faz **OCR** do texto humano-legível — Tesseract;
3. estima **indicadores de qualidade** (contraste, uniformidade, nitidez) — OpenCV;
4. **classifica o defeito** de impressão entre 7 classes — CNN MobileNetV3 (PyTorch);
5. **diagnostica a causa provável e a correção** — Gemini (ADK) com *fallback* por regras
   sobre a base de conhecimento Zebra;
6. consolida tudo em um **laudo** JSON, servido por uma **API/chat** (envie a imagem,
   receba o laudo).

A orquestração usa o **ADK**: análises 1–4 em paralelo → diagnóstico → laudo.

## Regras globais (obrigatórias)
- **Português** nos nomes de funções, variáveis e docstrings.
- **Imports pesados são LAZY**: `import cv2`, `torch`, `pyzbar`, `pytesseract`,
  `google.adk`, `google.genai` devem ficar **dentro das funções**, nunca no topo do
  módulo. Assim o pacote importa mesmo sem essas libs instaladas, e `python -m
  py_compile` passa. No topo só: stdlib, `from __future__ import annotations`, e
  imports de `inspetor.config` / `inspetor.laudo`.
- **Degradação graciosa**: se uma lib/binário faltar, capture o `ImportError`/erro e
  retorne um dict com o campo de erro preenchido e valores neutros (não derrube o
  processo). Ex.: decodificação sem pyzbar → `{"legivel": None, ..., "erro": "pyzbar ausente"}`.
- Constantes vêm de `inspetor.config` (CLASSES, CLASSE_PT, IMG_SIZE, BACKBONE, MEAN,
  STD, DATASET_DIR, LABELS_CSV, MODELO_PATH, GEMINI_MODEL, `tem_gemini()`).
- Sem `print` fora de scripts `__main__`; use `return`/`raise`.

## Módulos e assinaturas

### inspetor/visao.py
```python
def carregar_imagem(caminho: str) -> "np.ndarray"        # BGR (cv2.imread)
def para_cinza(img) -> "np.ndarray"
def segmentar_codigo(cinza) -> tuple["np.ndarray", tuple | None]
    # detecta a região do código: gradiente (Sobel/Scharr) -> blur -> threshold
    # (Otsu) -> morfologia (close+erode+dilate) -> maior contorno.
    # retorna (roi_cinza, bbox) com bbox=(x, y, w, h) ou (cinza, None) se não achar.
def decodificar(caminho_ou_img) -> dict
    # usa pyzbar.decode (tenta imagem original e ROI/limiarizada).
    # -> {"legivel": bool|None, "simbologia": str|None, "conteudo": str|None,
    #     "n_simbolos": int, "erro": str|None}
def ocr_texto(img_ou_roi) -> str      # pytesseract.image_to_string; "" se indisponível
def indicadores(cinza, roi=None) -> dict
    # contraste = (Imax - Imin)/255 sobre a ROI; uniformidade = 1 - desvio-padrão
    # normalizado do perfil; nitidez = variância do Laplaciano normalizada em [0,1].
    # -> {"contraste": float, "uniformidade": float, "nitidez": float}
```

### inspetor/rede.py  (CNN — PyTorch/torchvision)
```python
def construir_modelo(num_classes=len(CLASSES), backbone=BACKBONE, preTreinado=True)
    # torchvision.models.mobilenet_v3_small; troca a última Linear por num_classes.
def transformacoes(treino: bool = False)
    # Resize(IMG_SIZE), (treino: augment leve), Grayscale(3), ToTensor, Normalize(MEAN,STD)
def carregar_modelo(caminho=MODELO_PATH, device=None) -> "nn.Module"
    # constrói + load_state_dict(eval). Se o arquivo não existir, levanta FileNotFoundError
    # com mensagem clara ("treine com: python -m inspetor.treino").
def prever(caminho_ou_img, modelo=None, device=None) -> dict
    # -> {"classe": str, "classe_pt": str, "confianca": float, "probs": {classe: float},
    #     "erro": str|None}. Se torch/modelo faltarem, retorna erro e classe=None.
```

### inspetor/dataset.py  (PyTorch Dataset)
```python
class DatasetDefeitos(torch.utils.data.Dataset)   # lê LABELS_CSV, filtra por split
    # __init__(self, split="train", dataset_dir=DATASET_DIR, transform=None)
    # rótulo = índice de CLASSES; imagem = DATASET_DIR / linha["filename"]
def carregar_loaders(dataset_dir=DATASET_DIR, batch_size=32, num_workers=2) -> dict
    # -> {"train": DataLoader, "val": DataLoader, "test": DataLoader}
```

### inspetor/treino.py  (script de treino)
```python
def treinar(epocas=10, lr=1e-3, batch_size=32, dataset_dir=DATASET_DIR,
            saida=MODELO_PATH, congelar_backbone=True) -> dict
    # transferência de aprendizado; CrossEntropy; Adam; salva o melhor por val_acc em `saida`.
    # retorna métricas finais {"val_acc":..., "test_acc":..., "por_classe": {...}}.
# if __name__ == "__main__": argparse (--epocas --lr --batch --saida)
```

### inspetor/kb.py  (base de conhecimento Zebra)
```python
KB: list[dict]   # cada item: {"classe", "aparencia", "causa_provavel",
                 #             "acao_corretiva", "parametros": [...], "fonte"}
def buscar_por_classe(classe: str) -> dict | None
def buscar(sintomas: str) -> list[dict]           # recuperação simples por palavra-chave
def contexto_para_llm(classe: str, indicadores: dict, leitura: dict) -> str
```
> Preencher KB com o mapeamento defeito→causa→ação da documentação Zebra
> (será fornecido um JSON extraído dos PDFs; enquanto isso, use a taxonomia das 7
> classes de CLASSE_PT). Campo `fonte` = "Zebra Technologies (2024)".

### inspetor/diagnostico.py
```python
def diagnosticar(defeito: dict, leitura: dict, indicadores: dict,
                 usar_gemini: bool = True) -> dict
    # -> {"causa_provavel", "correcao_sugerida", "fundamentacao", "fonte", "via"}
    # via="gemini" se tem_gemini() e google.genai disponível (monta prompt com
    # kb.contexto_para_llm e pede JSON); caso contrário via="regras" usando
    # kb.buscar_por_classe(defeito["classe"]).
```

### inspetor/ferramentas.py  (ferramentas para o ADK + pipeline direto)
```python
# Funções-ferramenta (docstring clara — o ADK usa a docstring como descrição):
def decodificar_codigo(caminho_imagem: str) -> dict      # -> visao.decodificar (+ ocr)
def estimar_indicadores(caminho_imagem: str) -> dict     # -> visao.indicadores
def classificar_defeito(caminho_imagem: str) -> dict     # -> rede.prever
def buscar_documentacao_zebra(sintomas: str) -> str      # -> kb.buscar (texto)

def analisar_imagem(caminho_imagem: str) -> dict
    # PIPELINE DIRETO (sem ADK): decodificar+ocr, indicadores, classificar,
    # diagnosticar -> laudo.montar_laudo(...).to_dict(). É o núcleo robusto usado
    # por CLI/API e serve de "baseline monolítico". Nunca levanta por lib ausente:
    # acumula avisos em laudo["erros"].
```

### inspetor/agentes.py  (grafo ADK — google.adk)
```python
def construir_root_agent()   # LlmAgent p/ leitura, indicadores, defeito (tools acima) ->
                             # ParallelAgent -> LlmAgent diagnóstico -> LlmAgent laudo ->
                             # SequentialAgent root. MODEL=config.GEMINI_MODEL.
async def analisar_via_adk(caminho_imagem: str) -> dict   # roda o grafo via Runner
# Se google.adk indisponível, construir_root_agent levanta ImportError com dica.
```

### app/cli.py
`python -m app.cli CAMINHO [--adk] [--json]` → chama `analisar_imagem` (ou
`analisar_via_adk` se `--adk`), imprime `Laudo.resumo()` e, com `--json`, o JSON.

### app/api.py  (FastAPI)
- `GET /` → serve `app/chat.html`.
- `POST /analisar` (multipart, campo `imagem`; query `adk: bool=false`) → salva temp,
  chama `analisar_imagem` (ou ADK), devolve o laudo JSON.
- `GET /saude` → `{"status": "ok"}`.
Rodar: `uvicorn app.api:app --reload`.

### app/chat.html
Página única autossuficiente (HTML+CSS+JS vanilla, sem CDN): input de imagem +
preview + botão "Analisar" que faz `POST /analisar` e renderiza o laudo como
mensagens de chat (legível/simbologia, defeito+confiança, causa, correção). Trata erro.

## Formato do laudo (retorno de analisar_imagem)
```json
{
  "legivel": true, "simbologia": "CODE128", "conteudo": "CB123",
  "texto_ocr": "CB123", "indicadores": {"contraste":0.82,"uniformidade":0.74,"nitidez":0.6},
  "defeito": {"classe":"ribbon_enrugado","classe_pt":"Ribbon enrugado","confianca":0.91,"probs":{...}},
  "causa_provavel":"Tensão/alinhamento do ribbon",
  "correcao_sugerida":"Ajustar a tensão do ribbon; verificar o percurso",
  "fundamentacao":"...", "fonte":"Zebra Technologies (2024)",
  "via_diagnostico":"regras", "confianca_geral":0.91, "erros":[]
}
```
