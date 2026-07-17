"""Inspector tools: tool-functions for the ADK and the direct pipeline.

This module exposes four functions designed to be used as *tools* by the
Agent Development Kit (the ADK uses each function's docstring as the
description shown to the model) and a fifth function — ``analyze_image`` —
that runs the complete pipeline **without** the ADK. This direct pipeline is
the robust core used by the CLI/API and serves as a monolithic baseline: it
never raises on a missing library, it only accumulates warnings in
``report["errors"]``.

All heavy imports (OpenCV, PyTorch, pyzbar, Gemini) are
encapsulated inside the ``config.inspector.vision`` / ``config.inspector.network``
/ etc. modules, which import their dependencies lazily. Only stdlib and
imports from this package's own modules appear at the top here.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from config.inspector import vision, network, diagnosis, kb, settings, ratelimit  # noqa: F401  (settings kept for consistency)
from config.inspector.report import build_report

if TYPE_CHECKING:
    # Type-only import: NEVER imported at runtime, so the package stays fully
    # usable "without Google" (no google-adk dependency on the direct path).
    # The ADK still discovers the injected argument by the parameter NAME
    # ``tool_context``; the annotation is purely for static tooling.
    from google.adk.tools import ToolContext


def _save_state(tool_context: "ToolContext | None", key: str, value) -> None:
    """Persist a tool's real structured result into the ADK session state.

    In the ADK, a tool's declared ``output_key`` stores the agent's TEXT
    (a string), never the dict the tool returned. To make the actual
    structured payload available to downstream agents/tools, each tool writes
    its own dict into ``tool_context.state[key]`` under a ``*_data`` key.

    Args:
        tool_context: The ADK-injected context, or ``None`` when the tool is
            called from the direct pipeline (``analyze_image``). When ``None``
            this is a no-op.
        key: The state key to write (e.g. ``"reading_data"``).
        value: The structured value (dict/str) to store.

    Side effects:
        Mutates ``tool_context.state`` when a context is present.

    Failure modes:
        Never raises. Any error (missing ``state`` attribute, non-subscriptable
        state, etc.) is swallowed so the direct pipeline and the tool's return
        value are never affected. ``getattr``/``try`` keep this free of any
        google-adk import at runtime.
    """
    if tool_context is None:
        return
    try:
        state = getattr(tool_context, "state", None)
        if state is not None:
            state[key] = value
    except Exception:
        # State persistence is best-effort telemetry; never break the tool.
        pass


# ---------------------------------------------------------------------------
# Tools (one per specialist) — used by the ADK and by the direct pipeline.
# ---------------------------------------------------------------------------
def decode_code(image_path: str, tool_context: "ToolContext | None" = None) -> dict:
    """Decode a label's barcode.

    Takes the PATH of a label image and decodes the barcode (symbology +
    content) with ``vision.decode``.

    Args:
        image_path: Path to the label image file.
        tool_context: ADK-injected session context, or ``None`` when called
            from the direct pipeline (``analyze_image``). The ADK detects it
            by the parameter NAME; it is never passed on the direct path.

    Returns:
        A dict with keys: ``readable`` (bool|None), ``symbology`` (str|None),
        ``content`` (str|None), ``symbol_count`` (int) and ``error``
        (str|None).

    Side effects:
        When ``tool_context`` is present, writes the returned dict into
        ``tool_context.state["reading_data"]`` (best-effort; see
        ``_save_state``). Never mutates state on the direct path.

    Failure modes:
        Never raises. If ``vision.decode`` returns something other than a
        dict, a minimal error dict is built instead. State persistence
        failures are swallowed and never affect the return value.
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

    _save_state(tool_context, "reading_data", result)
    return result


def estimate_indicators(image_path: str, tool_context: "ToolContext | None" = None) -> dict:
    """Estimate print-quality indicators for a label.

    Takes the PATH of an image, loads it in grayscale (``vision.load_image``
    followed by ``vision.to_gray``) and computes, via ``vision.indicators``,
    three indices in [0, 1]: ``contrast``, ``uniformity`` and ``sharpness``.

    Args:
        image_path: Path to the label image file.
        tool_context: ADK-injected session context, or ``None`` when called
            from the direct pipeline. The ADK detects it by the parameter
            NAME; it is never passed on the direct path.

    Returns:
        ``{"contrast": float, "uniformity": float, "sharpness": float}``.

    Side effects:
        When ``tool_context`` is present, writes the returned dict into
        ``tool_context.state["indicators_data"]`` (best-effort). Never mutates
        state on the direct path.

    Failure modes:
        Propagates any exception raised while loading the image or computing
        the indicators (callers in the direct pipeline wrap this call in a
        try/except). State persistence failures are swallowed.
    """
    image = vision.load_image(image_path)
    gray = vision.to_gray(image)
    result = vision.indicators(gray)
    _save_state(tool_context, "indicators_data", result)
    return result


