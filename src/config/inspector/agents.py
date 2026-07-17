"""Multi-agent orchestration with the ADK (Google Agent Development Kit).

Builds the label-inspector agent graph:

    ┌────────────────────── ParallelAgent ──────────────────────┐
    │  LlmAgent reading      (tool: decode_code)                │
    │  LlmAgent indicators   (tool: estimate_indicators)        │  → run in parallel
    │  LlmAgent defect       (tool: classify_defect)            │
    └─────────────────────────────────────────────────────────┘
                              │
                    LlmAgent visual_arbiter (tool: inspect_image_visually)
                              │   ← may CORRECT the CNN class (state defect_data)
                    LlmAgent diagnosis      (tool: search_zebra_docs)
                              │
                    LlmAgent report         (consolidates into JSON)

The root ``SequentialAgent`` executes:
    [parallel] → [visual_arbiter] → [diagnosis] → [report].

Every import of ``google.adk`` / ``google.genai`` is LAZY (done inside the
functions), so the module imports fine even without the ADK installed and
``python -m py_compile`` passes. The tools come from ``config.inspector.tools``.
"""
from __future__ import annotations

import inspect
import json
import uuid

from config.inspector import settings, vision, diagnosis as diagnosis_mod
from config.inspector.report import build_report
from config.inspector.tools import (
    classify_defect,
    decode_code,
    estimate_indicators,
    inspect_image_visually,
    search_zebra_docs,
)

# Gemini model used by every LlmAgent in the graph.
MODEL = settings.GEMINI_MODEL

# Runner application/session identifiers.
_APP_NAME = "label_inspector"
_USER_ID = "user"
_SESSION_ID = "session"

# Lean single-agent graph (visual arbiter only), cached for the optimized
# analyze_via_adk hot path. Built on demand; None until first use / if ADK
# is unavailable.
_arbiter_root = None

# Visual arbiter agent — one source of truth, reused by the full graph
# (build_root_agent, for `adk web`) and by the lean arbiter-only graph.
_ARBITER_DESC = (
    "Visually arbitrates a confusable CNN class pair, correcting the defect "
    "class when warranted."
)
_ARBITER_INSTRUCTION = (
    "You are the VISUAL ARBITER for confusable print-defect classes. "
    "The user provides the PATH of a label image. The CNN has already "
    "classified the defect; its result — class and per-class "
    "probabilities — is in the state:\n"
    "- CNN defect: {defect_data?}\n"
    "- Quality indicators: {indicators_data?}\n\n"
    "Call the `inspect_image_visually` tool passing: image_path = the "
    "exact image path from the user message; candidate_classes = the "
    "list with the TWO highest-probability class keys taken from the "
    "CNN probabilities above; indicators = the quality-indicators "
    "object above. The tool decides ON ITS OWN whether arbitration is "
    "warranted (only for a confusable near-tie pair). If it returns "
    "null, keep the CNN class UNCHANGED and state that the original "
    "classification stands. If it returns a defect object, report the "
    "corrected class and the visual evidence it cites. Never invent a "
    "class the tool did not return."
)


def _new_visual_arbiter():
    """Build the visual-arbiter ``LlmAgent`` (tool: ``inspect_image_visually``).

    Also injects ``ToolContext`` into the tools module so the ADK can resolve
    the tool annotations at declaration time (idempotent — safe to call from
    both graph builders). Requires google-adk (lazy import).
    """
    from google.adk.agents import LlmAgent
    from google.adk.tools import ToolContext as _ToolContext
    import config.inspector.tools as _tools_mod
    _tools_mod.ToolContext = _ToolContext
    return LlmAgent(
        name="visual_arbiter",
        model=MODEL,
        description=_ARBITER_DESC,
        instruction=_ARBITER_INSTRUCTION,
        tools=[inspect_image_visually],
        output_key="arbitration",
    )


