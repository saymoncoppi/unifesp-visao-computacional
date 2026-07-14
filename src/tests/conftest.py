"""Configuração compartilhada dos testes (pytest).

Garante que a raiz do projeto (``src/``, que contém o pacote ``inspetor``) esteja
no ``sys.path`` para que os testes importem ``inspetor`` independentemente de onde
o pytest seja invocado. Define também fixtures de imagem reutilizáveis.

Nenhuma biblioteca pesada (torch/cv2/pyzbar/PIL) é importada no topo — os testes
que precisam delas usam ``pytest.importorskip`` e continuam passando (via *skip*)
quando as dependências não estão instaladas.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

# --------------------------------------------------------------------------
# sys.path: raiz do projeto = src/ (pasta que contém o pacote `inspetor`).
# conftest.py está em src/tests/conftest.py -> parents[1] == src/.
# --------------------------------------------------------------------------
RAIZ_SRC = Path(__file__).resolve().parents[1]          # .../src
if str(RAIZ_SRC) not in sys.path:
    sys.path.insert(0, str(RAIZ_SRC))

# Diretório do dataset sintético (relativo à raiz do projeto: src/datasets/...).
_DIR_TEST = RAIZ_SRC / "datasets" / "dataset_sintetico" / "images" / "test"


@pytest.fixture
def imagem_teste() -> Path:
    """Caminho do primeiro ``.png`` do split de teste do dataset sintético.

    Procura recursivamente em ``datasets/dataset_sintetico/images/test/**``.
    Se nenhuma imagem for encontrada (dataset ausente), o teste é *skipado* em vez
    de falhar.
    """
    if not _DIR_TEST.exists():
        pytest.skip(f"dataset de teste ausente: {_DIR_TEST}")
    pngs = sorted(_DIR_TEST.glob("**/*.png"))
    if not pngs:
        pytest.skip(f"nenhum .png em {_DIR_TEST}")
    return pngs[0]


@pytest.fixture
def imagem_tmp(tmp_path) -> Path:
    """Cria um PNG pequeno com PIL em ``tmp_path`` e devolve seu caminho.

    Requer Pillow; se ausente, o teste que usar esta fixture é *skipado*.
    """
    Image = pytest.importorskip("PIL.Image")
    caminho = tmp_path / "amostra.png"
    img = Image.new("RGB", (32, 16), color=(255, 255, 255))
    img.save(caminho)
    return caminho