def classify_defect(image_path: str, tool_context: "ToolContext | None" = None) -> dict:
    """Classify the label's print defect among the model's 7 classes.

    Takes the PATH of an image and uses the CNN (``network.predict``) to
    predict the print-defect class.

    Args:
        image_path: Path to the label image file.
        tool_context: ADK-injected session context, or ``None`` when called
            from the direct pipeline. The ADK detects it by the parameter
            NAME; it is never passed on the direct path.

    Returns:
        ``{"class": str|None, "class_label": str|None, "confidence": float,
        "probs": {class: float}, "error": str|None}``. If PyTorch or the
        model file is missing, ``class`` comes back null and ``error`` is
        populated.

    Side effects:
        When ``tool_context`` is present, writes the returned dict into
        ``tool_context.state["defect_data"]`` (best-effort). Note that
        ``inspect_image_visually`` may later OVERWRITE this key with an
        arbitrated defect. Never mutates state on the direct path.

    Failure modes:
        Delegates all error handling to ``network.predict``, which is
        expected to never raise (it reports failures via the ``error`` key
        instead). State persistence failures are swallowed.
    """
    result = network.predict(image_path)
    _save_state(tool_context, "defect_data", result)
    return result


def search_zebra_docs(symptoms: str, tool_context: "ToolContext | None" = None) -> str:
    """Query the Zebra knowledge base and return the relevant entries.

    Takes a textual description of the ``symptoms`` (for example: the
    predicted defect class plus the anomalous indicators observed) and
    retrieves, via ``kb.search``, the most relevant Zebra documentation
    entries. Formats the result as a human-readable text with appearance,
    probable cause, corrective action, parameters and source for each entry —
    ready to ground the diagnosis.

    Args:
        symptoms: Free-text description of the observed symptoms.
        tool_context: ADK-injected session context, or ``None`` when called
            from the direct pipeline. The ADK detects it by the parameter
            NAME; it is never passed on the direct path.

    Returns:
        Always a string (never raises). If the knowledge base is
        unavailable, returns an explanatory message instead of raising. If no
        entry matches, returns a "no match" message.

    Side effects:
        When ``tool_context`` is present, writes the returned string into
        ``tool_context.state["diagnosis_data"]`` (best-effort). Never mutates
        state on the direct path.
    """
    try:
        items = kb.search(symptoms)
    except Exception as exc:  # graceful degradation: kb may be unavailable.
        text = f"Could not query the Zebra knowledge base: {exc}"
        _save_state(tool_context, "diagnosis_data", text)
        return text

    if not items:
        text = ("No Zebra documentation entry matched the given symptoms: "
                f"{symptoms!r}.")
        _save_state(tool_context, "diagnosis_data", text)
        return text

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
    text = "\n\n".join(blocks)
    _save_state(tool_context, "diagnosis_data", text)
    return text