# ---------------------------------------------------------------------------
# Agent graph construction.
# ---------------------------------------------------------------------------
def build_root_agent():
    """Build and return the root ``SequentialAgent`` of the label inspector.

    Structure: a ``ParallelAgent`` with the three perception specialists
    (reading, indicators, defect), followed by a diagnosis ``LlmAgent`` and a
    report ``LlmAgent`` that consolidates everything into JSON. Each specialist
    writes its result into the session state via ``output_key``; the
    downstream agents read that state through the ``{reading}`` /
    ``{indicators}`` / ``{defect}`` / ``{diagnosis}`` template markers.

    Params:
        None.

    Returns:
        A ``google.adk.agents.SequentialAgent`` instance wired with the full
        perception → diagnosis → report pipeline.

    Side effects:
        None beyond constructing the in-memory agent objects (no I/O).

    Failure modes:
        Raises ``ImportError`` (with an install hint) if the ``google-adk``
        package is not available.
    """
    try:
        from google.adk.agents import LlmAgent, ParallelAgent, SequentialAgent
        from google.adk.tools import ToolContext as _ToolContext
    except ImportError as exc:
        raise ImportError(
            "google-adk is not installed. Install it with: pip install google-adk"
        ) from exc

    # The tool functions annotate their injected argument as ``ToolContext |
    # None`` but keep the import under ``TYPE_CHECKING`` (so the direct pipeline
    # needs no google-adk). When the ADK builds each tool's declaration it calls
    # ``typing.get_type_hints`` on the function, which evaluates that annotation
    # in the TOOL MODULE's globals — where ``ToolContext`` would otherwise be
    # undefined, raising ``NameError`` and forcing every ADK run to fall back to
    # the direct pipeline. Inject the real symbol into the tools module now, at
    # graph-build time (ADK is guaranteed installed here), before constructing
    # any LlmAgent that registers a tool.
    import config.inspector.tools as _tools_mod
    _tools_mod.ToolContext = _ToolContext

    # --- Perception specialists (run in parallel) ---------------------------
    reading_agent = LlmAgent(
        name="reading_specialist",
        model=MODEL,
        description="Decodes the barcode and OCRs the label text.",
        instruction=(
            "You are the barcode READING specialist. The user provides the "
            "PATH of a label image file. Call the `decode_code` tool passing "
            "exactly that path as the argument. Then report objectively: "
            "whether the code is readable, the symbology, the decoded content "
            "and the ocr_text. Do not invent values; use only what the tool "
            "returns."
        ),
        tools=[decode_code],
        output_key="reading",
    )

    indicators_agent = LlmAgent(
        name="indicators_specialist",
        model=MODEL,
        description="Estimates print contrast, uniformity and sharpness.",
        instruction=(
            "You are the print QUALITY INDICATORS specialist. The user "
            "provides the PATH of a label image. Call the `estimate_indicators` "
            "tool passing that path and report the contrast, uniformity and "
            "sharpness values (each between 0 and 1). Point out which "
            "indicators look low/anomalous."
        ),
        tools=[estimate_indicators],
        output_key="indicators",
    )

    defect_agent = LlmAgent(
        name="defect_specialist",
        model=MODEL,
        description="Classifies the print defect among the model's 7 classes.",
        instruction=(
            "You are the print DEFECT CLASSIFICATION specialist. The user "
            "provides the PATH of a label image. Call the `classify_defect` "
            "tool passing that path and report the predicted class (class and "
            "class_label) with its confidence. If the tool returns an error, "
            "report the error without inventing the class."
        ),
        tools=[classify_defect],
        output_key="defect",
    )

    parallel_analysis = ParallelAgent(
        name="perceptual_parallel_analysis",
        sub_agents=[reading_agent, indicators_agent, defect_agent],
    )

    # --- Visual arbiter (may CORRECT the CNN class on a confusable pair) -----
    # Runs AFTER the parallel perception (the CNN's `defect_data` must already
    # be in state) and BEFORE diagnosis, so the diagnosis reasons over the
    # possibly-corrected class. The `inspect_image_visually` tool applies its
    # own cheap gate and, on override, overwrites state["defect_data"].
    visual_arbiter_agent = _new_visual_arbiter()

    # --- Diagnosis (consumes the state from the specialists + arbiter) ------
    diagnosis_agent = LlmAgent(
        name="diagnosis_specialist",
        model=MODEL,
        description="Determines the probable cause and fix based on Zebra documentation.",
        instruction=(
            "You are the label print DEFECT DIAGNOSIS specialist. Consider "
            "the evidence already collected:\n"
            "- Code reading: {reading?}\n"
            "- Quality indicators: {indicators?}\n"
            "- Classified defect (possibly CORRECTED by the visual arbiter — "
            "always use this as the authoritative defect class): {defect_data?}\n\n"
            "Build a short description of the symptoms (defect class + "
            "anomalous indicators) and call the `search_zebra_docs` tool "
            "passing that description. Based on what the tool returns, report: "
            "probable_cause, suggested correction, a brief rationale and the "
            "cited source. Base your answer only on the retrieved "
            "documentation."
        ),
        tools=[search_zebra_docs],
        output_key="diagnosis",
    )

    # --- Final report (consolidates everything into JSON) -------------------
    report_agent = LlmAgent(
        name="report_consolidator",
        model=MODEL,
        description="Consolidates reading, indicators, defect and diagnosis into a JSON report.",
        instruction=(
            "You consolidate the FINAL REPORT of the inspection. Gather all "
            "the evidence:\n"
            "- Reading: {reading?}\n"
            "- Indicators: {indicators?}\n"
            "- Defect (possibly corrected by the visual arbiter): {defect_data?}\n"
            "- Diagnosis: {diagnosis?}\n\n"
            "Produce a SINGLE valid JSON object, with no text before or after "
            "and no code fences (```), containing exactly these keys: "
            "readable, code_detected, symbology, content, ocr_text, "
            "indicators, defect, probable_cause, corrective_action, "
            "reasoning, source, diagnosis_method, overall_confidence, errors. "
            "Use the values from the evidence above; for missing fields use "
            "null, \"\", {} or []. The diagnosis_method field must reflect the "
            "origin of the diagnosis and overall_confidence the confidence of "
            "the classified defect."
        ),
        output_key="report",
    )

    root = SequentialAgent(
        name="label_inspector_root",
        sub_agents=[parallel_analysis, visual_arbiter_agent, diagnosis_agent, report_agent],
    )
    return root


