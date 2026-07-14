"""Testes de inspetor.dataset (Dataset map-style, duck-typed).

O ``DatasetDefeitos`` NÃO herda de ``torch.utils.data.Dataset`` (é duck-typed),
portanto construção e ``__len__`` não exigem torch. Para obter um item, usamos uma
transformação no-op (evitando ``torchvision``): assim só o Pillow é necessário para
abrir a imagem.
"""
from __future__ import annotations

import pytest

from inspetor import config
from inspetor.dataset import DatasetDefeitos


def _dataset_disponivel() -> bool:
    csv_path = config.DATASET_DIR / "labels.csv"
    if not csv_path.exists():
        csv_path = config.LABELS_CSV
    return csv_path.exists()


def test_dataset_test_tem_itens():
    if not _dataset_disponivel():
        pytest.skip("labels.csv do dataset ausente")
    ds = DatasetDefeitos("test")
    assert len(ds) > 0


def test_item_tem_rotulo_int_valido():
    # __getitem__ abre a imagem com Pillow; sem torchvision usamos transform no-op.
    pytest.importorskip("PIL")
    if not _dataset_disponivel():
        pytest.skip("labels.csv do dataset ausente")

    ds = DatasetDefeitos("test", transform=lambda imagem: imagem)
    if len(ds) == 0:
        pytest.skip("split de teste vazio")

    _imagem, rotulo = ds[0]
    assert isinstance(rotulo, int)
    assert 0 <= rotulo < len(config.CLASSES)
