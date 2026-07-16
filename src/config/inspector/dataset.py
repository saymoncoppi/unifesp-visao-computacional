"""PyTorch dataset for the labeled label images.

Reads ``settings.LABELS_CSV`` (columns: filename,split,classe,simbologia,payload,params),
filters by split, and yields ``(transformed_image, class_index)`` pairs. The class
index follows the ORDER of ``settings.CLASSES``.

Note: to respect the LAZY import rule (torch never at module top level), the
``DefectDataset`` class does NOT inherit from ``torch.utils.data.Dataset`` — it is a
map-style dataset compatible by duck typing (implements ``__len__`` and
``__getitem__``), which is all a ``DataLoader`` needs.
"""
from __future__ import annotations

import csv
from pathlib import Path

from config.inspector import settings


class DefectDataset:
    """Print-defect dataset, filtered by split.

    Parameters
    ----------
    split : str
        "train", "val" or "test".
    dataset_dir : Path
        Dataset root; ``filename`` in the CSV is relative to it.
    transform : callable | None
        Transformation applied to the PIL image. If ``None``, uses
        ``network.build_transforms(train=split == "train")``.

    Attributes
    ----------
    class_to_index : dict[str, int]
        Maps each class key (``settings.CLASSES``) to its integer index.
    rows : list[dict]
        CSV rows (as dicts) belonging to the requested split.

    Failure modes
    -------------
    Raises ``FileNotFoundError`` if neither ``<dataset_dir>/labels.csv`` nor
    ``settings.LABELS_CSV`` exists. Raises ``KeyError`` in ``__getitem__`` if a
    row's "classe" value is not present in ``settings.CLASSES``.
    """

    def __init__(self, split: str = "train", dataset_dir=settings.DATASET_DIR, transform=None):
        self.split = split
        self.dataset_dir = Path(dataset_dir)
        self.transform = transform
        self.class_to_index = {defect_class: i for i, defect_class in enumerate(settings.CLASSES)}

        csv_path = self.dataset_dir / "labels.csv"
        if not csv_path.exists():
            csv_path = Path(settings.LABELS_CSV)

        self.rows: list[dict] = []
        with open(csv_path, newline="", encoding="utf-8") as file:
            reader = csv.DictReader(file)
            for row in reader:
                if row.get("split") == split:
                    self.rows.append(row)

    def _ensure_transform(self):
        """Resolve the default transform (lazily) when none was provided.

        Returns
        -------
        callable
            The transform to apply to PIL images: ``self.transform`` if it was
            set explicitly, otherwise a freshly built
            ``network.build_transforms(train=...)`` cached on ``self.transform``.

        Side effects
        ------------
        Imports ``config.inspector.network`` lazily and mutates
        ``self.transform`` the first time it is called with no explicit
        transform.
        """
        if self.transform is None:
            from config.inspector import network
            self.transform = network.build_transforms(train=self.split == "train")
        return self.transform

    def __len__(self) -> int:
        return len(self.rows)

    def __getitem__(self, index: int):
        from PIL import Image

        row = self.rows[index]
        path = self.dataset_dir / row["filename"]
        image = Image.open(path).convert("RGB")
        image = self._ensure_transform()(image)
        target = self.class_to_index[row["classe"]]
        return image, target


def build_loaders(dataset_dir=settings.DATASET_DIR, batch_size: int = 32, num_workers: int = 2) -> dict:
    """Build the train, validation, and test ``DataLoader`` objects.

    Parameters
    ----------
    dataset_dir : Path
        Dataset root passed through to each ``DefectDataset`` split.
    batch_size : int
        Batch size used by every ``DataLoader``.
    num_workers : int
        Number of worker processes used by every ``DataLoader``.

    Returns
    -------
    dict
        ``{"train": DataLoader, "val": DataLoader, "test": DataLoader}``.

    Side effects
    ------------
    Applies augmentation only to the train split (which is also the only one
    shuffled). Imports ``torch`` and ``config.inspector.network`` lazily.
    """
    from torch.utils.data import DataLoader
    from config.inspector import network

    loaders = {}
    for split in ("train", "val", "test"):
        is_train = split == "train"
        dataset_split = DefectDataset(
            split=split,
            dataset_dir=dataset_dir,
            transform=network.build_transforms(train=is_train),
        )
        loaders[split] = DataLoader(
            dataset_split,
            batch_size=batch_size,
            shuffle=is_train,
            num_workers=num_workers,
        )
    return loaders
