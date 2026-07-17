"""Central project configuration (constants shared by every module).

This module defines filesystem paths, the defect-class taxonomy, the CNN
input normalization constants, and small language/Gemini helper functions
used throughout the ``config.inspector`` package (vision, network, training,
diagnosis, report, tools, agents) and by the ``app`` package (API/CLI).

Side effects on import:
    - Attempts to load environment variables from a ``.env`` file located at
      the project ``ROOT`` (see below). If ``python-dotenv`` is not
      installed, or the file does not exist, this is silently ignored so the
      module remains importable in minimal environments (e.g. CI).
"""
from __future__ import annotations

import os
from pathlib import Path

# --------------------------------------------------------------------------
# Paths
# --------------------------------------------------------------------------
# This file lives at src/config/inspector/settings.py, so ROOT (the project
# "src" root) is two levels up: config/inspector -> config -> src.
ROOT = Path(__file__).resolve().parents[2]                 # .../src
PROJECT_ROOT = ROOT.parent                                  # .../repo root

# Load variables from a .env file (e.g. GOOGLE_API_KEY), if present. We look in
# both the repo root and src/ so the key is found regardless of where the file
# lives; an already-set environment variable always wins (override=False).
try:
    from dotenv import load_dotenv
    for _env_path in (PROJECT_ROOT / ".env", ROOT / ".env"):
        load_dotenv(_env_path, override=False)
except Exception:
    pass

# Resolve a path from an env var: absolute paths are used as-is; RELATIVE paths
# are resolved against ROOT (src/), so a .env value like
# ``MODEL_PATH=config/models/modelo_v1.pt`` works regardless of the current
# working directory. An unset/empty var falls back to ``default``.
def _resolve_path(env_value, default):
    if not env_value:
        return default
    p = Path(env_value)
    return p if p.is_absolute() else (ROOT / p)


MODELS_DIR = ROOT / "config" / "models"
# Dataset lives inside the project at: src/config/datasets/
DATASET_DIR = _resolve_path(os.environ.get("DATASET_DIR"), ROOT / "config" / "datasets" / "dataset_sintetico")
LABELS_CSV = DATASET_DIR / "labels.csv"
MODEL_PATH = _resolve_path(os.environ.get("MODEL_PATH"), MODELS_DIR / "classificador_defeitos.pt")

# --------------------------------------------------------------------------
# Defect classes (same taxonomy as generate_dataset.py)
# ORDER defines the index used by the CNN — do not reorder without retraining.
# --------------------------------------------------------------------------
# NOTE: restored to the v1 7-class taxonomy for the app (the 10-class v2 model,
# trained on 13k real-based images, collapsed to `registration_shift` on real
# photos because the added positional classes act as a sink). The v2 model is
# preserved in scratchpad; to switch back, restore the 10-class list + the v2
# model and keep it in sync with generate_dataset.CLASSES.
CLASSES = [
    "no_defect",
    "damaged_printhead_element",
    "wrinkled_ribbon",
    "burnt_spot",
    "light_print",
    "uneven_pressure",
    "dirty_printhead",
]

# The "defect-free" class key (used to short-circuit the diagnosis: a label with
# no defect has no probable cause / corrective action to report).
NO_DEFECT_CLASS = "no_defect"

CLASS_LABELS_PT = {
    "no_defect": "Sem defeito",
    "damaged_printhead_element": "Elemento da cabeça danificado",
    "wrinkled_ribbon": "Ribbon enrugado",
    "burnt_spot": "Ponto queimado (darkness alto)",
    "light_print": "Impressão clara (darkness baixo)",
    "uneven_pressure": "Pressão desigual da cabeça",
    "dirty_printhead": "Cabeça de impressão suja (voids)",
    "smear": "Borrão (smear)",
    "cutoff": "Impressão cortada (cutoff)",
    "registration_shift": "Perda de registro (deslocamento)",
}

# Display names in English (same taxonomy as CLASSES).
CLASS_LABELS_EN = {
    "no_defect": "No defect",
    "damaged_printhead_element": "Damaged printhead element",
    "wrinkled_ribbon": "Wrinkled ribbon",
    "burnt_spot": "Burnt spot (high darkness)",
    "light_print": "Light print (low darkness)",
    "uneven_pressure": "Uneven printhead pressure",
    "dirty_printhead": "Dirty printhead (voids)",
    "smear": "Smear (dragged ink)",
    "cutoff": "Cutoff (truncated print)",
    "registration_shift": "Registration shift",
}

# --------------------------------------------------------------------------
# Languages supported by the interface / report
# --------------------------------------------------------------------------
LANGUAGES = ("pt-BR", "en-US")
DEFAULT_LANGUAGE = "pt-BR"


