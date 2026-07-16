"""Experiment harness for the print-defect classifier.

Reproducibly runs the rigor experiments requested by the article's evaluation:

  E1      - fixed split (train/val/test from ``labels.csv``): trains each
            architecture, selects the best one by validation accuracy, and
            measures the full metrics on the test set (accuracy,
            per-class and macro precision/recall/F1, and the confusion
            matrix). Saves the test predictions for the statistical tests.

  E-BASE  - comparison against baselines (ResNet18 and EfficientNet-B0)
            under the exact same protocol as our CNN (MobileNetV3-Small):
            same data, splits, augmentation, and hyperparameters. Also
            reports the parameter count and average inference latency
            (CPU).

  E-KFOLD - stratified k-fold cross-validation over the 630 images
            (aggregating all splits), reporting mean +/- standard
            deviation of accuracy and macro F1 per architecture.

  E-STAT  - McNemar's test (exact binomial) between our CNN and each
            baseline, over the fixed test set, to check statistical
            significance.

Experiment E3 (multi-agent ADK vs. monolithic) is NOT run here: the
orchestrated path depends on a ``GOOGLE_API_KEY`` (Gemini), which is absent
in the evaluation environment. Classification is identical on both paths
(same CNN tool); the orchestration comparison is recorded as a
limitation/future work.

Usage:
    python -m config.experiments [--epochs N] [--lr LR] [--batch B]
                                  [--kfolds K] [--seed S] [--quick]
                                  [--out DIR]

All heavy imports (torch/torchvision/PIL) are LAZY.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import time
from pathlib import Path

from config.inspector import settings

RESULTS_DIR = settings.ROOT / "config" / "results"

# Architectures evaluated: label -> (torchvision name, is our proposal?)
ARCHITECTURES = [
    ("MobileNetV3-Small", "mobilenet_v3_small", True),
    ("ResNet18", "resnet18", False),
    ("EfficientNet-B0", "efficientnet_b0", False),
]


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------
def read_rows(dataset_dir=settings.DATASET_DIR) -> list[dict]:
    """Read ``labels.csv`` and return its rows.

    Args:
        dataset_dir: Directory containing ``labels.csv``. Defaults to
            ``settings.DATASET_DIR``.

    Returns:
        A list of dicts, one per CSV row, each with (at least) the
        ``filename``, ``split``, and ``classe`` keys (the CSV header keys
        are kept as-is; ``classe`` values are the English defect-class
        keys).
    """
    dataset_dir = Path(dataset_dir)
    csv_path = dataset_dir / "labels.csv"
    rows = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            rows.append(row)
    return rows


class RowDataset:
    """Map-style dataset built from a list of CSV rows.

    Duck-type compatible with ``torch.utils.data.DataLoader`` (implements
    ``__len__`` and ``__getitem__``), like the rest of the project.

    Attributes:
        rows: List of CSV row dicts (``filename``/``classe`` keys).
        dataset_dir: Root directory the ``filename`` paths are relative to.
        transform: torchvision transform pipeline applied to each image.
        class_to_index: Mapping from defect-class key to integer label.
    """

    def __init__(self, rows, dataset_dir, train: bool):
        """Build the dataset.

        Args:
            rows: List of CSV row dicts to expose as dataset items.
            dataset_dir: Directory the ``filename`` values are relative to.
            train: Whether to build the training (augmented) transform
                pipeline or the eval (deterministic) one.
        """
        from config.inspector import network

        self.rows = rows
        self.dataset_dir = Path(dataset_dir)
        self.transform = network.build_transforms(train=train)
        self.class_to_index = {c: i for i, c in enumerate(settings.CLASSES)}

    def __len__(self):
        return len(self.rows)

    def __getitem__(self, i):
        from PIL import Image

        row = self.rows[i]
        img = Image.open(self.dataset_dir / row["filename"]).convert("RGB")
        return self.transform(img), self.class_to_index[row["classe"]]


def _build_loader(rows, dataset_dir, train, batch_size, num_workers=2):
    """Build a ``DataLoader`` over ``rows``.

    Args:
        rows: List of CSV row dicts.
        dataset_dir: Directory the ``filename`` values are relative to.
        train: Whether this is the training split (enables shuffling and
            the augmented transform pipeline).
        batch_size: Batch size for the loader.
        num_workers: Number of worker processes for data loading.

    Returns:
        A ``torch.utils.data.DataLoader`` wrapping a ``RowDataset``.
    """
    from torch.utils.data import DataLoader

    return DataLoader(
        RowDataset(rows, dataset_dir, train),
        batch_size=batch_size,
        shuffle=train,
        num_workers=num_workers,
    )


# ---------------------------------------------------------------------------
# Model (our CNN + baselines) under the SAME protocol
# ---------------------------------------------------------------------------
def build_torchvision_model(tv_name: str, num_classes: int, pretrained: bool = True):
    """Build a torchvision architecture with its head replaced for num_classes.

    Args:
        tv_name: torchvision model identifier, one of
            ``"mobilenet_v3_small"``, ``"resnet18"``, ``"efficientnet_b0"``.
        num_classes: Number of output classes for the replaced head.
        pretrained: Whether to load ImageNet-pretrained weights before
            replacing the head.

    Returns:
        The instantiated ``torch.nn.Module``.

    Raises:
        ValueError: If ``tv_name`` is not one of the supported identifiers.
    """
    import torch.nn as nn
    from torchvision import models

    if tv_name == "mobilenet_v3_small":
        weights = models.MobileNet_V3_Small_Weights.DEFAULT if pretrained else None
        model = models.mobilenet_v3_small(weights=weights)
        model.classifier[-1] = nn.Linear(model.classifier[-1].in_features, num_classes)
    elif tv_name == "resnet18":
        weights = models.ResNet18_Weights.DEFAULT if pretrained else None
        model = models.resnet18(weights=weights)
        model.fc = nn.Linear(model.fc.in_features, num_classes)
    elif tv_name == "efficientnet_b0":
        weights = models.EfficientNet_B0_Weights.DEFAULT if pretrained else None
        model = models.efficientnet_b0(weights=weights)
        model.classifier[-1] = nn.Linear(model.classifier[-1].in_features, num_classes)
    else:
        raise ValueError(f"unknown architecture: {tv_name}")
    return model


def _num_params(model) -> int:
    """Return the total number of parameters (trainable + frozen) in model."""
    return sum(p.numel() for p in model.parameters())


def _seed(seed: int):
    """Seed Python's ``random``, ``numpy``, and ``torch`` for reproducibility."""
    import random

    import numpy as np
    import torch

    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)


