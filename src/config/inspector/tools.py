"""Inspector tools: tool-functions for the ADK and the direct pipeline.

This module exposes four functions designed to be used as *tools* by the
Agent Development Kit (the ADK uses each function's docstring as the
description shown to the model) and a fifth function — ``analyze_image`` —
that runs the complete pipeline **without** the ADK. This direct pipeline is
the robust core used by the CLI/API and serves as a monolithic baseline: it
never raises on a missing library, it only accumulates warnings in
``report["errors"]``.

All heavy imports (OpenCV, PyTorch, pyzbar, Tesseract, Gemini) are
encapsulated inside the ``config.inspector.vision`` / ``config.inspector.network``
/ etc. modules, which import their dependencies lazily. Only stdlib and
imports from this package's own modules appear at the top here.
"""
from __future__ import annotations

from config.inspector import vision, network, diagnosis, kb, settings  # noqa: F401  (settings kept for consistency)
from config.inspector.report import build_report


# ---------------------------------------------------------------------------
# Tools (one per specialist) — used by the ADK and by the direct pipeline.
# ---------------------------------------------------------------------------
def decode_code(image_path: str) -> dict:
    """Decode a label's barcode and OCR its human-readable text.

    Takes the PATH of a label image, decodes the barcode (symbology +
    content) with ``vision.decode`` and adds the ``ocr_text`` field with the
    human-readable text extracted by ``vision.ocr_text``.

    Args:
        image_path: Path to the label image file.

    Returns:
        A dict with keys: ``readable`` (bool|None), ``symbology`` (str|None),
        ``content`` (str|None), ``symbol_count`` (int), ``error`` (str|None)
        and ``ocr_text`` (str). OCR is complementary: if it is unavailable,
        ``ocr_text`` comes back empty without interrupting the barcode
        decoding.

    Side effects / failure modes:
        Never raises. If ``vision.decode`` returns something other than a
        dict, a minimal error dict is built instead. If OCR fails for any
        reason, ``ocr_text`` falls back to an empty string.
    """
    result = vision.decode(image_path)
    if not isinstance(result, dict):
        result = {
            "readable": None,
            "symbology": None,
            "content": None,
            "symbol_count": 0,
            "error": "unexpected return from vision.decode",
        }

    ocr_text = ""
    try:
        image = vision.load_image(image_path)
        ocr_text = vision.ocr_text(image)
    except Exception:
        # OCR is optional; a failure here must not bring down the code reading.
        ocr_text = ""

    result["ocr_text"] = ocr_text or ""
    return result


def estimate_indicators(image_path: str) -> dict:
    """Estimate print-quality indicators for a label.

    Takes the PATH of an image, loads it in grayscale (``vision.load_image``
    followed by ``vision.to_gray``) and computes, via ``vision.indicators``,
    three indices in [0, 1]: ``contrast``, ``uniformity`` and ``sharpness``.

    Args:
        image_path: Path to the label image file.

    Returns:
        ``{"contrast": float, "uniformity": float, "sharpness": float}``.

    Side effects / failure modes:
        Propagates any exception raised while loading the image or computing
        the indicators (callers in the direct pipeline wrap this call in a
        try/except).
    """
    image = vision.load_image(image_path)
    gray = vision.to_gray(image)
    return vision.indicators(gray)


def classify_defect(image_path: str) -> dict:
    """Classify the label's print defect among the model's 7 classes.

    Takes the PATH of an image and uses the CNN (``network.predict``) to
    predict the print-defect class.

    Args:
        image_path: Path to the label image file.

    Returns:
        ``{"class": str|None, "class_label": str|None, "confidence": float,
        "probs": {class: float}, "error": str|None}``. If PyTorch or the
        model file is missing, ``class`` comes back null and ``error`` is
        populated.

    Side effects / failure modes:
        Delegates all error handling to ``network.predict``, which is
        expected to never raise (it reports failures via the ``error`` key
        instead).
    """
    return network.predict(image_path)


