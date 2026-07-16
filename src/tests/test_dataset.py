"""Tests for config.inspector.dataset (map-style, duck-typed Dataset).

``DefectDataset`` does NOT inherit from ``torch.utils.data.Dataset`` (it is
duck-typed), so construction and ``__len__`` do not require torch. To fetch an
item we use a no-op transform (avoiding ``torchvision``): this way only
Pillow is needed to open the image.
"""
from __future__ import annotations

import pytest

from config.inspector import settings
from config.inspector.dataset import DefectDataset


def _dataset_available() -> bool:
    csv_path = settings.DATASET_DIR / "labels.csv"
    if not csv_path.exists():
        csv_path = settings.LABELS_CSV
    return csv_path.exists()


def test_dataset_test_split_has_items():
    if not _dataset_available():
        pytest.skip("dataset labels.csv missing")
    ds = DefectDataset("test")
    assert len(ds) > 0


def test_item_has_valid_int_label():
    # __getitem__ opens the image with Pillow; without torchvision we use a no-op transform.
    pytest.importorskip("PIL")
    if not _dataset_available():
        pytest.skip("dataset labels.csv missing")

    ds = DefectDataset("test", transform=lambda image: image)
    if len(ds) == 0:
        pytest.skip("test split is empty")

    _image, label = ds[0]
    assert isinstance(label, int)
    assert 0 <= label < len(settings.CLASSES)