# ---------------------------------------------------------------------------
# Graph execution via Runner.
# ---------------------------------------------------------------------------
def _detect_barcode(image_path: str) -> tuple[dict, bool]:
    """Read the label and decide whether a barcode is present (ADK short-circuit).

    Mirrors the presence check of ``tools.analyze_image`` (decode + OCR, then
    ``vision.has_barcode`` on grayscale) so the ADK path can skip the whole
    agent graph when there is nothing to inspect — saving CNN work and paid
    Gemini calls, exactly like the direct pipeline.

    Params:
        image_path: filesystem path of the label image.

    Returns:
        ``(reading, code_detected)`` — ``reading`` is the ``decode_code`` dict
        (or ``{}`` on failure); ``code_detected`` is ``True`` when the code is
        readable or ``vision.has_barcode`` detects a code region.

    Side effects / failure modes:
        Never raises; any error degrades to ``({}, False)`` / a best-effort
        partial reading. No Google import is triggered on this path.
    """
    reading: dict = {}
    try:
        reading = decode_code(image_path)
    except Exception:
        reading = {}

    code_detected = bool(isinstance(reading, dict) and reading.get("readable") is True)
    if not code_detected:
        try:
            image = vision.load_image(image_path)
            gray = vision.to_gray(image)
            code_detected = bool(vision.has_barcode(gray)[0])
        except Exception:
            pass
    return (reading if isinstance(reading, dict) else {}), code_detected


def _diagnosis_from_report_text(final_text: str) -> dict:
    """Extract the diagnosis PROSE fields from the report agent's JSON output.

    The perception state (``reading_data``/``indicators_data``/``defect_data``)
    is deterministic tool output, but the diagnosis narrative
    (probable cause / correction / rationale / source) is LLM prose. The
    report-consolidator agent already emits it as JSON; here we parse that
    JSON and reshape it into the dict shape ``report.build_report`` expects
    (``rationale``/``method`` keys), so the deterministic report keeps the
    authoritative structured state AND the LLM's grounded narrative.

    Params:
        final_text: raw text emitted by the report-consolidating LlmAgent.

    Returns:
        ``{"probable_cause", "corrective_action", "rationale", "source",
        "method"}`` — empty strings for whatever the agent did not provide.

    Side effects / failure modes:
        None; delegates parsing to ``_text_to_report`` which never raises.
    """
    parsed = _text_to_report(final_text)
    if not isinstance(parsed, dict):
        parsed = {}
    return {
        "probable_cause": parsed.get("probable_cause", "") or "",
        "corrective_action": parsed.get("corrective_action", "") or "",
        "rationale": parsed.get("reasoning", "") or "",
        "source": parsed.get("source", "") or "",
        "method": parsed.get("diagnosis_method", "") or "gemini",
    }