def train_and_predict(tv_name, train, val, test, dataset_dir,
                       epochs, lr, batch, seed):
    """Train (full fine-tuning) and return predictions on ``test``.

    Selects the best state by validation accuracy (when ``val`` is given);
    otherwise uses the final state.

    Args:
        tv_name: torchvision model identifier passed to
            ``build_torchvision_model``.
        train: List of CSV row dicts for the training split.
        val: List of CSV row dicts for the validation split, or a falsy
            value to skip validation-based model selection.
        test: List of CSV row dicts for the test split.
        dataset_dir: Directory the ``filename`` values are relative to.
        epochs: Number of training epochs.
        lr: Learning rate for the Adam optimizer.
        batch: Batch size for all loaders.
        seed: Random seed for reproducibility (see ``_seed``).

    Returns:
        A dict with:
            y_true: Ground-truth labels for the test set.
            y_pred: Predicted labels for the test set.
            val_acc: Best validation accuracy achieved, or ``None`` if
                ``val`` was not provided.
            n_params: Total parameter count of the trained model.
            latency_ms: Average inference latency per image, in
                milliseconds.
    """
    import torch
    import torch.nn as nn

    _seed(seed)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    num_classes = len(settings.CLASSES)

    model = build_torchvision_model(tv_name, num_classes, pretrained=True).to(device)
    criterion = nn.CrossEntropyLoss()
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)  # full fine-tuning

    train_loader = _build_loader(train, dataset_dir, True, batch)
    val_loader = _build_loader(val, dataset_dir, False, batch) if val else None
    test_loader = _build_loader(test, dataset_dir, False, batch)

    def accuracy(loader):
        model.eval()
        correct = total = 0
        with torch.no_grad():
            for x, y in loader:
                x, y = x.to(device), y.to(device)
                p = model(x).argmax(1)
                correct += int((p == y).sum().item())
                total += int(y.size(0))
        return correct / total if total else 0.0

    best_val = -1.0
    best_state = None
    for _ in range(epochs):
        model.train()
        for x, y in train_loader:
            x, y = x.to(device), y.to(device)
            optimizer.zero_grad()
            loss = criterion(model(x), y)
            loss.backward()
            optimizer.step()
        if val_loader is not None:
            va = accuracy(val_loader)
            if va > best_val:
                best_val = va
                best_state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}

    if best_state is not None:
        model.load_state_dict(best_state)

    # Test predictions + inference latency.
    model.eval()
    y_true, y_pred = [], []
    t0 = time.perf_counter()
    n_images = 0
    with torch.no_grad():
        for x, y in test_loader:
            x = x.to(device)
            p = model(x).argmax(1).cpu().tolist()
            y_pred.extend(p)
            y_true.extend(y.tolist())
            n_images += len(y)
    latency_ms = 1000.0 * (time.perf_counter() - t0) / max(n_images, 1)

    return {
        "y_true": y_true,
        "y_pred": y_pred,
        "val_acc": round(best_val, 4) if best_val >= 0 else None,
        "n_params": _num_params(model),
        "latency_ms": round(latency_ms, 2),
    }


