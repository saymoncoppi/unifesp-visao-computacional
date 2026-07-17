"""Convolutional neural network (CNN) for print defect classification.

Uses transfer learning on top of MobileNetV3-Small (torchvision). All heavy imports
(torch/torchvision/PIL/numpy) are LAZY — they live inside the functions — so that the
package can be imported and `python -m py_compile` can pass even without those libs
installed.
"""
from __future__ import annotations

from pathlib import Path

from config.inspector import settings


def _device(device=None):
    """Resolve the execution device (CPU/GPU).

    Args:
        device: Explicit device spec (e.g. ``"cpu"``, ``"cuda"``) or ``None`` to
            auto-detect: uses CUDA when available, otherwise CPU.

    Returns:
        torch.device: The resolved device.

    Side effects:
        Imports torch lazily (only when called).
    """
    import torch

    if device is None:
        return torch.device("cuda" if torch.cuda.is_available() else "cpu")
    return torch.device(device)


def build_model(num_classes: int = len(settings.CLASSES),
                backbone: str = settings.BACKBONE,
                pretrained: bool = True):
    """Build the defect classification CNN (MobileNetV3-Small).

    Loads the backbone (with ImageNet weights if ``pretrained``) and replaces the
    last ``Linear`` layer of the ``classifier`` with a new one having ``num_classes``
    outputs.

    Args:
        num_classes: Number of output classes for the final linear layer. Defaults
            to ``len(settings.CLASSES)``.
        backbone: Backbone architecture name. Currently informational only — the
            implementation always instantiates MobileNetV3-Small.
        pretrained: Whether to initialize the backbone with ImageNet weights.

    Returns:
        torch.nn.Module: The constructed (untrained-head) model.

    Side effects:
        Imports torch.nn and torchvision.models lazily.
    """
    import torch.nn as nn
    from torchvision import models

    weights = None
    if pretrained:
        try:
            weights = models.MobileNet_V3_Small_Weights.DEFAULT
        except AttributeError:          # old torchvision, no weights enum
            weights = None

    try:
        model = models.mobilenet_v3_small(weights=weights)
    except TypeError:                    # legacy API uses `pretrained=`
        model = models.mobilenet_v3_small(pretrained=pretrained)

    # The last layer of the classifier is the final Linear (in_features -> 1000 on ImageNet).
    in_features = model.classifier[-1].in_features
    model.classifier[-1] = nn.Linear(in_features, num_classes)
    return model


def build_transforms(train: bool = False):
    """Build the image preprocessing pipeline.

    Resizes to ``IMG_SIZE``; when ``train`` is set, applies light augmentation
    (rotation and color jitter); converts to 3 grayscale channels, tensorizes and
    normalizes using ImageNet statistics (``settings.MEAN`` / ``settings.STD``).

    Args:
        train: If ``True``, includes training-time augmentation (random rotation
            and color jitter). If ``False``, returns the plain inference pipeline.

    Returns:
        torchvision.transforms.Compose: The composed transform pipeline.

    Side effects:
        Imports torchvision.transforms lazily.
    """
    from torchvision import transforms

    steps = [transforms.Resize((settings.IMG_SIZE, settings.IMG_SIZE))]
    if train:
        steps += [
            transforms.RandomRotation(8),
            transforms.ColorJitter(brightness=0.2, contrast=0.2),
        ]
    steps += [
        transforms.Grayscale(num_output_channels=3),
        transforms.ToTensor(),
        transforms.Normalize(settings.MEAN, settings.STD),
    ]
    return transforms.Compose(steps)