def search_zebra_docs(symptoms: str) -> str:
    """Query the Zebra knowledge base and return the relevant entries.

    Takes a textual description of the ``symptoms`` (for example: the
    predicted defect class plus the anomalous indicators observed) and
    retrieves, via ``kb.search``, the most relevant Zebra documentation
    entries. Formats the result as a human-readable text with appearance,
    probable cause, corrective action, parameters and source for each entry —
    ready to ground the diagnosis.

    Args:
        symptoms: Free-text description of the observed symptoms.

    Returns:
        Always a string (never raises). If the knowledge base is
        unavailable, returns an explanatory message instead of raising. If no
        entry matches, returns a "no match" message.
    """
    try:
        items = kb.search(symptoms)
    except Exception as exc:  # graceful degradation: kb may be unavailable.
        return f"Could not query the Zebra knowledge base: {exc}"

    if not items:
        return ("No Zebra documentation entry matched the given symptoms: "
                f"{symptoms!r}.")

    blocks: list[str] = []
    for i, item in enumerate(items, start=1):
        parameters = item.get("parameters") or []
        parameters_txt = ", ".join(str(p) for p in parameters) if parameters else "—"
        blocks.append(
            f"[{i}] Class: {item.get('class', '—')}\n"
            f"    Appearance: {item.get('appearance', '—')}\n"
            f"    Probable cause: {item.get('probable_cause', '—')}\n"
            f"    Corrective action: {item.get('corrective_action', '—')}\n"
            f"    Parameters: {parameters_txt}\n"
            f"    Source: {item.get('source', '—')}"
        )
    return "\n\n".join(blocks)