# ---------------------------------------------------------------------------
# Metrics (pure numpy -- no sklearn)
# ---------------------------------------------------------------------------
def confusion_matrix(y_true, y_pred, k):
    """Build a k x k confusion matrix (rows=true, cols=predicted).

    Args:
        y_true: Ground-truth integer labels.
        y_pred: Predicted integer labels.
        k: Number of classes.

    Returns:
        A ``numpy.ndarray`` of shape ``(k, k)`` with integer counts.
    """
    import numpy as np

    M = np.zeros((k, k), dtype=int)
    for t, p in zip(y_true, y_pred):
        M[t, p] += 1
    return M


def metrics(y_true, y_pred):
    """Compute accuracy, per-class and macro P/R/F1, and the confusion matrix.

    Args:
        y_true: Ground-truth integer labels.
        y_pred: Predicted integer labels.

    Returns:
        A dict with:
            accuracy: Overall accuracy.
            macro_precision: Unweighted mean of per-class precision.
            macro_recall: Unweighted mean of per-class recall.
            macro_f1: Unweighted mean of per-class F1.
            per_class: Dict keyed by class name, each value a dict with
                ``precision``, ``recall``, ``f1``, and ``n`` (support).
            confusion_matrix: The confusion matrix as a nested list.
    """
    import numpy as np

    k = len(settings.CLASSES)
    M = confusion_matrix(y_true, y_pred, k)
    total = M.sum()
    acc = float(np.trace(M) / total) if total else 0.0

    per_class = {}
    precisions, recalls, f1s = [], [], []
    for i in range(k):
        tp = int(M[i, i])
        fp = int(M[:, i].sum() - tp)
        fn = int(M[i, :].sum() - tp)
        prec = tp / (tp + fp) if (tp + fp) else 0.0
        rec = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0
        per_class[settings.CLASSES[i]] = {
            "precision": round(prec, 4), "recall": round(rec, 4),
            "f1": round(f1, 4), "n": int(M[i, :].sum()),
        }
        precisions.append(prec); recalls.append(rec); f1s.append(f1)

    return {
        "accuracy": round(acc, 4),
        "macro_precision": round(float(np.mean(precisions)), 4),
        "macro_recall": round(float(np.mean(recalls)), 4),
        "macro_f1": round(float(np.mean(f1s)), 4),
        "per_class": per_class,
        "confusion_matrix": M.tolist(),
    }


