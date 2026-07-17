"""Diagnosis of the probable cause and of the suggested correction.

Combines the LLM (Gemini) with a deterministic rule-based fallback over the
Zebra knowledge base. Gemini is optional: it is only used when an API key is
configured and the library is available; any failure gracefully falls back
to the rule-based path. The `google.genai` import is always LAZY (inside the
function).
"""
from __future__ import annotations

import json

from config.inspector import settings, kb, ratelimit


def diagnose(defect: dict, reading: dict, indicators: dict,
             use_gemini: bool = True, language: str = settings.DEFAULT_LANGUAGE) -> dict:
    """Determine the probable cause and the suggested correction for a defect.

    Args:
        defect: Dict describing the detected defect. Only the ``"class"``
            key is read from it (the defect class key, e.g.
            ``"wrinkled_ribbon"``).
        reading: Dict with the barcode/label reading data (symbology,
            content, OCR text, etc.), forwarded to the Gemini prompt when
            applicable.
        indicators: Dict with the measured image indicators (contrast,
            uniformity, sharpness, ...).
        use_gemini: Selects the diagnosis engine. ``True`` tries the LLM
            (Gemini) first and falls back to the rule-based path if it is
            unavailable; ``False`` forces the Zebra knowledge base (rules).
        language: Language of the returned text (``"pt-BR"`` or ``"en-US"``).

    Returns:
        A dict with the keys ``probable_cause``, ``corrective_action``,
        ``rationale``, ``source`` and ``method`` (``"gemini"`` or
        ``"rules"``).

    Side effects:
        None directly. May trigger a network call to the Gemini API (via
        ``_diagnose_with_gemini``) when ``use_gemini`` is ``True`` and a key
        is configured.

    Failure modes:
        Never raises. Any failure on the LLM path (missing library, network
        error, quota, invalid JSON) causes a silent fallback to the
        rule-based diagnosis over the knowledge base.
    """
    defect = defect or {}
    defect_class = defect.get("class")
    language = settings.normalize_language(language)

    # Defect-free label: there is nothing to diagnose. Short-circuit BEFORE the
    # LLM/rules so we neither invent a cause for a clean label nor spend a Gemini
    # call. (Applies after the visual arbiter, so an arbitrated "no_defect" also
    # yields a coherent report.)
    if defect_class == settings.NO_DEFECT_CLASS:
        return _no_defect_diagnosis(language)

    if use_gemini and settings.has_gemini():
        result = _diagnose_with_gemini(defect_class, reading, indicators, language)
        if result is not None:
            return result

    return _diagnose_by_rules(defect_class, indicators, language)


def _no_defect_diagnosis(language: str = settings.DEFAULT_LANGUAGE) -> dict:
    """Diagnosis payload for a defect-free label (no cause, no correction).

    Args:
        language: Language of the returned text (``"pt-BR"`` or ``"en-US"``).

    Returns:
        A dict with the same keys as the other diagnosis paths
        (``probable_cause``, ``corrective_action``, ``rationale``, ``source``,
        ``method``), stating that no defect was found and no action is needed.
        ``method`` is ``"rules"`` (the result is deterministic, no LLM call).
    """
    if settings.normalize_language(language) == "en-US":
        return {
            "probable_cause": "No defect detected.",
            "corrective_action": "No corrective action required — the print "
                                 "quality is within acceptable parameters.",
            "rationale": "The classifier (and the visual arbiter, when it ran) "
                         "identified the label as defect-free.",
            "source": "",
            "method": "rules",
        }
    return {
        "probable_cause": "Nenhum defeito detectado.",
        "corrective_action": "Nenhuma ação corretiva necessária — a qualidade "
                             "de impressão está dentro dos parâmetros aceitáveis.",
        "rationale": "O classificador (e o árbitro visual, quando atuou) "
                     "identificou a etiqueta como sem defeito.",
        "source": "",
        "method": "rules",
    }


