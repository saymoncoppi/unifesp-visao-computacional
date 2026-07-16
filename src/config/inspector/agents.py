"""Multi-agent orchestration with the ADK (Google Agent Development Kit).

Builds the label-inspector agent graph:

    ┌────────────────────── ParallelAgent ──────────────────────┐
    │  LlmAgent reading      (tool: decode_code)                │
    │  LlmAgent indicators   (tool: estimate_indicators)        │  → run in parallel
    │  LlmAgent defect       (tool: classify_defect)            │
    └─────────────────────────────────────────────────────────┘
                              │
                    LlmAgent diagnosis   (tool: search_zebra_docs)
                              │
                    LlmAgent report      (consolidates into JSON)

The root ``SequentialAgent`` executes: [parallel] → [diagnosis] → [report].

Every import of ``google.adk`` / ``google.genai`` is LAZY (done inside the
functions), so the module imports fine even without the ADK installed and
``python -m py_compile`` passes. The tools come from ``config.inspector.tools``.
"""
from __future__ import annotations

import inspect
import json

from config.inspector import settings
from config.inspector.tools import (
    classify_defect,
    decode_code,
    estimate_indicators,
    search_zebra_docs,
)

# Gemini model used by every LlmAgent in the graph.
MODEL = settings.GEMINI_MODEL

# Runner application/session identifiers.
_APP_NAME = "label_inspector"
_USER_ID = "user"
_SESSION_ID = "session"


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
    except ImportError as exc:
        raise ImportError(
            "google-adk is not installed. Install it with: pip install google-adk"
        ) from exc

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

    # --- Diagnosis (consumes the state from the three specialists) ----------
    diagnosis_agent = LlmAgent(
        name="diagnosis_specialist",
        model=MODEL,
        description="Determines the probable cause and fix based on Zebra documentation.",
        instruction=(
            "You are the label print DEFECT DIAGNOSIS specialist. Consider "
            "the evidence already collected:\n"
            "- Code reading: {reading?}\n"
            "- Quality indicators: {indicators?}\n"
            "- Classified defect: {defect?}\n\n"
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
            "- Defect: {defect?}\n"
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
        sub_agents=[parallel_analysis, diagnosis_agent, report_agent],
    )
    return root


# ---------------------------------------------------------------------------
# Graph execution via Runner.
# ---------------------------------------------------------------------------
async def analyze_via_adk(image_path: str) -> dict:
    """Run the label analysis THROUGH the ADK graph and return the report (dict).

    Creates a ``Runner`` with ``InMemorySessionService``, sends the image path
    as the user message, runs the root graph and returns the consolidated
    report (JSON emitted by the report agent, converted to a ``dict``).

    Params:
        image_path: filesystem path of the label image to analyze.

    Returns:
        A dict with the report-shaped keys produced by the report agent (see
        ``_text_to_report`` for the fallback shape when parsing fails).

    Side effects:
        Instantiates an in-memory ADK session and runs the full agent graph,
        which performs network calls to the Gemini API through the ADK
        runner.

    Failure modes:
        Raises ``ImportError`` with a clear message if the ADK / Gemini SDK
        are not available (the direct ``tools.analyze_image`` pipeline keeps
        working in that case).
    """
    try:
        from google.adk.runners import Runner
        from google.adk.sessions import InMemorySessionService
        from google.genai import types
    except ImportError as exc:
        raise ImportError(
            "ADK/Gemini are unavailable for agent-based execution. "
            "Install them with: pip install google-adk google-genai "
            "(or use the direct pipeline tools.analyze_image)."
        ) from exc

    root_agent_local = build_root_agent()

    session_service = InMemorySessionService()
    # create_session is async in recent ADK versions and sync in older
    # ones — we handle both cases.
    creation = session_service.create_session(
        app_name=_APP_NAME, user_id=_USER_ID, session_id=_SESSION_ID
    )
    if inspect.isawaitable(creation):
        await creation

    runner = Runner(
        agent=root_agent_local,
        app_name=_APP_NAME,
        session_service=session_service,
    )

    message = types.Content(
        role="user",
        parts=[types.Part(text=image_path)],
    )

    final_text = ""
    async for event in runner.run_async(
        user_id=_USER_ID, session_id=_SESSION_ID, new_message=message
    ):
        if event.is_final_response() and event.content and event.content.parts:
            parts = [p.text for p in event.content.parts if getattr(p, "text", None)]
            if parts:
                final_text = "".join(parts)

    return _text_to_report(final_text)


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
