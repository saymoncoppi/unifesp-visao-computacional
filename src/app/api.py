"""HTTP API for the label inspector (FastAPI).

Starts a server that serves the chat interface and exposes the analysis
pipeline.

Routes:
    GET  /               -> chat page (app/chat.html)
    GET  /health         -> {"status": "ok"}
    POST /analyze        -> receives an image (field `image`) and returns the
                             report JSON. Optional query `adk=true` uses the
                             multi-agent graph (ADK).
    POST /analyze-htmx   -> receives an image (+ form fields `language`,
                             `inspector`) and returns the report card as an
                             HTML fragment (used by chat.html's htmx hx-post).

Run:
    # uvicorn app.api:app --reload
"""
from __future__ import annotations

import html
import os
import tempfile
from pathlib import Path

from fastapi import FastAPI, File, Form, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from config.inspector import settings
from config.inspector.tools import analyze_image

# Path to the chat page, next to this module.
_CHAT_HTML = Path(__file__).resolve().parent / "chat.html"

app = FastAPI(
    title="Label Inspector",
    description="Analyzes barcode labels and issues a defect report.",
    version="0.1.0",
)

# Static files (local htmx, etc.). Served at /static.
app.mount("/static", StaticFiles(directory="app/static"), name="static")


def _active_model_js() -> str:
    """Return the active LLM model name, safe for embedding in JS.

    Returns:
        The Gemini model name (e.g. "gemini-1.5-flash") with backslashes and
        quotes stripped for safe injection into a JS string literal, or an
        empty string when Gemini is not configured.
    """
    if not settings.has_gemini():
        return ""
    model = settings.GEMINI_MODEL or ""
    # The value comes from config/environment (trusted), but quotes/backslashes
    # are stripped defensively since it is injected inside a JS string on the page.
    return model.replace("\\", "").replace('"', "").replace("'", "").strip()


@app.get("/", response_class=HTMLResponse)
def index() -> HTMLResponse:
    """Serve the chat interface (self-contained HTML).

    Injects the active LLM model into the page (for the "Inspector" selector)
    by replacing the ``__ACTIVE_MODEL__`` and ``__HAS_GEMINI__`` placeholders.

    Returns:
        HTMLResponse with the rendered chat page, or a 500 error page if
        ``chat.html`` cannot be read from disk.
    """
    try:
        page = _CHAT_HTML.read_text(encoding="utf-8")
    except OSError as exc:
        return HTMLResponse(
            f"<h1>Interface unavailable</h1><p>{exc}</p>",
            status_code=500,
        )
    page = page.replace("__ACTIVE_MODEL__", _active_model_js()).replace(
        "__HAS_GEMINI__", "true" if settings.has_gemini() else "false"
    )
    return HTMLResponse(page)


@app.get("/health")
def health() -> dict:
    """Health check endpoint for the service."""
    return {"status": "ok"}


@app.get("/quota")
def quota() -> JSONResponse:
    """Current Gemini free-tier quota state, for the footer counter.

    Returns a JSON snapshot of the rolling requests-per-minute window plus the
    active model name. The client polls this on load and after each analysis
    and counts ``reset_in`` down locally, so this endpoint is hit rarely (never
    per-second). When no key is configured, ``enabled`` is ``false`` and the
    footer status stays hidden.

    Returns:
        JSONResponse with ``enabled``, ``model``, ``limit``, ``used``,
        ``remaining``, ``reset_in`` (seconds) and ``blocked``.
    """
    from config.inspector import ratelimit

    if not settings.has_gemini():
        return JSONResponse({"enabled": False})
    snap = ratelimit.snapshot()
    snap.update(enabled=True, model=_active_model_js() or settings.GEMINI_MODEL)
    return JSONResponse(snap)


@app.post("/analyze")
async def analyze(image: UploadFile = File(...), adk: bool = False) -> JSONResponse:
    """Receive an image, run the analysis pipeline, and return the report.

    Args:
        image: Uploaded image (multipart/form-data field `image`).
        adk: When True, tries the multi-agent (ADK) graph first and falls back
            to the direct pipeline if the ADK path raises any exception.

    Returns:
        JSONResponse with the report dict on success, or
        ``{"error": <message>}`` with HTTP 500 on failure.

    Side effects:
        Writes the uploaded image to a temporary file (the pipeline works
        with file paths) and always removes it afterwards, regardless of
        the outcome.
    """
    suffix = Path(image.filename or "").suffix or ".png"
    temp_path = None
    try:
        image_bytes = await image.read()
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(image_bytes)
            temp_path = tmp.name

        if adk:
            try:
                from config.inspector.agents import analyze_via_adk

                report = await analyze_via_adk(temp_path)
            except Exception as exc:  # noqa: BLE001 - deliberate fallback
                report = analyze_image(temp_path)
                report.setdefault("errors", []).append(
                    f"ADK unavailable ({exc}); used the direct pipeline instead."
                )
        else:
            report = analyze_image(temp_path)

        return JSONResponse(report)
    except Exception as exc:  # noqa: BLE001 - do not leak the stacktrace to the client
        return JSONResponse(
            {"error": f"Failed to analyze the image: {exc}"},
            status_code=500,
        )
    finally:
        if temp_path:
            try:
                os.remove(temp_path)
            except OSError:
                pass