def _build_arbiter_root():
    """Build the lean single-agent graph (visual arbiter only) for the hot path."""
    from google.adk.agents import SequentialAgent
    return SequentialAgent(
        name="label_inspector_arbiter",
        sub_agents=[_new_visual_arbiter()],
    )


def _arbiter_gate(defect: dict) -> bool:
    """Python-side gate deciding whether the visual arbiter is worth invoking.

    Fires only when the CNN's top-2 classes are a configured confusable pair
    (``settings.ARBITER_PAIRS``) AND it is a near-tie (gap within
    ``ARBITER_MARGIN``) or low-confidence (top-1 below ``ARBITER_MIN_CONFIDENCE``).
    Doing this in Python — before any LLM call — means the (paid) arbiter runs
    only on the rare ambiguous cases, keeping the common path Gemini-free.
    """
    probs = (defect or {}).get("probs") or {}
    if len(probs) < 2:
        return False
    top = sorted(probs.items(), key=lambda kv: kv[1], reverse=True)
    (c1, p1), (c2, p2) = top[0], top[1]
    if frozenset({c1, c2}) not in settings.ARBITER_PAIRS:
        return False
    return (p1 - p2) <= settings.ARBITER_MARGIN or p1 < settings.ARBITER_MIN_CONFIDENCE


async def _run_visual_arbiter(image_path: str, defect: dict, indicators: dict) -> dict:
    """Run ONLY the visual arbiter through the ADK on a seeded session.

    Perception is already done; we seed the session state with ``defect_data``
    and ``indicators_data`` and let the arbiter agent + its multimodal tool
    possibly overwrite ``defect_data``. Returns the (possibly corrected) defect
    dict; the caller wraps this in try/except so any failure keeps the CNN class.
    """
    from google.adk.runners import Runner
    from google.adk.sessions import InMemorySessionService
    from google.genai import types

    global _arbiter_root
    if _arbiter_root is None:
        _arbiter_root = _build_arbiter_root()

    session_id = uuid.uuid4().hex
    session_service = InMemorySessionService()
    creation = session_service.create_session(
        app_name=_APP_NAME, user_id=_USER_ID, session_id=session_id,
        state={"defect_data": dict(defect), "indicators_data": dict(indicators or {})},
    )
    if inspect.isawaitable(creation):
        await creation

    runner = Runner(agent=_arbiter_root, app_name=_APP_NAME, session_service=session_service)
    message = types.Content(role="user", parts=[types.Part(text=image_path)])
    async for _event in runner.run_async(
        user_id=_USER_ID, session_id=session_id, new_message=message
    ):
        pass

    getter = session_service.get_session(
        app_name=_APP_NAME, user_id=_USER_ID, session_id=session_id
    )
    session = await getter if inspect.isawaitable(getter) else getter
    new_defect = dict(getattr(session, "state", None) or {}).get("defect_data")
    return new_defect if isinstance(new_defect, dict) else defect