def mcnemar(y_true, pred_a, pred_b):
    """McNemar's test (two-tailed exact binomial) between two classifiers.

    Args:
        y_true: Ground-truth integer labels.
        pred_a: Predictions from classifier A.
        pred_b: Predictions from classifier B.

    Returns:
        A dict with:
            b: Count of items where A is correct and B is wrong.
            c: Count of items where B is correct and A is wrong.
            p_value: Two-tailed exact binomial p-value (n=b+c, p=0.5),
                robust for small samples (does not require scipy).
    """
    b = c = 0
    for t, a, bb in zip(y_true, pred_a, pred_b):
        a_ok, b_ok = (a == t), (bb == t)
        if a_ok and not b_ok:
            b += 1
        elif b_ok and not a_ok:
            c += 1
    n = b + c
    if n == 0:
        return {"b": b, "c": c, "p_value": 1.0}
    smaller = min(b, c)
    # two-tailed p = 2 * P(X <= smaller), X ~ Binomial(n, 0.5), truncated at 1.0
    tail = sum(math.comb(n, i) for i in range(smaller + 1)) / (2 ** n)
    p = min(1.0, 2 * tail)
    return {"b": b, "c": c, "p_value": round(p, 5)}


# ---------------------------------------------------------------------------
# Stratified k-fold (manual)
# ---------------------------------------------------------------------------
def stratified_folds(rows, k, seed):
    """Split rows into k class-stratified folds.

    Args:
        rows: List of CSV row dicts (each with a ``classe`` key).
        k: Number of folds.
        seed: Random seed for shuffling within each class.

    Returns:
        A list of k lists of row dicts, with each class's rows distributed
        as evenly as possible across the folds.
    """
    import random

    rng = random.Random(seed)
    by_class: dict[str, list] = {}
    for r in rows:
        by_class.setdefault(r["classe"], []).append(r)

    folds = [[] for _ in range(k)]
    for _class_key, items in by_class.items():
        items = items[:]
        rng.shuffle(items)
        for idx, item in enumerate(items):
            folds[idx % k].append(item)
    return folds