# ---------------------------------------------------------------------------
# HTMX -- HTML fragment (report card, shadcn/ui aesthetic).
# ---------------------------------------------------------------------------
# Fixed card labels, per language. Dynamic content (cause/correction) already
# comes translated from the pipeline (see config.inspector.diagnosis).
_LABELS = {
    "pt-BR": {
        "report_title": "Laudo de inspeção",
        "readable": "Legível",
        "unreadable": "Ilegível",
        "reading_unavailable": "Leitura indisponível",
        "no_code": "Nenhum código de barras detectado na imagem.",
        "reading": "Leitura",
        "ocr_text": "Texto (OCR):",
        "not_decoded": "Não foi possível decodificar o código.",
        "indicators": "Indicadores de qualidade",
        "ind_contrast": "Contraste",
        "ind_uniformity": "Uniformidade",
        "ind_sharpness": "Nitidez",
        "defect": "Defeito",
        "confidence": "Confiança:",
        "visual_evidence": "Evidência visual",
        "visual_review": "revisão visual",
        "cause": "Causa provável",
        "correction": "Correção sugerida",
        "source": "Fonte:",
        "via_rules": "regras",
        "warnings": "Avisos",
        "analysis_failure": "Falha ao analisar a imagem:",
    },
    "en-US": {
        "report_title": "Inspection report",
        "readable": "Readable",
        "unreadable": "Unreadable",
        "reading_unavailable": "Reading unavailable",
        "no_code": "No barcode detected in the image.",
        "reading": "Reading",
        "ocr_text": "Text (OCR):",
        "not_decoded": "The code could not be decoded.",
        "indicators": "Quality indicators",
        "ind_contrast": "Contrast",
        "ind_uniformity": "Uniformity",
        "ind_sharpness": "Sharpness",
        "defect": "Defect",
        "confidence": "Confidence:",
        "visual_evidence": "Visual evidence",
        "visual_review": "visual review",
        "cause": "Probable cause",
        "correction": "Suggested correction",
        "source": "Source:",
        "via_rules": "rules",
        "warnings": "Warnings",
        "analysis_failure": "Failed to analyze the image:",
    },
}

# Display order of the indicators and the label key for each one.
_INDICATORS = (
    ("contrast", "ind_contrast"),
    ("uniformity", "ind_uniformity"),
    ("sharpness", "ind_sharpness"),
)


def _label(language: str, key: str) -> str:
    """Look up a fixed card label in the requested language.

    Args:
        language: Language code ("pt-BR" or "en-US"); normalized internally.
        key: Label key from ``_LABELS``.

    Returns:
        The label string in ``language``, falling back to pt-BR and then to
        ``key`` itself if not found in either table.
    """
    table = _LABELS.get(settings.normalize_language(language), _LABELS["pt-BR"])
    return table.get(key) or _LABELS["pt-BR"].get(key, key)


def _esc(value) -> str:
    """Escape a value coming from the server for safe insertion into HTML."""
    if value is None:
        return ""
    return html.escape(str(value))


def _pct(value) -> str:
    """Format a [0, 1] fraction as an integer percentage; '—' if not numeric."""
    if isinstance(value, (int, float)):
        return f"{round(value * 100)}%"
    return "—"


def _pct_width(value) -> int:
    """Convert a [0, 1] fraction into a meter bar width (0-100), clamped defensively."""
    if not isinstance(value, (int, float)):
        return 0
    return max(0, min(100, round(value * 100)))