def _diagnose_with_gemini(defect_class: str | None, reading: dict,
                           indicators: dict,
                           language: str = settings.DEFAULT_LANGUAGE) -> dict | None:
    """Try to diagnose the defect via Gemini. Returns None on any failure.

    Args:
        defect_class: The defect class key (e.g. ``"burnt_spot"``), or None.
        reading: Dict with the barcode/label reading data, used to build the
            LLM context via ``kb.context_for_llm``.
        indicators: Dict with the measured image indicators, used to build
            the LLM context.
        language: Language requested for the LLM answer (``"pt-BR"`` or
            ``"en-US"``).

    Returns:
        A dict with keys ``probable_cause``, ``corrective_action``,
        ``rationale``, ``source`` and ``method="gemini"``, or ``None`` if
        the ``google-genai`` library is unavailable, the request fails, or
        the response cannot be parsed into a valid diagnosis.

    Side effects:
        Performs a network call to the Gemini API.

    Failure modes:
        Any exception (missing library, network error, quota exceeded,
        malformed/incomplete JSON response) is caught and results in
        ``None`` being returned, letting the caller fall back to the
        rule-based diagnosis.
    """
    try:
        from google import genai   # LAZY import (only when actually needed)

        context = kb.context_for_llm(defect_class, indicators or {}, reading or {})
        language_instruction = (
            "Write your answer in English." if language == "en-US"
            else "Escreva em português."
        )
        prompt = (
            "You are a specialist in Zebra thermal label printing.\n"
            "Based on the knowledge base and the measured indicators below, "
            "diagnose the probable cause of the defect and the suggested "
            "correction.\n\n"
            f"{context}\n\n"
            "Answer STRICTLY in JSON, with no extra text, in the format:\n"
            '{"probable_cause": "...", "corrective_action": "...", '
            '"rationale": "..."}\n'
            f"{language_instruction}"
        )

        client = genai.Client()
        ratelimit.record()   # count the attempt toward the RPM window.
        response = client.models.generate_content(
            model=settings.GEMINI_MODEL,
            contents=prompt,
        )
        text = (getattr(response, "text", None) or "").strip()
        data = _extract_json(text)
        if not data:
            return None

        cause = (data.get("probable_cause") or "").strip()
        correction = (data.get("corrective_action") or "").strip()
        rationale = (data.get("rationale") or "").strip()
        if not cause or not correction:
            return None

        item = kb.search_by_class(defect_class)
        source = item.get("source", kb.SOURCE) if item else kb.SOURCE
        return {
            "probable_cause": cause,
            "corrective_action": correction,
            "rationale": rationale,
            "source": source,
            "method": "gemini",
        }
    except Exception as exc:
        # Any error (missing lib, network, quota, invalid JSON) -> fallback.
        ratelimit.observe_exception(exc)   # fold a 429's retryDelay into the quota state.
        return None


def _extract_json(text: str) -> dict | None:
    """Extract a JSON object from the LLM response text.

    Tolerant of Markdown code fences (```) or extra surrounding text: first
    tries to parse the whole text as JSON, then falls back to slicing out
    the substring between the first ``{`` and the last ``}``.

    Args:
        text: Raw text returned by the LLM.

    Returns:
        The parsed dict, or ``None`` if no valid JSON object could be
        extracted.

    Side effects:
        None.
    """
    if not text:
        return None
    try:
        return json.loads(text)
    except Exception:
        pass
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(text[start:end + 1])
        except Exception:
            return None
    return None


def _diagnose_by_rules(defect_class: str | None, indicators: dict,
                        language: str = settings.DEFAULT_LANGUAGE) -> dict:
    """Deterministic fallback diagnosis using the Zebra knowledge base.

    Args:
        defect_class: The defect class key (e.g. ``"dirty_printhead"``), or
            None.
        indicators: Dict with the measured image indicators (contrast,
            uniformity, sharpness), used only to build the human-readable
            rationale text.
        language: Language of the returned text (``"pt-BR"`` or
            ``"en-US"``).

    Returns:
        A dict with keys ``probable_cause``, ``corrective_action``,
        ``rationale``, ``source`` and ``method="rules"``. If
        ``defect_class`` has no match in the knowledge base, returns a
        generic "cause not identified" message in the requested language.

    Side effects:
        None.
    """
    en = settings.normalize_language(language) == "en-US"
    item = kb.search_by_class(defect_class)
    if item is None:
        if en:
            return {
                "probable_cause": "Cause not identified.",
                "corrective_action": "Manually check the print parameters "
                                     "(darkness, speed, pressure) and the printhead "
                                     "cleanliness.",
                "rationale": "Defect with no match in the Zebra knowledge base "
                             f"(class: {defect_class or '—'}).",
                "source": kb.SOURCE,
                "method": "rules",
            }
        return {
            "probable_cause": "Causa não identificada.",
            "corrective_action": "Verificar manualmente os parâmetros de impressão "
                                 "(darkness, velocidade, pressão) e a limpeza da "
                                 "cabeça.",
            "rationale": "Defeito sem correspondência na base de conhecimento "
                         f"Zebra (classe: {defect_class or '—'}).",
            "source": kb.SOURCE,
            "method": "rules",
        }

    ind = indicators or {}
    appearance = kb.localized_field(item, "appearance", language)
    name = settings.class_display_name(defect_class, language)
    if en:
        rationale = (
            f"Classification '{name}' associated, in the Zebra knowledge base, with "
            f"the appearance: {appearance or '—'} "
            f"Measured indicators — contrast={ind.get('contrast', '—')}, "
            f"uniformity={ind.get('uniformity', '—')}, "
            f"sharpness={ind.get('sharpness', '—')}."
        )
    else:
        rationale = (
            f"Classificação '{name}' associada, na base de conhecimento Zebra, à "
            f"aparência: {appearance or '—'} "
            f"Indicadores medidos — contraste={ind.get('contrast', '—')}, "
            f"uniformidade={ind.get('uniformity', '—')}, "
            f"nitidez={ind.get('sharpness', '—')}."
        )
    return {
        "probable_cause": kb.localized_field(item, "probable_cause", language),
        "corrective_action": kb.localized_field(item, "corrective_action", language),
        "rationale": rationale,
        "source": item.get("source", kb.SOURCE),
        "method": "rules",
    }
