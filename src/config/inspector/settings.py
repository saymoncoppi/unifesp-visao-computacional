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

# Load variables from a .env file (e.g. GOOGLE_API_KEY), if present.
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except Exception:
    pass

# Dataset lives inside the project at: src/config/datasets/
DATASET_DIR = Path(os.environ.get("DATASET_DIR", ROOT / "config" / "datasets" / "dataset_sintetico"))
LABELS_CSV = DATASET_DIR / "labels.csv"
MODELS_DIR = ROOT / "config" / "models"
MODEL_PATH = Path(os.environ.get("MODEL_PATH", MODELS_DIR / "classificador_defeitos.pt"))

# --------------------------------------------------------------------------
# Defect classes (same taxonomy as generate_dataset.py)
# ORDER defines the index used by the CNN — do not reorder without retraining.
# --------------------------------------------------------------------------
CLASSES = [
    "no_defect",
    "damaged_printhead_element",
    "wrinkled_ribbon",
    "burnt_spot",
    "light_print",
    "uneven_pressure",
    "dirty_printhead",
]

CLASS_LABELS_PT = {
    "no_defect": "Sem defeito",
    "damaged_printhead_element": "Elemento da cabeça danificado",
    "wrinkled_ribbon": "Ribbon enrugado",
    "burnt_spot": "Ponto queimado (darkness alto)",
    "light_print": "Impressão clara (darkness baixo)",
    "uneven_pressure": "Pressão desigual da cabeça",
    "dirty_printhead": "Cabeça de impressão suja (voids)",
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

# --------------------------------------------------------------------------
# LLM / ADK
# --------------------------------------------------------------------------
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-flash-latest")
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY", "")   # if empty -> rule-based fallback


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