# ---------------------------------------------------------------------------
# Experiment orchestration
# ---------------------------------------------------------------------------
def run(epochs, lr, batch, kfolds, seed, out_dir, quick=False, kfold_all=False):
    """Run the full experiment suite (E1 + baselines, McNemar, k-fold).

    Trains each architecture on the fixed split, records test metrics and
    predictions, runs McNemar's test between our CNN and each baseline, then
    runs stratified k-fold cross-validation (by default only for our
    proposed architecture). Results are written incrementally to
    ``out_dir/resultados.json`` after each architecture/fold so partial
    progress is never lost.

    Args:
        epochs: Number of training epochs per model.
        lr: Learning rate for the Adam optimizer.
        batch: Batch size for all loaders.
        kfolds: Number of folds for the k-fold cross-validation.
        seed: Base random seed for reproducibility.
        out_dir: Directory to write ``resultados.json`` into (created if
            missing).
        quick: If True, only run the proposed architecture (debug/timing
            runs) instead of the full architecture list.
        kfold_all: If True, run k-fold cross-validation for every
            architecture instead of only the proposed one (much more
            expensive on CPU).

    Returns:
        The results dict, matching what is written to ``resultados.json``.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    rows = read_rows()
    train_rows = [r for r in rows if r["split"] == "train"]
    val_rows = [r for r in rows if r["split"] == "val"]
    test_rows = [r for r in rows if r["split"] == "test"]

    archs = ARCHITECTURES[:1] if quick else ARCHITECTURES

    results = {
        "config": {
            "epochs": epochs, "lr": lr, "batch": batch, "kfolds": kfolds,
            "seed": seed, "n_train": len(train_rows), "n_val": len(val_rows),
            "n_test": len(test_rows), "classes": settings.CLASSES,
        },
        "fixed_split": {},
        "kfold": {},
        "mcnemar": {},
    }

    # ---- E1 + baselines on the fixed split ----
    predictions = {}
    for label, tv_name, _ in archs:
        print(f"[fixed-split] training {label} ...", flush=True)
        t0 = time.time()
        r = train_and_predict(tv_name, train_rows, val_rows, test_rows, settings.DATASET_DIR,
                               epochs, lr, batch, seed)
        m = metrics(r["y_true"], r["y_pred"])
        m.update({
            "val_acc": r["val_acc"], "n_params": r["n_params"],
            "latency_ms": r["latency_ms"], "train_time_s": round(time.time() - t0, 1),
        })
        results["fixed_split"][label] = m
        predictions[label] = (r["y_true"], r["y_pred"])
        print(f"[fixed-split] {label}: acc={m['accuracy']} macroF1={m['macro_f1']} "
              f"({m['train_time_s']}s)", flush=True)
        # incremental save
        (out_dir / "resultados.json").write_text(
            json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")

    # ---- McNemar: our CNN vs. each baseline (same test set) ----
    if "MobileNetV3-Small" in predictions:
        yt, yp_ours = predictions["MobileNetV3-Small"]
        for label, (_, yp_base) in predictions.items():
            if label == "MobileNetV3-Small":
                continue
            results["mcnemar"][f"MobileNetV3-Small vs {label}"] = mcnemar(yt, yp_ours, yp_base)

    # ---- E-KFOLD stratified ----
    # By default, k-fold validation only runs for the proposed architecture
    # (stability of our model); baselines are compared on the fixed test set
    # + McNemar instead. Use --kfold-all to run k-fold on every architecture
    # (much more expensive on CPU).
    kfold_archs = archs if kfold_all else [a for a in archs if a[2]]
    folds = stratified_folds(rows, kfolds, seed)
    for label, tv_name, _ in kfold_archs:
        accs, f1s = [], []
        for i in range(kfolds):
            test_fold = folds[i]
            train_fold = [x for j in range(kfolds) if j != i for x in folds[j]]
            print(f"[kfold] {label} fold {i + 1}/{kfolds} ...", flush=True)
            r = train_and_predict(tv_name, train_fold, None, test_fold, settings.DATASET_DIR,
                                   epochs, lr, batch, seed + i)
            m = metrics(r["y_true"], r["y_pred"])
            accs.append(m["accuracy"]); f1s.append(m["macro_f1"])
        import numpy as np
        results["kfold"][label] = {
            "accuracy_mean": round(float(np.mean(accs)), 4),
            "accuracy_std": round(float(np.std(accs)), 4),
            "f1_mean": round(float(np.mean(f1s)), 4),
            "f1_std": round(float(np.std(f1s)), 4),
            "accuracies": [round(a, 4) for a in accs],
            "f1s": [round(f, 4) for f in f1s],
        }
        print(f"[kfold] {label}: acc={results['kfold'][label]['accuracy_mean']}"
              f"+/-{results['kfold'][label]['accuracy_std']}", flush=True)
        (out_dir / "resultados.json").write_text(
            json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")

    (out_dir / "resultados.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nResults saved to {out_dir / 'resultados.json'}", flush=True)
    return results


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Rigor experiments for the classifier.")
    p.add_argument("--epochs", type=int, default=40)
    p.add_argument("--lr", type=float, default=5e-4)
    p.add_argument("--batch", type=int, default=32)
    p.add_argument("--kfolds", type=int, default=5)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--quick", action="store_true", help="only our CNN (debug/timing)")
    p.add_argument("--kfold-all", action="store_true",
                   help="run k-fold on every architecture (expensive on CPU)")
    p.add_argument("--out", type=str, default=str(RESULTS_DIR))
    a = p.parse_args()
    run(a.epochs, a.lr, a.batch, a.kfolds, a.seed, a.out, a.quick, a.kfold_all)
