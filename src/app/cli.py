"""Command-line interface for the label inspector.

Usage:
    python -m app.cli PATH [--adk] [--json]

Without ``--adk`` it runs the direct pipeline (``config.inspector.tools.analyze_image``).
With ``--adk`` it tries the multi-agent graph (``config.inspector.agents.analyze_via_adk``)
and, if that fails for any reason (missing library, execution error), it falls back
to the direct pipeline — the analysis always happens regardless.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys

from config.inspector.tools import analyze_image


def _pct(value) -> str:
    """Format a number in [0, 1] as a readable percentage; '—' if absent.

    Args:
        value: The numeric value to format, expected to be in the range [0, 1].
            May be ``None`` or any non-numeric type, in which case a
            placeholder is returned.

    Returns:
        The formatted percentage string (e.g. ``"87%"``), or ``"—"`` when
        ``value`` is not an ``int``/``float``.
    """
    if isinstance(value, (int, float)):
        return f"{value:.0%}"
    return "—"


def _bar(value, width: int = 20) -> str:
    """Render a simple textual bar for an indicator in [0, 1].

    Args:
        value: The indicator value to render, expected to be in [0, 1].
            Values outside that range are clamped; non-numeric values
            produce a placeholder.
        width: Total number of characters in the bar. Defaults to 20.

    Returns:
        A string of filled (``█``) and empty (``░``) block characters
        representing the fraction, or ``"—"`` if ``value`` cannot be
        converted to ``float``.
    """
    try:
        fraction = max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return "—"
    filled = int(round(fraction * width))
    return "█" * filled + "░" * (width - filled)


def format_summary(report: dict) -> str:
    """Build a friendly, human-readable summary of the report (dict).

    Args:
        report: The report dictionary as produced by
            ``config.inspector.tools.analyze_image`` or
            ``config.inspector.agents.analyze_via_adk``. Expected to follow
            the finalized report contract (keys such as ``readable``,
            ``code_detected``, ``symbology``, ``content``,
            ``indicators``, ``defect``, ``probable_cause``,
            ``corrective_action``, ``source``, ``diagnosis_method``,
            ``errors``).

    Returns:
        A multi-line string with a boxed summary suitable for printing to
        a terminal.
    """
    readable = report.get("readable")
    if readable:
        state = "readable"
    elif readable is None:
        state = "reading unavailable"
    else:
        state = "unreadable"

    reading_line = f"Reading: {state}"
    if readable:
        symbology = report.get("symbology") or "?"
        content = report.get("content") or ""
        reading_line += f" — {symbology}: {content}"

    indicators = report.get("indicators") or {}
    indicator_lines = []
    labels = {
        "contrast": "Contrast",
        "uniformity": "Uniformity",
        "sharpness": "Sharpness",
    }
    for key, label in labels.items():
        if key in indicators:
            value = indicators.get(key)
            indicator_lines.append(f"    {label:<12} {_bar(value)} {_pct(value)}")

    defect = report.get("defect") or {}
    defect_class = defect.get("class_label") or defect.get("class") or "—"
    conf = defect.get("confidence")

    parts = [
        "=" * 52,
        "  INSPECTION REPORT — Label Inspector",
        "=" * 52,
    ]
    # Highlighted warning, at the top, when no barcode is found in the image.
    if report.get("code_detected") is False:
        parts.append("⚠ No barcode detected in the image.")
        parts.append("-" * 52)
    parts.append(reading_line)
    if indicator_lines:
        parts.append("Quality indicators:")
        parts.extend(indicator_lines)
    parts.extend([
        f"Defect: {defect_class} ({_pct(conf)})",
        f"Probable cause: {report.get('probable_cause') or '—'}",
        f"Corrective action: {report.get('corrective_action') or '—'}",
    ])

    source = report.get("source")
    method = report.get("diagnosis_method")
    if source or method:
        footer = "Source: " + (source or "—")
        if method:
            footer += f"  |  via: {method}"
        parts.append(footer)

    errors = report.get("errors") or []
    if errors:
        parts.append("Warnings:")
        parts.extend(f"    - {error}" for error in errors)

    parts.append("=" * 52)
    return "\n".join(parts)


def _run(path: str, use_adk: bool) -> dict:
    """Run the analysis, falling back from ADK to the direct pipeline.

    Args:
        path: Filesystem path to the label image to analyze.
        use_adk: If ``True``, attempt the multi-agent (ADK) pipeline first;
            on any failure (missing library, runtime error), fall back to
            the direct pipeline. If ``False``, use the direct pipeline
            directly.

    Returns:
        The report dictionary produced by whichever pipeline succeeded.

    Side Effects:
        Prints a warning to stderr if the ADK pipeline was requested but
        failed and the code fell back to the direct pipeline.
    """
    if use_adk:
        try:
            from config.inspector.agents import analyze_via_adk

            return asyncio.run(analyze_via_adk(path))
        except Exception as exc:  # noqa: BLE001 - deliberate, broad fallback
            print(
                f"[warning] ADK analysis unavailable ({exc}); "
                "using direct pipeline.",
                file=sys.stderr,
            )
    return analyze_image(path)


def main(argv: list[str] | None = None) -> int:
    """Entry point for ``python -m app.cli``.

    Parses command-line arguments, runs the label analysis, and prints
    either a human-readable summary or the full report as JSON.

    Args:
        argv: Optional list of command-line arguments (excluding the
            program name). If ``None``, arguments are taken from
            ``sys.argv``.

    Returns:
        Process exit code (``0`` on success).

    Side Effects:
        Clears the terminal screen when stdout is a tty. Prints the
        analysis result (summary or JSON) to stdout.
    """
    # Clear the terminal screen on launch (only when stdout is a terminal).
    if sys.stdout.isatty():
        try:
            os.system("cls" if os.name == "nt" else "clear")
        except Exception:  # noqa: BLE001 - clearing is a convenience, never critical
            pass

    parser = argparse.ArgumentParser(
        prog="app.cli",
        description="Analyzes a barcode label image and produces a report.",
    )
    parser.add_argument("path", help="Path to the label image to inspect.")
    parser.add_argument(
        "--adk",
        action="store_true",
        help="Use the multi-agent graph (ADK/Gemini); falls back to the direct pipeline on failure.",
    )
    parser.add_argument(
        "--json",
        dest="as_json",
        action="store_true",
        help="Print the full report as (indented) JSON.",
    )
    args = parser.parse_args(argv)

    report = _run(args.path, args.adk)

    if args.as_json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print(format_summary(report))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
