"""Training script for the defect classifier (transfer learning).

Usage:
    python -m config.inspector.training [--epochs N] [--lr LR] [--batch B]
                                         [--out PATH] [--no-freeze]

Heavy imports are LAZY (inside functions) — this module can be imported/compiled
without torch installed.
"""
from __future__ import annotations

from pathlib import Path

from config.inspector import settings


def _evaluate(model, loader, device, num_classes: int):
    """Compute overall and per-class accuracy over a ``DataLoader``.

    Args:
        model: Trained (or in-training) ``torch.nn.Module`` to evaluate.
        loader: ``DataLoader`` yielding ``(images, targets)`` batches.
        device: ``torch.device`` the model and tensors live on.
        num_classes: Number of defect classes (used to size per-class counters).

    Returns:
        Tuple ``(accuracy, per_class)`` where ``accuracy`` is the overall
        fraction of correct predictions (``0.0`` if the loader is empty) and
        ``per_class`` is a dict mapping each class name (from
        ``settings.CLASSES``) to its accuracy rounded to 4 decimals (``0.0``
        if that class had no samples in the loader).

    Side effects:
        Puts ``model`` into eval mode (``model.eval()``); disables gradient
        tracking for the duration of the pass via ``torch.no_grad()``.
    """
    import torch

    model.eval()
    correct = 0
    total = 0
    correct_per_class = [0] * num_classes
    total_per_class = [0] * num_classes

    with torch.no_grad():
        for images, targets in loader:
            images = images.to(device)
            targets = targets.to(device)
            outputs = model(images)
            preds = outputs.argmax(dim=1)
            correct += int((preds == targets).sum().item())
            total += int(targets.size(0))
            for target, pred in zip(targets.view(-1).tolist(), preds.view(-1).tolist()):
                total_per_class[target] += 1
                if target == pred:
                    correct_per_class[target] += 1

    accuracy = correct / total if total else 0.0
    per_class = {}
    for i in range(num_classes):
        name = settings.CLASSES[i]
        per_class[name] = (
            round(correct_per_class[i] / total_per_class[i], 4) if total_per_class[i] else 0.0
        )
    return accuracy, per_class


def train(epochs: int = 10, lr: float = 1e-3, batch_size: int = 32,
          dataset_dir=settings.DATASET_DIR, out_path=settings.MODEL_PATH,
          freeze_backbone: bool = True) -> dict:
    """Train the CNN via transfer learning and save the best checkpoint.

    Args:
        epochs: Number of training epochs (full passes over the train split).
        lr: Learning rate for the ``Adam`` optimizer.
        batch_size: Batch size used to build the data loaders.
        dataset_dir: Root directory of the labeled dataset (passed through to
            ``build_loaders``). Defaults to ``settings.DATASET_DIR``.
        out_path: Destination path (``.pt``) for the saved state_dict.
            Defaults to ``settings.MODEL_PATH``. Its parent directory
            (typically ``settings.MODELS_DIR``) is created if missing.
        freeze_backbone: If ``True``, only the ``classifier`` head is trained
            (backbone weights are frozen, ``requires_grad = False``). If
            ``False``, the entire network is fine-tuned.

    Returns:
        Dict with keys:
            - ``val_acc``: best validation accuracy observed across epochs
              (rounded to 4 decimals, ``0.0`` if never improved).
            - ``test_acc``: test-set accuracy of the best checkpoint (rounded
              to 4 decimals).
            - ``per_class``: dict mapping class name to test-set accuracy.

    Side effects:
        - Loss: ``CrossEntropyLoss``; optimizer: ``Adam(lr)``.
        - Creates ``out_path``'s parent directory if it does not exist.
        - Writes the state_dict of the best (highest ``val_acc``) epoch to
          ``out_path``, overwriting any existing file there.
        - After training, reloads the best checkpoint from ``out_path`` (if
          it exists) before computing the final test accuracy.

    Failure modes:
        Requires ``torch`` to be importable (imported lazily on call); raises
        whatever ``build_loaders`` raises if the dataset is missing/invalid.
    """
    import torch
    import torch.nn as nn

    from config.inspector import network
    from config.inspector.dataset import build_loaders

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    num_classes = len(settings.CLASSES)

    model = network.build_model(num_classes=num_classes, pretrained=True)
    model.to(device)

    if freeze_backbone:
        for param in model.parameters():
            param.requires_grad = False
        for param in model.classifier.parameters():
            param.requires_grad = True
        params = [p for p in model.parameters() if p.requires_grad]
    else:
        params = list(model.parameters())

    criterion = nn.CrossEntropyLoss()
    optimizer = torch.optim.Adam(params, lr=lr)

    loaders = build_loaders(dataset_dir=dataset_dir, batch_size=batch_size)

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    best_val = -1.0
    for _ in range(epochs):
        model.train()
        for images, targets in loaders["train"]:
            images = images.to(device)
            targets = targets.to(device)
            optimizer.zero_grad()
            outputs = model(images)
            loss = criterion(outputs, targets)
            loss.backward()
            optimizer.step()

        val_acc, _ = _evaluate(model, loaders["val"], device, num_classes)
        if val_acc > best_val:
            best_val = val_acc
            torch.save(model.state_dict(), out_path)

    # Reload the best checkpoint before measuring test accuracy.
    if out_path.exists():
        model.load_state_dict(torch.load(out_path, map_location=device))
    test_acc, per_class = _evaluate(model, loaders["test"], device, num_classes)

    return {
        "val_acc": round(best_val if best_val >= 0 else 0.0, 4),
        "test_acc": round(test_acc, 4),
        "per_class": per_class,
    }


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Train the defect classifier (MobileNetV3-Small CNN)."
    )
    parser.add_argument("--epochs", type=int, default=10, help="number of epochs")
    parser.add_argument("--lr", type=float, default=1e-3, help="learning rate")
    parser.add_argument("--batch", type=int, default=32, help="batch size")
    parser.add_argument("--out", type=str, default=str(settings.MODEL_PATH),
                        help="output path for the model (.pt)")
    parser.add_argument("--no-freeze", action="store_true",
                        help="also train the backbone (full fine-tuning)")
    args = parser.parse_args()

    metrics = train(
        epochs=args.epochs,
        lr=args.lr,
        batch_size=args.batch,
        out_path=args.out,
        freeze_backbone=not args.no_freeze,
    )

    print("Final metrics:")
    print(f"  val_acc : {metrics['val_acc']}")
    print(f"  test_acc: {metrics['test_acc']}")
    print("  per class:")
    for name, acc in metrics["per_class"].items():
        print(f"    {name}: {acc}")
    print(f"Model saved to: {args.out}")
