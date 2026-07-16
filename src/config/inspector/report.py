"""Report schema (structured result of analyzing a single label).

Defines the ``Report`` dataclass — the consolidated, serializable result of
inspecting one barcode label — and the ``build_report`` factory that
assembles it from the outputs of the other specialists (vision, network,
diagnosis). This module has no external dependencies beyond the standard
library, so it can be imported by ``app.api``, ``app.cli``, tests, and the
chat frontend's JSON contract without pulling in torch/PIL/etc.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict


@dataclass
class Report:
    """Consolidated result of inspecting a barcode label.

    Every field is optional/defaulted so that a partial pipeline (e.g. no
    barcode detected, or the diagnosis step failing) still produces a valid,
    serializable ``Report``. Field names double as the JSON keys emitted to
    consumers (``app.api``, ``app.cli``, the chat frontend, and the test
    suite), so they must not be renamed without updating those consumers.

    Attributes:
        readable: Whether the barcode/QR code could be successfully
            decoded. ``None`` means the check was not performed (e.g. no
            image or no code region found); ``True``/``False`` otherwise.
        code_detected: Whether the image plausibly contains a barcode
            region at all (independent of whether it was decodable).
            ``None`` when this check was skipped.
        symbology: Detected code symbology, e.g. ``"CODE128"``, ``"EAN13"``,
            ``"QRCODE"``. ``None`` when not decoded.
        content: Decoded payload (raw text/data encoded in the barcode).
            ``None`` when not decoded.
        ocr_text: Human-readable text extracted from the image via OCR
            (Tesseract). Empty string when OCR found nothing or was not run.
        indicators: Dict of image-quality indicators produced by the vision
            module, e.g. ``{"contrast": ..., "uniformity": ..., "sharpness": ...}``.
        defect: Dict describing the classified defect, e.g.
            ``{"class": ..., "class_label": ..., "confidence": ..., "probs": ...}``.
        probable_cause: Human-readable probable cause of the defect, as
            produced by the diagnosis step (LLM or rule-based fallback).
        corrective_action: Human-readable suggested corrective action.
        reasoning: Short excerpt/rationale that supports the diagnosis
            (e.g. the knowledge-base passage or LLM justification used).
        source: Reference/citation for the diagnosis (e.g. "Zebra
            Technologies, 2024").
        diagnosis_method: Which engine produced the diagnosis —
            ``"gemini"`` (LLM) or ``"rules"`` (deterministic fallback).
        overall_confidence: Overall confidence score (0.0-1.0) for the
            defect classification, rounded for display.
        errors: List of warnings/degradations encountered while building
            the report (e.g. missing optional libraries, fallbacks taken).
            Does not include hard failures, which would prevent building
            the report at all.
    """
    readable: bool | None = None
    code_detected: bool | None = None
    symbology: str | None = None
    content: str | None = None
    ocr_text: str = ""
    indicators: dict = field(default_factory=dict)
    defect: dict = field(default_factory=dict)
    probable_cause: str = ""
    corrective_action: str = ""
    reasoning: str = ""
    source: str = ""
    diagnosis_method: str = ""
    overall_confidence: float = 0.0
    errors: list = field(default_factory=list)

    def to_dict(self) -> dict:
        """Return a plain-``dict`` representation (JSON-serializable).

        Returns:
            The report as a nested dict via ``dataclasses.asdict``, suitable
            for passing to ``json.dumps`` or a template renderer.
        """
        return asdict(self)

    def summary(self) -> str:
        """Build a short, human-friendly text summary (for chat/CLI use).

        Returns:
            A multi-line string with the read status, decoded symbology/
            content (if readable), the classified defect and confidence,
            the probable cause, the suggested corrective action, and — if
            no barcode was detected at all — a trailing warning line.
        """
        read_status = (
            "readable" if self.readable
            else ("unreadable" if self.readable is not None else "reading unavailable")
        )
        defect_class = self.defect.get("class_label") or self.defect.get("class") or "—"
        confidence = self.defect.get("confidence")
        confidence_txt = f" ({confidence:.0%})" if isinstance(confidence, (int, float)) else ""
        lines = [
            f"Reading: {read_status}" + (f" — {self.symbology}: {self.content}" if self.readable else ""),
            f"Defect: {defect_class}{confidence_txt}",
            f"Probable cause: {self.probable_cause or '—'}",
            f"Suggested correction: {self.corrective_action or '—'}",
        ]
        if self.code_detected is False:
            lines.append("Warning: no barcode detected in the image.")
        return "\n".join(lines)


def build_report(*, reading: dict, indicators: dict, defect: dict,
                 diagnosis: dict, code_detected: bool | None = None,
                 errors: list | None = None) -> Report:
    """Aggregate the specialists' outputs into a single ``Report``.

    Args:
        reading: Dict produced by ``config.inspector.vision`` /
            ``config.inspector.tools`` describing the barcode read, with
            keys such as ``readable``, ``symbology``, ``content`` and
            ``ocr_text``. Missing keys are tolerated (treated as absent).
        indicators: Dict of image-quality indicators produced by
            ``config.inspector.vision`` (e.g. ``contrast``, ``uniformity``,
            ``sharpness``). Passed through unchanged.
        defect: Dict produced by ``config.inspector.network`` /
            ``config.inspector.tools`` describing the classified defect
            (e.g. ``class``, ``class_label``, ``confidence``, ``probs``).
            Passed through unchanged.
        diagnosis: Dict produced by ``config.inspector.diagnosis`` with
            keys such as ``probable_cause``, ``corrective_action``,
            ``reasoning``, ``source`` and ``diagnosis_method`` (previously
            ``method``). Missing keys default to empty strings.
        code_detected: Whether a barcode region was plausibly found in the
            image, independent of whether it was decodable. Defaults to
            ``None`` (check not performed / not applicable).
        errors: List of warnings/degradations collected while building the
            report (e.g. missing optional libraries). Defaults to an empty
            list when ``None``.

    Returns:
        A populated ``Report`` instance. Never raises: any missing or
        malformed input dict is treated as empty, so a partial pipeline
        still yields a usable (if sparse) report.
    """
    defect_confidence = float(defect.get("confidence", 0.0) or 0.0)
    return Report(
        readable=reading.get("readable"),
        code_detected=code_detected,
        symbology=reading.get("symbology"),
        content=reading.get("content"),
        ocr_text=reading.get("ocr_text", "") or "",
        indicators=indicators or {},
        defect=defect or {},
        probable_cause=diagnosis.get("probable_cause", ""),
        corrective_action=diagnosis.get("corrective_action", ""),
        reasoning=diagnosis.get("rationale", ""),
        source=diagnosis.get("source", ""),
        diagnosis_method=diagnosis.get("method", ""),
        overall_confidence=round(defect_confidence, 3),
        errors=errors or [],
    )