def _report_card_html(report: dict, language: str = settings.DEFAULT_LANGUAGE) -> str:
    """Build the report card (HTML fragment), styled like shadcn/ui cards.

    All data coming from the report is escaped with ``html.escape`` before
    being inserted into the HTML. The CSS classes used here match the ones
    defined in ``chat.html``. Fixed labels follow ``language``; dynamic
    content (probable cause / corrective action) already comes translated
    from the pipeline.

    Args:
        report: Report dict following the FINALIZED REPORT CONTRACT keys
            (readable, code_detected, symbology, content, ocr_text,
            indicators, defect, probable_cause, corrective_action, source,
            diagnosis_method, errors, ...), as produced by ``analyze_image``
            or ``analyze_via_adk``.
        language: Display language for the fixed labels ("pt-BR" or "en-US").

    Returns:
        An HTML fragment (string) ready to be appended to the chat.
    """
    language = settings.normalize_language(language)
    parts: list[str] = []
    parts.append('<div class="msg msg-bot">')
    parts.append('<div class="avatar" aria-hidden="true">IE</div>')
    parts.append('<div class="card report">')

    # -- Card header + readability badge -----------------------------------
    readable = report.get("readable")
    if readable is True:
        badge = f'<span class="badge badge-ok">{_esc(_label(language, "readable"))}</span>'
    elif readable is False:
        badge = f'<span class="badge badge-bad">{_esc(_label(language, "unreadable"))}</span>'
    else:
        badge = (f'<span class="badge badge-muted">'
                 f'{_esc(_label(language, "reading_unavailable"))}</span>')
    parts.append(
        '<div class="card-header">'
        f'<h3 class="card-title">{_esc(_label(language, "report_title"))}</h3>'
        f"{badge}"
        "</div>"
    )

    # -- Highlighted alert: no barcode found in the image -------------------
    if report.get("code_detected") is False:
        parts.append(
            '<div class="alert alert-nocode"><div class="alert-title">'
            f"⚠️ {_esc(_label(language, 'no_code'))}"
            "</div></div>"
        )
        # No code detected: the report is reduced to this warning -- no
        # reading, indicators, defect, or diagnosis (the pipeline doesn't
        # even compute them in this case).
        parts.append("</div>")  # .card
        parts.append("</div>")  # .msg
        return "".join(parts)

    # -- Reading (symbology / content / OCR) --------------------------------
    reading_html = [
        '<div class="section"><div class="section-label">'
        f'{_esc(_label(language, "reading"))}</div>'
    ]
    if readable is True:
        symbology = _esc(report.get("symbology") or "?")
        content = _esc(report.get("content") or "")
        reading_html.append(
            f'<div class="kv"><span class="k">{symbology}:</span> '
            f'<span class="mono">{content}</span></div>'
        )
    ocr = (report.get("ocr_text") or "").strip()
    if ocr:
        reading_html.append(
            f'<div class="ocr">{_esc(_label(language, "ocr_text"))} {_esc(ocr)}</div>'
        )
    if readable is not True and not ocr:
        reading_html.append(
            f'<div class="section-body">{_esc(_label(language, "not_decoded"))}</div>'
        )
    reading_html.append("</div>")
    parts.append("".join(reading_html))

    # -- Indicators (bars) ---------------------------------------------------
    indicators = report.get("indicators") or {}
    keys = [(k, lbl) for k, lbl in _INDICATORS
            if isinstance(indicators.get(k), (int, float))]
    if keys:
        ind_html = [
            '<div class="section"><div class="section-label">'
            f'{_esc(_label(language, "indicators"))}</div>'
        ]
        for k, lbl in keys:
            v = indicators.get(k)
            ind_html.append(
                '<div class="meter">'
                '<div class="meter-head">'
                f"<span>{_esc(_label(language, lbl))}</span>"
                f'<span class="val">{_pct(v)}</span>'
                "</div>"
                f'<div class="track"><span class="fill" style="width:{_pct_width(v)}%"></span></div>'
                "</div>"
            )
        ind_html.append("</div>")
        parts.append("".join(ind_html))

    # -- Defect (localized name + confidence) --------------------------------
    defect = report.get("defect") or {}
    defect_class = defect.get("class")
    if defect_class:
        name = settings.class_display_name(defect_class, language)
    else:
        name = defect.get("class_label") or "—"
    def_html = [
        '<div class="section"><div class="section-label">'
        f'{_esc(_label(language, "defect"))}</div>',
        f'<div class="defect-name">{_esc(name)}</div>',
    ]
    # Visual arbitration seal: the CNN class was overridden by the visual
    # arbiter. Show "CNN: <original> (<prob>%) -> visual review: <final>".
    if defect.get("arbitrated") is True and defect.get("original_class"):
        orig_key = defect.get("original_class")
        orig_name = settings.class_display_name(orig_key, language)
        orig_probs = defect.get("probs") or {}
        orig_prob = orig_probs.get(orig_key)
        prob_txt = _pct(orig_prob) if isinstance(orig_prob, (int, float)) else "—"
        def_html.append(
            '<div class="defect-conf defect-arbitration">'
            f'CNN: {_esc(orig_name)} ({_esc(prob_txt)}) → '
            f'{_esc(_label(language, "visual_review"))}: {_esc(name)}'
            "</div>"
        )
    if isinstance(defect.get("confidence"), (int, float)):
        def_html.append(
            f'<div class="defect-conf">{_esc(_label(language, "confidence"))} '
            f'{_pct(defect.get("confidence"))}</div>'
        )
    # Visual evidence text produced by the visual arbiter (ADK path only).
    visual_evidence = defect.get("visual_evidence")
    if visual_evidence:
        def_html.append(
            '<div class="section-label sub-label">'
            f'{_esc(_label(language, "visual_evidence"))}</div>'
            f'<div class="section-body">{_esc(visual_evidence)}</div>'
        )
    def_html.append("</div>")
    parts.append("".join(def_html))

    # -- Probable cause --------------------------------------------------------
    parts.append(
        '<div class="section"><div class="section-label">'
        f'{_esc(_label(language, "cause"))}</div>'
        f'<div class="section-body">{_esc(report.get("probable_cause") or "—")}</div></div>'
    )

    # -- Suggested correction ----------------------------------------------------
    parts.append(
        '<div class="section"><div class="section-label">'
        f'{_esc(_label(language, "correction"))}</div>'
        f'<div class="section-body">{_esc(report.get("corrective_action") or "—")}</div></div>'
    )

    # -- Source / diagnosis method -------------------------------------------------
    source = report.get("source")
    method = report.get("diagnosis_method")
    if source or method:
        footer = []
        if source:
            footer.append(f'{_label(language, "source")} {_esc(source)}')
        if method:
            method_txt = "Gemini" if method == "gemini" else (
                _label(language, "via_rules") if method == "rules" else method
            )
            footer.append(f"via {_esc(method_txt)}")
        parts.append(f'<div class="card-footer">{"  •  ".join(footer)}</div>')

    # -- Warnings (errors) -------------------------------------------------------
    errors = report.get("errors")
    if isinstance(errors, list) and errors:
        items = "".join(f"<li>{_esc(e)}</li>" for e in errors)
        parts.append(
            '<div class="alert"><div class="alert-title">'
            f'{_esc(_label(language, "warnings"))}</div>'
            f"<ul>{items}</ul></div>"
        )

    parts.append("</div>")  # .card
    parts.append("</div>")  # .msg
    return "".join(parts)