def inspect_image_visually(image_path: str, candidate_classes: list,
                            indicators: dict,
                            tool_context: "ToolContext | None" = None) -> dict | None:
    """Visually arbitrate a confusable CNN class pair with a multimodal LLM.

    This is the VISUAL ARBITER. The CNN sometimes cannot separate a specific
    pair of look-alike classes (see ``settings.ARBITER_PAIRS``). When the
    CNN's top-2 prediction lands exactly on such a pair AND is a near-tie
    (top-2 gap within ``settings.ARBITER_MARGIN``) or low-confidence (top-1
    below ``settings.ARBITER_MIN_CONFIDENCE``), this tool sends the actual
    image plus grounded context to Gemini's multimodal model and lets it
    CORRECT the class. Outside those conditions it is a cheap no-op (the paid
    API is never called).

    Multimodal analysis is EXCLUSIVE to the ADK path: this tool reads the
    CNN result from ``tool_context.state["defect_data"]`` and, when it
    overrides the class, writes the reshaped defect back to that same key.

    Args:
        image_path: Path to the label image file.
        candidate_classes: The candidate defect-class keys to disambiguate
            (typically the CNN's top-2). Used to ground the prompt; the gate
            itself is computed from the CNN probabilities in state.
        indicators: Measured print-quality indicators, used to ground the
            prompt via ``kb.context_for_llm``.
        tool_context: ADK-injected session context. Required in practice:
            when ``None`` (or without a ``defect_data`` payload) the tool
            cannot read the CNN probabilities and returns ``None``.

    Returns:
        On override: the reshaped defect dict matching ``network.predict``'s
        shape plus additive keys — ``{"class", "class_label", "confidence",
        "probs" (ORIGINAL CNN probs preserved), "error": None,
        "arbitrated": True, "visual_evidence", "original_class"}``. Otherwise
        (gate not met, LLM unavailable/failed, agreed with the CNN, or the
        image falls outside the taxonomy): ``None`` and no state change.

    Side effects:
        On override, overwrites ``tool_context.state["defect_data"]`` with the
        reshaped defect (best-effort via ``_save_state``). May perform a
        network call to the Gemini multimodal API when the gate is met.

    Failure modes:
        Never raises. The ``google-genai`` import is LAZY; any failure
        (missing library, network error, quota, malformed JSON) is caught and
        yields ``None``, leaving the CNN's original ``defect_data`` untouched
        — exactly like ``diagnosis._diagnose_with_gemini``.
    """
    # --- Read the CNN result from state (arbiter is ADK-only). -------------
    defect = None
    if tool_context is not None:
        try:
            state = getattr(tool_context, "state", None)
            if state is not None:
                defect = state["defect_data"]
        except Exception:
            defect = None
    if not isinstance(defect, dict):
        return None

    probs = defect.get("probs")
    if not isinstance(probs, dict) or not probs:
        return None
    cnn_class = defect.get("class")

    # --- Cheap gate: only pay for the API on a confusable near-tie. --------
    ranked = sorted(probs.items(), key=lambda kv: kv[1], reverse=True)
    if len(ranked) < 2:
        return None
    (top1_key, top1_p), (top2_key, top2_p) = ranked[0], ranked[1]
    top2_pair = frozenset({top1_key, top2_key})
    if top2_pair not in settings.ARBITER_PAIRS:
        return None
    near_tie = (float(top1_p) - float(top2_p)) <= settings.ARBITER_MARGIN
    low_conf = float(top1_p) < settings.ARBITER_MIN_CONFIDENCE
    if not (near_tie or low_conf):
        return None

    # --- Multimodal arbitration (LAZY google-genai import). ----------------
    try:
        from google import genai
        from google.genai import types

        with open(image_path, "rb") as fh:
            image_bytes = fh.read()
        mime_type = "image/png" if str(image_path).lower().endswith(".png") else "image/jpeg"

        # Ground the prompt with the KB context for each candidate class.
        cands = list(candidate_classes) if candidate_classes else [top1_key, top2_key]
        contexts = "\n\n".join(
            kb.context_for_llm(c, indicators or {}, {}) for c in cands
        )
        valid = ", ".join(f'"{c}"' for c in cands)
        prompt = (
            "You are a visual quality inspector for Zebra thermal labels.\n"
            "A CNN cannot reliably separate the following visually confusable "
            "candidate classes for THIS label image:\n"
            f"  {valid}\n\n"
            "Look at the attached image and decide which candidate class it "
            "truly is. Ground your decision on the knowledge base below and on "
            "the measured indicators.\n\n"
            f"{contexts}\n\n"
            f"CNN's tentative top class: {cnn_class!r} "
            f"(top-2 candidates and probabilities: "
            f"{top1_key}={float(top1_p):.4f}, {top2_key}={float(top2_p):.4f}).\n\n"
            "If the image clearly does not match any candidate, set "
            "out_of_taxonomy to true and keep chosen_class as the best of the "
            "candidates.\n"
            "Answer STRICTLY in JSON, with no extra text, in the format:\n"
            '{"chosen_class": "<one of the candidate keys>", '
            '"out_of_taxonomy": false, '
            '"visual_evidence": "<what you actually see in the image>", '
            '"arbitration_rationale": "<why you chose it over the other>", '
            '"confidence": 0.0}'
        )

        client = genai.Client()
        ratelimit.record()   # count the attempt toward the RPM window.
        response = client.models.generate_content(
            model=settings.GEMINI_MODEL,
            contents=[
                types.Content(role="user", parts=[
                    types.Part(inline_data=types.Blob(mime_type=mime_type, data=image_bytes)),
                    types.Part(text=prompt),
                ]),
            ],
            config=types.GenerateContentConfig(response_mime_type="application/json"),
        )
        text = (getattr(response, "text", None) or "").strip()
        data = diagnosis._extract_json(text)
        if not data:
            return None

        chosen = (data.get("chosen_class") or "").strip()
        out_of_taxonomy = bool(data.get("out_of_taxonomy"))
        visual_evidence = (data.get("visual_evidence") or "").strip()

        # No correction: image outside taxonomy, empty/invalid choice, or the
        # arbiter agrees with the CNN. Leave defect_data untouched.
        if out_of_taxonomy or not chosen or chosen not in settings.CLASSES:
            return None
        if chosen == cnn_class:
            return None

        try:
            confidence = round(float(data.get("confidence")), 4)
        except (TypeError, ValueError):
            confidence = round(float(probs.get(chosen, 0.0) or 0.0), 4)

        arbitrated = {
            "class": chosen,
            "class_label": settings.class_display_name(chosen, "pt-BR"),
            "confidence": confidence,
            "probs": probs,                 # ORIGINAL CNN probs, preserved.
            "error": None,
            "arbitrated": True,
            "visual_evidence": visual_evidence,
            "original_class": cnn_class,
        }
        _save_state(tool_context, "defect_data", arbitrated)
        return arbitrated
    except Exception as exc:
        # Any error (missing lib, network, quota, invalid JSON) -> no-op.
        ratelimit.observe_exception(exc)   # fold a 429's retryDelay into the quota state.
        return None


# ---------------------------------------------------------------------------
# Direct pipeline (without ADK) — robust monolithic baseline.
# ---------------------------------------------------------------------------
def analyze_image(image_path: str, use_gemini: bool = True,
                   language: str = settings.DEFAULT_LANGUAGE) -> dict:
    """Run the complete analysis of a label WITHOUT the ADK (direct pipeline).

    Chains, in sequence: decoding, checking for the PRESENCE of a
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

    # 1) Barcode reading.
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