def load_model(path=settings.MODEL_PATH, device=None):
    """Load the trained classifier from ``path`` (state_dict).

    Builds the architecture, loads the weights with ``map_location`` on the chosen
    device, and puts the model in evaluation mode.

    Args:
        path: Path to the state_dict file. Defaults to ``settings.MODEL_PATH``.
        device: Device spec to load the model onto, or ``None`` to auto-detect
            (see :func:`_device`).

    Returns:
        torch.nn.Module: The loaded model in eval mode.

    Raises:
        FileNotFoundError: If ``path`` does not exist, with a hint on how to train
            the model.

    Side effects:
        Imports torch lazily.
    """
    import torch

    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(
            f"Model not found at '{path}'. "
            "Train it first with: python -m config.inspector.training"
        )

    disp = _device(device)
    model = build_model(pretrained=False)   # weights come from the state_dict
    state = torch.load(path, map_location=disp)
    model.load_state_dict(state)
    model.to(disp)
    model.eval()
    return model


def predict(path_or_img, model=None, device=None, roi=None, fit=False) -> dict:
    """Classify the defect of a label image.

    Accepts a path (str/Path), a ``numpy.ndarray`` or a PIL image. Applies the
    inference preprocessing, runs softmax, and returns per-class probabilities.
    Degrades gracefully: if torch/torchvision/PIL are missing OR the model does not
    exist, returns ``class=None`` with the ``error`` field filled in (does not
    raise).

    Args:
        path_or_img: Image source — a filesystem path (str/Path), a
            ``numpy.ndarray``, or a PIL ``Image``.
        model: Pre-loaded model to use for inference. If ``None``, loads the
            default model via :func:`load_model`.
        device: Device spec to run inference on, or ``None`` to auto-detect.

    Returns:
        dict: With keys ``class`` (predicted class key or ``None`` on failure),
            ``class_label`` (Portuguese display label for the class, or ``None``),
            ``confidence`` (float, top-class probability), ``probs`` (dict mapping
            each class key to its probability), and ``error`` (``None`` on success,
            otherwise a descriptive message).

    Side effects:
        Imports torch, PIL and numpy lazily. May load the default model from disk
        the first time it's needed.
    """
    def _error(msg: str) -> dict:
        return {"class": None, "class_label": None, "confidence": 0.0, "probs": {}, "error": msg}

    try:
        import torch
        from PIL import Image
    except ImportError as exc:
        return _error(f"missing dependency (torch/torchvision/PIL): {exc}")

    try:
        disp = _device(device)

        if model is None:
            model = load_model(device=disp)

        # Normalize the input to an RGB PIL image.
        if isinstance(path_or_img, Image.Image):
            image = path_or_img.convert("RGB")
        elif isinstance(path_or_img, (str, Path)):
            image = Image.open(path_or_img).convert("RGB")
        else:
            import numpy as np
            image = Image.fromarray(np.asarray(path_or_img)).convert("RGB")

        # Optional (fit=True): segment the code + fit-to-fill canvas to mirror the
        # training preprocessing. This removes the "small code on background ->
        # registration_shift" artifact on raw photos, BUT it DESTROYS positional
        # defects (cutoff / registration_shift depend on the code's position and
        # extent in the frame) and drops in-distribution accuracy 96.5% -> 69%.
        # So it is OFF by default; the real fix for raw-photo robustness is
        # training-side framing augmentation, not inference-time cropping.
        # Any failure here silently degrades to the raw image -- never raises.
        if fit:
            try:
                from config.inspector import vision
                prepared = vision.prepare_for_cnn(path_or_img, roi=roi)
                if prepared is not None:
                    image = prepared.convert("RGB")
            except Exception:
                pass

        tensor = build_transforms(False)(image).unsqueeze(0).to(disp)
        with torch.no_grad():
            logits = model(tensor)
            probs = torch.softmax(logits, dim=1)[0]

        idx = int(torch.argmax(probs).item())
        class_key = settings.CLASSES[idx]
        probs_dict = {
            settings.CLASSES[i]: round(float(probs[i].item()), 4)
            for i in range(len(settings.CLASSES))
        }
        return {
            "class": class_key,
            "class_label": settings.CLASS_LABELS_PT.get(class_key, class_key),
            "confidence": round(float(probs[idx].item()), 4),
            "probs": probs_dict,
            "error": None,
        }
    except FileNotFoundError as exc:
        return _error(str(exc))
    except Exception as exc:                          # graceful degradation
        return _error(f"prediction failed: {exc}")
