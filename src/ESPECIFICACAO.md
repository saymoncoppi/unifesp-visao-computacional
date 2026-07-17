# Especificação do inspetor de etiquetas (contrato de interfaces)

Fonte da verdade para a implementação. **Siga as assinaturas e os formatos de
retorno à risca** — vários módulos são escritos em paralelo e precisam encaixar.

## Objetivo
Dada a imagem de uma etiqueta com código de barras, o sistema:
1. **decodifica** o código (simbologia + conteúdo) e diz se é legível — OpenCV + pyzbar;
2. estima **indicadores de qualidade** (contraste, uniformidade, nitidez) — OpenCV;
3. **classifica o defeito** de impressão entre 7 classes — CNN MobileNetV3 (PyTorch);
4. **diagnostica a causa provável e a correção** — Gemini (ADK) com *fallback* por regras
   sobre a base de conhecimento Zebra;
5. consolida tudo em um **laudo** JSON, servido por uma **API/chat** (envie a imagem,
   receba o laudo).

A orquestração usa o **ADK**: análises 1–3 em paralelo → diagnóstico → laudo.

## Regras globais (obrigatórias)
- **Português** nos nomes de funções, variáveis e docstrings.
- **Imports pesados são LAZY**: `import cv2`, `torch`, `pyzbar`,
  `google.adk`, `google.genai` devem ficar **dentro das funções**, nunca no topo do
  módulo. Assim o pacote importa mesmo sem essas libs instaladas, e `python -m
  py_compile` passa. No topo só: stdlib, `from __future__ import annotations`, e
  imports de `config.inspector.settings` / `config.inspector.report`.
- **Degradação graciosa**: se uma lib/binário faltar, capture o `ImportError`/erro e
  retorne um dict com o campo de erro preenchido e valores neutros (não derrube o
  processo). Ex.: decodificação sem pyzbar → `{"readable": None, ..., "error": "pyzbar ausente"}`.
- Constantes vêm de `config.inspector.settings` (CLASSES, CLASS_LABELS_PT, IMG_SIZE, BACKBONE, MEAN,
  STD, DATASET_DIR, LABELS_CSV, MODEL_PATH, GEMINI_MODEL, `has_gemini()`).
- Sem `print` fora de scripts `__main__`; use `return`/`raise`.

## Módulos e assinaturas

### config/inspector/vision.py
```python
def load_image(path: str) -> "np.ndarray"        # BGR (cv2.imread)
def to_gray(img) -> "np.ndarray"
def segment_code(gray) -> tuple["np.ndarray", tuple | None]
    # detecta a região do código: gradiente (Sobel/Scharr) -> blur -> threshold
    # (Otsu) -> morfologia (close+erode+dilate) -> maior contorno.
    # retorna (roi_gray, bbox) com bbox=(x, y, w, h) ou (gray, None) se não achar.
def decode(path_or_img) -> dict
    # usa pyzbar.decode (tenta imagem original e ROI/limiarizada).
    # -> {"readable": bool|None, "symbology": str|None, "content": str|None,
    #     "symbol_count": int, "error": str|None}
def indicators(gray, roi=None) -> dict
    # contraste = (Imax - Imin)/255 sobre a ROI; uniformidade = 1 - desvio-padrão
    # normalizado do perfil; nitidez = variância do Laplaciano normalizada em [0,1].
    # -> {"contrast": float, "uniformity": float, "sharpness": float}
```

### config/inspector/network.py  (CNN — PyTorch/torchvision)
```python
def build_model(num_classes=len(CLASSES), backbone=BACKBONE, pretrained=True)
    # torchvision.models.mobilenet_v3_small; troca a última Linear por num_classes.
def build_transforms(train: bool = False)
    # Resize(IMG_SIZE), (train: augment leve), Grayscale(3), ToTensor, Normalize(MEAN,STD)
def load_model(path=MODEL_PATH, device=None) -> "nn.Module"
    # constrói + load_state_dict(eval). Se o arquivo não existir, levanta FileNotFoundError
    # com mensagem clara ("treine com: python -m config.inspector.training").
def predict(path_or_img, model=None, device=None) -> dict
    # -> {"class": str, "class_label": str, "confidence": float, "probs": {class: float},
    #     "error": str|None}. Se torch/modelo faltarem, retorna erro e class=None.
```

### config/inspector/dataset.py  (PyTorch Dataset)
```python
class DefectDataset(torch.utils.data.Dataset)   # lê LABELS_CSV, filtra por split
    # __init__(self, split="train", dataset_dir=DATASET_DIR, transform=None)
    # rótulo = índice de CLASSES; imagem = DATASET_DIR / row["filename"]
def build_loaders(dataset_dir=DATASET_DIR, batch_size=32, num_workers=2) -> dict
    # -> {"train": DataLoader, "val": DataLoader, "test": DataLoader}
```