def _error_card_html(message: str) -> str:
    """Build an error bubble (HTML fragment) for analysis failures."""
    return (
        '<div class="msg msg-bot">'
        '<div class="avatar" aria-hidden="true">IE</div>'
        f'<div class="bubble is-error">⚠️ {_esc(message)}</div>'
        "</div>"
    )


@app.post("/analyze-htmx", response_class=HTMLResponse)
async def analyze_htmx(
    image: UploadFile = File(...),
    language: str = Form(settings.DEFAULT_LANGUAGE),
    inspector: str = Form("llm"),
) -> HTMLResponse:
    """HTMX variant: receive an image and return the report card as HTML.

    Saves the image to a temporary file, runs ``analyze_image``, and returns
    an HTML FRAGMENT (shadcn-styled card) to be appended to the chat. The
    temporary file is always removed in the ``finally`` block.

    Args:
        image: Uploaded image (multipart/form-data field `image`).
        language: Report language (pt-BR/en-US).
        inspector: Engine selector -- ``"kb"`` forces the Zebra knowledge base
            (rules); ``"llm"`` runs the direct pipeline with Gemini; ``"auto"``
            runs the multi-agent (ADK) graph with visual arbitration when an
            LLM is configured, falling back to the direct pipeline on any ADK
            failure (and to plain Gemini when no LLM is configured).

    Returns:
        HTMLResponse with the report card fragment, or an error card fragment
        with HTTP 500 on failure.
    """
    language = settings.normalize_language(language)
    suffix = Path(image.filename or "").suffix or ".png"
    temp_path = None
    try:
        image_bytes = await image.read()
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(image_bytes)
            temp_path = tmp.name

        if inspector == "auto" and settings.has_gemini():
            # Multi-agent path (ADK) with visual arbitration. On any ADK
            # failure, degrade to the direct Gemini pipeline so the user still
            # gets a report.
            try:
                from config.inspector.agents import analyze_via_adk

                report = await analyze_via_adk(temp_path)
            except Exception as exc:  # noqa: BLE001 - deliberate fallback
                report = analyze_image(temp_path, use_gemini=True, language=language)
                report.setdefault("errors", []).append(
                    f"ADK unavailable ({exc}); used the direct pipeline instead."
                )
        else:
            # "llm" -> direct pipeline with Gemini; "kb" -> rules only.
            use_gemini = inspector != "kb"
            report = analyze_image(temp_path, use_gemini=use_gemini, language=language)
        return HTMLResponse(_report_card_html(report, language))
    except Exception as exc:  # noqa: BLE001 - do not leak the stacktrace to the client
        return HTMLResponse(
            _error_card_html(f"{_label(language, 'analysis_failure')} {exc}"),
            status_code=500,
        )
    finally:
        if temp_path:
            try:
                os.remove(temp_path)
            except OSError:
                pass


# uvicorn app.api:app --reload