async def analyze_via_adk(image_path: str,
                          language: str = settings.DEFAULT_LANGUAGE) -> dict:
    """Run the label analysis for the ADK ("Auto") path and return the report.

    Optimized, free-tier-friendly orchestration:
      1. no-barcode short-circuit (no CNN, no Gemini);
      2. DETERMINISTIC perception — decode + indicators + CNN, zero Gemini calls;
      3. the visual arbiter (the one stage that needs multimodal reasoning) runs
         THROUGH the ADK, but only when the Python gate (``_arbiter_gate``) fires
         on a confusable near-tie pair — so most analyses cost 0 arbiter calls;
      4. diagnosis via ``diagnosis.diagnose`` — one grounded Gemini call with a
         deterministic rule-based fallback;
      5. deterministic report assembly via ``report.build_report``.

    This keeps the ADK genuinely orchestrating the arbitration (the article's
    multi-agent contribution) while cutting per-analysis Gemini calls from ~6
    (one LlmAgent per stage) to ~1–2, fitting a free-tier quota. The full agent
    graph (``build_root_agent`` / module ``root_agent``) is kept for ``adk web``.

    Params:
        image_path: filesystem path of the label image to analyze.
        language: report language ("pt-BR" or "en-US").

    Returns:
        A dict following the 14-key report contract (``report.Report``).

    Failure modes:
        Never raises. Without a barcode it returns a minimal report; if the ADK
        arbiter is unavailable/fails the CNN class is kept; diagnosis degrades to
        rules when Gemini is unavailable. All google imports stay LAZY.
    """
    language = settings.normalize_language(language)

    # 1) Short-circuit: no barcode -> minimal report, no CNN, no Gemini. -----
    reading, code_detected = _detect_barcode(image_path)
    if not code_detected:
        return build_report(
            reading=reading, indicators={}, defect={}, diagnosis={},
            code_detected=False,
            errors=["No barcode detected in the image."],
        ).to_dict()

    # 2) Deterministic perception (zero Gemini calls). -----------------------
    try:
        indicators = estimate_indicators(image_path)
    except Exception:
        indicators = {}
    defect = classify_defect(image_path)
    if not isinstance(defect, dict):
        defect = {}

    # 3) Visual arbiter (ADK) — only for a confusable near-tie pair. ---------
    if settings.has_gemini() and _arbiter_gate(defect):
        try:
            defect = await _run_visual_arbiter(image_path, defect, indicators)
        except Exception:
            pass  # any ADK/Gemini failure -> keep the CNN class

    # 4) Diagnosis: one grounded Gemini call, deterministic rules fallback. --
    diagnosis = diagnosis_mod.diagnose(
        defect, reading, indicators,
        use_gemini=settings.has_gemini(), language=language,
    )

    # 5) Deterministic report assembly. --------------------------------------
    errors: list[str] = []
    for label, payload in (("reading", reading), ("defect", defect)):
        if isinstance(payload, dict) and payload.get("error"):
            errors.append(f"{label}: {payload['error']}")

    return build_report(
        reading=reading, indicators=indicators, defect=defect,
        diagnosis=diagnosis, code_detected=True, errors=errors,
    ).to_dict()


def _text_to_report(text: str) -> dict:
    """Convert the report agent's final text into a ``dict``.

    Tolerates code fences (```json ... ```) and stray text surrounding the
    JSON payload. If the text cannot be parsed as JSON, returns a minimal
    report dict with the raw text preserved under ``errors``.

    Params:
        text: raw text produced by the report-consolidating LlmAgent.

    Returns:
        A dict following the report contract's top-level keys (readable,
        code_detected, symbology, content, ocr_text, indicators, defect,
        probable_cause, corrective_action, reasoning, source,
        diagnosis_method, overall_confidence, errors). When parsing succeeds,
        the dict is whatever JSON object the agent produced (assumed to
        follow that same shape). When parsing fails, a minimal fallback dict
        is returned instead.

    Side effects:
        None (pure function).

    Failure modes:
        Never raises; any JSON-parsing exception is caught internally and
        results in the fallback dict being returned.
    """
    raw = (text or "").strip()

    # 1) direct attempt.
    try:
        return json.loads(raw)
    except Exception:
        pass

    # 2) strip code fences and try again.
    cleaned = raw
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()
        try:
            return json.loads(cleaned)
        except Exception:
            pass

    # 3) extract the first {...} block from the text.
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if 0 <= start < end:
        try:
            return json.loads(cleaned[start:end + 1])
        except Exception:
            pass

    # 4) fallback: minimal report with the raw text preserved.
    return {
        "readable": None,
        "code_detected": None,
        "symbology": None,
        "content": None,
        "ocr_text": "",
        "indicators": {},
        "defect": {},
        "probable_cause": "",
        "corrective_action": "",
        "reasoning": raw,
        "source": "",
        "diagnosis_method": "gemini",
        "overall_confidence": 0.0,
        "errors": ["ADK report agent did not return valid JSON"],
    }


# ---------------------------------------------------------------------------
# Root agent exposed for `adk web` / `adk run`.
# Guarded by try/except: if the ADK is missing, `root_agent` stays None and
# the module still imports normally.
# ---------------------------------------------------------------------------
try:
    root_agent = build_root_agent()
except Exception:
    root_agent = None
