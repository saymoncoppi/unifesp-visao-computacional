"""Configuração central do projeto (constantes compartilhadas por todos os módulos)."""
from __future__ import annotations

import os
from pathlib import Path

# --------------------------------------------------------------------------
# Caminhos
# --------------------------------------------------------------------------
RAIZ = Path(__file__).resolve().parent.parent            # .../solucao
PROJETO = RAIZ.parent                                     # .../artigo
# Carrega variáveis de um arquivo .env (ex.: GOOGLE_API_KEY), se existir
try:
    from dotenv import load_dotenv
    load_dotenv(RAIZ / ".env")
except Exception:
    pass

# Dataset agora vive dentro do projeto: src/datasets/
DATASET_DIR = Path(os.environ.get("DATASET_DIR", RAIZ / "datasets" / "dataset_sintetico"))
LABELS_CSV = DATASET_DIR / "labels.csv"
MODELOS_DIR = RAIZ / "modelos"
MODELO_PATH = Path(os.environ.get("MODELO_PATH", MODELOS_DIR / "classificador_defeitos.pt"))

# --------------------------------------------------------------------------
# Classes de defeito (mesma taxonomia de gerar_dataset.py)
# A ORDEM define o índice usado pela CNN — não reordenar sem retreinar.
# --------------------------------------------------------------------------
CLASSES = [
    "sem_defeito",
    "cabeca_queimada",
    "ribbon_enrugado",
    "ponto_queimado",
    "impressao_clara",
    "pressao_desigual",
    "cabeca_suja",
]

CLASSE_PT = {
    "sem_defeito": "Sem defeito",
    "cabeca_queimada": "Elemento da cabeça danificado",
    "ribbon_enrugado": "Ribbon enrugado",
    "ponto_queimado": "Ponto queimado (darkness alto)",
    "impressao_clara": "Impressão clara (darkness baixo)",
    "pressao_desigual": "Pressão desigual da cabeça",
    "cabeca_suja": "Cabeça de impressão suja (voids)",
}

# Nomes de exibição em inglês (mesma taxonomia de CLASSES).
CLASSE_EN = {
    "sem_defeito": "No defect",
    "cabeca_queimada": "Damaged printhead element",
    "ribbon_enrugado": "Wrinkled ribbon",
    "ponto_queimado": "Burnt spot (high darkness)",
    "impressao_clara": "Light print (low darkness)",
    "pressao_desigual": "Uneven printhead pressure",
    "cabeca_suja": "Dirty printhead (voids)",
}

# --------------------------------------------------------------------------
# Idiomas suportados pela interface / laudo
# --------------------------------------------------------------------------
IDIOMAS = ("pt-BR", "en-US")
IDIOMA_PADRAO = "pt-BR"


def normalizar_idioma(idioma: str | None) -> str:
    """Normaliza o código de idioma para um dos suportados (fallback: pt-BR)."""
    return idioma if idioma in IDIOMAS else IDIOMA_PADRAO


def nome_classe(classe: str | None, idioma: str = IDIOMA_PADRAO) -> str:
    """Nome de exibição do defeito no idioma pedido (fallback: código da classe)."""
    if not classe:
        return "—"
    tabela = CLASSE_EN if normalizar_idioma(idioma) == "en-US" else CLASSE_PT
    return tabela.get(classe, classe)

# --------------------------------------------------------------------------
# Modelo / visão
# --------------------------------------------------------------------------
BACKBONE = "mobilenet_v3_small"     # backbone leve (transferência de aprendizado)
IMG_SIZE = 224                      # entrada da CNN
MEAN = (0.485, 0.456, 0.406)        # normalização ImageNet
STD = (0.229, 0.224, 0.225)

# --------------------------------------------------------------------------
# LLM / ADK
# --------------------------------------------------------------------------
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-flash-latest")
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY", "")   # se vazio -> fallback por regras


def tem_gemini() -> bool:
    """Há chave de API configurada para usar o Gemini?"""
    return bool(os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY"))


def num_classes() -> int:
    return len(CLASSES)