def normalize_language(language: str | None) -> str:
    """Normalize a language code to one of the supported languages.

    Parameters:
        language: Candidate language code (e.g. ``"pt-BR"``, ``"en-US"``),
            or ``None``.

    Returns:
        ``language`` unchanged if it is one of ``LANGUAGES``; otherwise the
        fallback ``DEFAULT_LANGUAGE`` (``"pt-BR"``).

    Side effects:
        None (pure function).
    """
    return language if language in LANGUAGES else DEFAULT_LANGUAGE


def class_display_name(defect_class: str | None, language: str = DEFAULT_LANGUAGE) -> str:
    """Return the human-readable display name for a defect class.

    Parameters:
        defect_class: One of the keys in ``CLASSES`` (e.g. ``"no_defect"``),
            or ``None``/empty when no class is available.
        language: Requested display language; normalized via
            ``normalize_language`` (fallback: ``DEFAULT_LANGUAGE``).

    Returns:
        The localized label for ``defect_class`` from ``CLASS_LABELS_EN`` or
        ``CLASS_LABELS_PT`` depending on the normalized language. If
        ``defect_class`` is falsy, returns ``"—"``. If ``defect_class`` is not
        found in the label table, returns ``defect_class`` itself unchanged
        (degrades gracefully instead of raising).

    Side effects:
        None (pure function).
    """
    if not defect_class:
        return "—"
    table = CLASS_LABELS_EN if normalize_language(language) == "en-US" else CLASS_LABELS_PT
    return table.get(defect_class, defect_class)

# --------------------------------------------------------------------------
# Model / vision
# --------------------------------------------------------------------------
BACKBONE = "mobilenet_v3_small"     # lightweight backbone (transfer learning)
IMG_SIZE = 224                      # CNN input size
MEAN = (0.485, 0.456, 0.406)        # ImageNet normalization
STD = (0.229, 0.224, 0.225)

# Inference must mirror the TRAINING preprocessing: every base was placed on a
# fit-to-fill canvas (generate_dataset._fit_canvas) before the 224px resize.
# The classifier expects the code to FILL the frame, so at inference we segment
# the code and re-apply the same canvas (vision.prepare_for_cnn). Keep these in
# sync with generate_dataset.CANVAS / _fit_canvas(fill=...).
CNN_CANVAS = (560, 260)             # mirrors generate_dataset.CANVAS
CNN_CANVAS_FILL = 0.92              # mirrors _fit_canvas(fill=...)

# --------------------------------------------------------------------------
# LLM / ADK
# --------------------------------------------------------------------------
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-flash-latest")
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY", "")   # if empty -> rule-based fallback

# --------------------------------------------------------------------------
# Web UI
# --------------------------------------------------------------------------
def _env_bool(name: str, default: bool) -> bool:
    """Parse a boolean environment variable ("1/true/yes/on" -> True)."""
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


# CAMERA_USE_ZXING: controls what the "+" menu's "Camera" option does.
#   false (default) -> native capture: take a still photo and send it to the
#                      print-quality analysis pipeline (the original behavior).
#   true            -> opt in to route "Camera" through the live ZXing scanner
#                      instead. The separate "Scan" option always uses ZXing.
CAMERA_USE_ZXING = _env_bool("CAMERA_USE_ZXING", False)

# --------------------------------------------------------------------------
# Visual arbiter (multimodal tie-breaker for confusable CNN class pairs)
# --------------------------------------------------------------------------
# ARBITER_MARGIN: max probability gap between the CNN's top-2 classes for the
#   pair to be considered "confusable" (i.e. a near-tie worth arbitrating).
# ARBITER_MIN_CONFIDENCE: top-1 confidence below which arbitration is also
#   triggered even if the top-2 gap is wide.
# ARBITER_PAIRS: the set of frozenset class-key pairs eligible for visual
#   arbitration. The gate only calls the (paid) multimodal API when the CNN's
#   top-2 forms one of these pairs AND is a near-tie / low-confidence case.
ARBITER_MARGIN = float(os.environ.get("ARBITER_MARGIN", "0.15"))
ARBITER_MIN_CONFIDENCE = float(os.environ.get("ARBITER_MIN_CONFIDENCE", "0.70"))
ARBITER_PAIRS = frozenset({frozenset({"no_defect", "damaged_printhead_element"})})


def has_gemini() -> bool:
    """Check whether an API key is configured to use Gemini.

    Returns:
        ``True`` if either the ``GOOGLE_API_KEY`` or ``GEMINI_API_KEY``
        environment variable is set to a non-empty value, ``False``
        otherwise.

    Side effects:
        None (reads environment variables only; does not cache the result,
        so changes to the environment are reflected on the next call).

    Failure/degradation behavior:
        Never raises; an absent/empty key simply yields ``False``, which
        callers use to fall back to the rule-based diagnosis path.
    """
    return bool(os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY"))


def num_classes() -> int:
    """Return the number of defect classes defined in ``CLASSES``.

    Returns:
        ``int``: ``len(CLASSES)``.

    Side effects:
        None (pure function).
    """
    return len(CLASSES)