### config/inspector/training.py  (script de treino)
```python
def train(epochs=10, lr=1e-3, batch_size=32, dataset_dir=DATASET_DIR,
          output_path=MODEL_PATH, freeze_backbone=True) -> dict
    # transferência de aprendizado; CrossEntropy; Adam; salva o melhor por val_acc em `output_path`.
    # retorna métricas finais {"val_acc":..., "test_acc":..., "per_class": {...}}.
# if __name__ == "__main__": argparse (--epochs --lr --batch --output)
```

### config/inspector/kb.py  (base de conhecimento Zebra)
```python
KB: list[dict]   # cada item: {"class", "appearance", "probable_cause",
                 #             "corrective_action", "parameters": [...], "source"}
def search_by_class(defect_class: str) -> dict | None
def search(symptoms: str) -> list[dict]           # recuperação simples por palavra-chave
def context_for_llm(defect_class: str, indicators: dict, reading: dict) -> str
```
> Preencher KB com o mapeamento defeito→causa→ação da documentação Zebra
> (será fornecido um JSON extraído dos PDFs; enquanto isso, use a taxonomia das 7
> classes de CLASS_LABELS_PT). Campo `source` = "Zebra Technologies (2024)".

### config/inspector/diagnosis.py
```python
def diagnose(defect: dict, reading: dict, indicators: dict,
            use_gemini: bool = True) -> dict
    # -> {"probable_cause", "corrective_action", "rationale", "source", "method"}
    # method="gemini" se has_gemini() e google.genai disponível (monta prompt com
    # kb.context_for_llm e pede JSON); caso contrário method="rules" usando
    # kb.search_by_class(defect["class"]).
```

### config/inspector/tools.py  (ferramentas para o ADK + pipeline direto)
```python
# Funções-ferramenta (docstring clara — o ADK usa a docstring como descrição):
def decode_code(image_path: str) -> dict      # -> vision.decode
def estimate_indicators(image_path: str) -> dict     # -> vision.indicators
def classify_defect(image_path: str) -> dict     # -> network.predict
def search_zebra_docs(symptoms: str) -> str      # -> kb.search (texto)

def analyze_image(image_path: str) -> dict
    # PIPELINE DIRETO (sem ADK): decode, indicators, classify,
    # diagnose -> report.build_report(...).to_dict(). É o núcleo robusto usado
    # por CLI/API e serve de "baseline monolítico". Nunca levanta por lib ausente:
    # acumula avisos em report["errors"].
```

### config/inspector/agents.py  (grafo ADK — google.adk)
```python
def build_root_agent()   # LlmAgent p/ leitura, indicadores, defeito (tools acima) ->
                         # ParallelAgent -> LlmAgent diagnóstico -> LlmAgent laudo ->
                         # SequentialAgent root. MODEL=settings.GEMINI_MODEL.
async def analyze_via_adk(image_path: str) -> dict   # roda o grafo via Runner
# Se google.adk indisponível, build_root_agent levanta ImportError com dica.
```

### app/cli.py
`python -m app.cli PATH [--adk] [--json]` → chama `analyze_image` (ou
`analyze_via_adk` se `--adk`), imprime `Report.summary()` e, com `--json`, o JSON.

### app/api.py  (FastAPI)
- `GET /` → serve `app/chat.html`.
- `POST /analyze` (multipart, campo `image`; query `adk: bool=false`) → salva temp,
  chama `analyze_image` (ou ADK), devolve o laudo JSON.
- `GET /health` → `{"status": "ok"}`.
Rodar: `uvicorn app.api:app --reload`.

### app/chat.html
Página única autossuficiente (HTML+CSS+JS vanilla, sem CDN): input de imagem +
preview + botão "Analisar" que faz `POST /analyze` e renderiza o laudo como
mensagens de chat (legível/simbologia, defeito+confiança, causa, correção). Trata erro.

## Formato do laudo (retorno de analyze_image)
```json
{
  "readable": true, "code_detected": true, "symbology": "CODE128", "content": "CB123",
  "indicators": {"contrast":0.82,"uniformity":0.74,"sharpness":0.6},
  "defect": {"class":"wrinkled_ribbon","class_label":"Ribbon enrugado","confidence":0.91,"probs":{...}},
  "probable_cause":"Tensão/alinhamento do ribbon",
  "corrective_action":"Ajustar a tensão do ribbon; verificar o percurso",
  "reasoning":"...", "source":"Zebra Technologies (2024)",
  "diagnosis_method":"rules", "overall_confidence":0.91, "errors":[]
}
```