# ---------------------------------------------------------------------------
# Direct pipeline (without ADK) — robust monolithic baseline.
# ---------------------------------------------------------------------------
def analyze_image(image_path: str, use_gemini: bool = True,
                   language: str = settings.DEFAULT_LANGUAGE) -> dict:
    """Run the complete analysis of a label WITHOUT the ADK (direct pipeline).

    Chains, in sequence: decoding + OCR, checking for the PRESENCE of a
    barcode and — only when a code is present — print-quality indicators,
    defect classification, diagnosis of the cause/correction and, finally,
    consolidation into the report (``report.build_report(...).to_dict()``).
    When no code is detected, returns a minimal report (just the warning),
    without running the CNN or calling the LLM — saving processing time and
    API calls.

    This is the robust core used by the CLI/API and serves as a monolithic
    baseline: each step is isolated in a ``try/except`` and NEVER raises on a
    missing library — failures and degradations are accumulated in the
    ``errors`` list of the returned report.

    Args:
        image_path: Path to the label image to analyze.
        use_gemini: Selects the diagnosis engine (Gemini LLM vs. the
            rule-based Zebra knowledge base).
        language: Language of the diagnosis text.

    Returns:
        The report dict (see ``config.inspector.report.Report``).

    Side effects / failure modes:
        Never raises. Every stage (barcode reading, presence check,
        indicators, defect classification, diagnosis, report assembly) is
        wrapped in its own try/except; any exception is recorded as a string
        in the ``errors`` list instead of propagating. If report assembly
        itself fails, a hand-built fallback dict with the same top-level
        keys is returned instead.
    """
    errors: list[str] = []

    def _add_error(msg) -> None:
        """Accumulate a warning/error in the list, deduplicating and preserving order."""
        if msg is None:
            return
        text = str(msg).strip()
        if text and text not in errors:
            errors.append(text)

    # 1) Barcode reading (+ OCR).
    reading: dict = {}
    try:
        reading = decode_code(image_path)
        if isinstance(reading, dict) and reading.get("error"):
            _add_error(f"reading: {reading['error']}")
    except Exception as exc:
        _add_error(f"reading: {exc}")
        reading = {}

    # 2) Barcode PRESENCE — decided BEFORE the heavy inspection.
    #    Readable already implies present; otherwise, try detecting it from grayscale.
    code_detected = bool(isinstance(reading, dict) and reading.get("readable") is True)
    if not code_detected:
        try:
            image = vision.load_image(image_path)
            gray = vision.to_gray(image)
            code_detected = bool(vision.has_barcode(gray)[0])
        except Exception as exc:
            _add_error(f"code_detected: {exc}")

    # 2a) SHORT-CIRCUIT: with no barcode there is nothing to inspect.
    #     Avoids running the CNN and calling the LLM (Gemini) for nothing, and
    #     avoids returning a report with a false appearance of a useful result
    #     — just the warning.
    if not code_detected:
        _add_error("No barcode detected in the image.")
        try:
            report = build_report(
                reading=reading, indicators={}, defect={}, diagnosis={},
                code_detected=False, errors=errors,
            )
            return report.to_dict()
        except Exception as exc:  # safeguard: assembly must never bring down the pipeline
            _add_error(f"report: {exc}")
            return {
                "readable": reading.get("readable") if isinstance(reading, dict) else None,
                "code_detected": False,
                "symbology": None,
                "content": None,
                "ocr_text": (reading.get("ocr_text", "") if isinstance(reading, dict) else "") or "",
                "indicators": {},
                "defect": {},
                "probable_cause": "",
                "corrective_action": "",
                "reasoning": "",
                "source": "",
                "diagnosis_method": "",
                "overall_confidence": 0.0,
                "errors": errors,
            }

    # 3) Print-quality indicators.
    indicators: dict = {}
    try:
        indicators = estimate_indicators(image_path)
        if isinstance(indicators, dict) and indicators.get("error"):
            _add_error(f"indicators: {indicators['error']}")
    except Exception as exc:
        _add_error(f"indicators: {exc}")
        indicators = {}

    # 4) Defect classification (CNN).
    defect: dict = {}
    try:
        defect = classify_defect(image_path)
        if isinstance(defect, dict) and defect.get("error"):
            _add_error(f"defect: {defect['error']}")
    except Exception as exc:
        _add_error(f"defect: {exc}")
        defect = {}

    # 5) Diagnosis of the probable cause and correction (Gemini with rule-based fallback).
    diag: dict = {}
    try:
        diag = diagnosis.diagnose(
            defect=defect, reading=reading, indicators=indicators,
            use_gemini=use_gemini, language=language,
        )
        if isinstance(diag, dict) and diag.get("error"):
            _add_error(f"diagnosis: {diag['error']}")
    except Exception as exc:
        _add_error(f"diagnosis: {exc}")
        diag = {}

    # 6) Consolidation into the report.
    try:
        report = build_report(
            reading=reading,
            indicators=indicators,
            defect=defect,
            diagnosis=diag,
            code_detected=code_detected,
            errors=errors,
        )
        return report.to_dict()
    except Exception as exc:
        # Final safeguard: report assembly must never bring down the pipeline.
        _add_error(f"report: {exc}")
        return {
            "readable": reading.get("readable") if isinstance(reading, dict) else None,
            "code_detected": code_detected,
            "symbology": reading.get("symbology") if isinstance(reading, dict) else None,
            "content": reading.get("content") if isinstance(reading, dict) else None,
            "ocr_text": (reading.get("ocr_text", "") if isinstance(reading, dict) else "") or "",
            "indicators": indicators or {},
            "defect": defect or {},
            "probable_cause": diag.get("probable_cause", "") if isinstance(diag, dict) else "",
            "corrective_action": diag.get("corrective_action", "") if isinstance(diag, dict) else "",
            "reasoning": diag.get("rationale", "") if isinstance(diag, dict) else "",
            "source": diag.get("source", "") if isinstance(diag, dict) else "",
            "diagnosis_method": diag.get("method", "") if isinstance(diag, dict) else "",
            "overall_confidence": round(float(defect.get("confidence", 0.0) or 0.0), 3)
            if isinstance(defect, dict) else 0.0,
            "errors": errors,
        }
