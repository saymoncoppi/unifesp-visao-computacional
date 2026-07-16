"""Convert config/results/resultados.json into LaTeX table fragments (pt-BR).

Usage: python format_tables.py [json_path]
Prints, to standard output, blocks ready to paste into the article.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from config.inspector import settings

CLASS_LABEL = {
    "no_defect": "Sem defeito",
    "damaged_printhead_element": "Cabeça queimada",
    "wrinkled_ribbon": "\\textit{Ribbon} enrugado",
    "burnt_spot": "Ponto queimado",
    "light_print": "Impressão clara",
    "uneven_pressure": "Pressão desigual",
    "dirty_printhead": "Cabeça suja",
}
SHORT_LABEL = {
    "no_defect": "sem defeito",
    "damaged_printhead_element": "cab. queimada",
    "wrinkled_ribbon": "\\textit{ribbon} enrug.",
    "burnt_spot": "ponto queim.",
    "light_print": "impr. clara",
    "uneven_pressure": "pressão desig.",
    "dirty_printhead": "cabeça suja",
}


def _fmt(x):
    """Format a number using Brazilian Portuguese decimal notation (comma).

    Args:
        x: Numeric value to format (int or float).

    Returns:
        str: The value formatted with two decimal places and a comma as the
        decimal separator (e.g. ``0.85`` -> ``"0,85"``), matching the
        pt-BR numeric convention used in the article's LaTeX tables.

    Side effects:
        None.

    Failure modes:
        Raises ``TypeError`` if ``x`` does not support the ``:.2f`` format
        specifier.
    """
    return f"{x:.2f}".replace(".", ",")


def table_per_class(m):
    """Build the LaTeX rows of the per-class precision/recall/F1 table.

    Args:
        m: Metrics dict for a single model run, as stored in
            ``resultados.json``. Must contain ``"per_class"`` (a mapping
            of defect class key -> {"precision", "recall", "f1", "n"}),
            plus the aggregate keys ``"macro_precision"``,
            ``"macro_recall"`` and ``"macro_f1"``.

    Returns:
        str: LaTeX table body, one ``\\\\``-terminated row per defect class
        (in ``settings.CLASSES`` order) followed by a ``\\midrule`` and a
        bold "Macro / total" summary row.

    Side effects:
        None.

    Failure modes:
        Raises ``KeyError`` if any class in ``settings.CLASSES`` is missing
        from ``m["per_class"]``, or if the expected metric keys are absent.
    """
    rows = []
    for c in settings.CLASSES:
        class_metrics = m["per_class"][c]
        rows.append(f"{CLASS_LABEL[c]} & {_fmt(class_metrics['precision'])} & "
                    f"{_fmt(class_metrics['recall'])} "
                    f"& {_fmt(class_metrics['f1'])} & {class_metrics['n']}\\\\")
    macro = (f"\\textbf{{Macro / total}} & \\textbf{{{_fmt(m['macro_precision'])}}} & "
             f"\\textbf{{{_fmt(m['macro_recall'])}}} & \\textbf{{{_fmt(m['macro_f1'])}}} & "
             f"\\textbf{{{sum(m['per_class'][c]['n'] for c in settings.CLASSES)}}}\\\\")
    return "\n".join(rows) + "\n\\midrule\n" + macro


def confusion_table(m):
    """Build the LaTeX rows of the confusion matrix table.

    Args:
        m: Metrics dict for a single model run, as stored in
            ``resultados.json``. Must contain ``"confusion_matrix"``, a
            square matrix (list of lists) ordered like ``settings.CLASSES``.

    Returns:
        str: LaTeX table body, one ``\\\\``-terminated row per defect class,
        with the class label followed by its confusion-matrix counts.

    Side effects:
        None.

    Failure modes:
        Raises ``IndexError``/``KeyError`` if the matrix has fewer rows than
        ``settings.CLASSES``, or if a class key is missing from
        ``CLASS_LABEL``.
    """
    confusion_matrix = m["confusion_matrix"]
    rows = []
    for i, c in enumerate(settings.CLASSES):
        values = " & ".join(str(x) for x in confusion_matrix[i])
        rows.append(f"{CLASS_LABEL[c]} & {values}\\\\")
    return "\n".join(rows)


def baselines_table(d):
    """Build the LaTeX rows comparing baseline architectures on the fixed split.

    Args:
        d: Top-level results dict (parsed ``resultados.json``). Must contain
            ``"fixed_split"``, a mapping of architecture label -> metrics
            dict with ``"accuracy"``, ``"macro_f1"``, and optionally
            ``"n_params"`` and ``"latency_ms"``.

    Returns:
        str: LaTeX table body, one ``\\\\``-terminated row per architecture,
        with the "MobileNetV3-Small" row rendered in bold to highlight the
        adopted model. Columns: architecture, accuracy, macro F1, parameter
        count in millions, and latency in ms (``"--"`` if unavailable).

    Side effects:
        None.

    Failure modes:
        Raises ``KeyError`` if ``"fixed_split"`` or a required metric is
        missing.
    """
    fixed_split = d["fixed_split"]
    rows = []
    for label, m in fixed_split.items():
        params = m.get("n_params", 0) / 1e6
        bold_start = "\\textbf{" if label == "MobileNetV3-Small" else ""
        bold_end = "}" if label == "MobileNetV3-Small" else ""
        rows.append(
            f"{bold_start}{label}{bold_end} & {bold_start}{_fmt(m['accuracy'])}{bold_end} & "
            f"{bold_start}{_fmt(m['macro_f1'])}{bold_end} "
            f"& {params:.1f} & {m.get('latency_ms', '--')}\\\\")
    return "\n".join(rows)


def kfold_table(d):
    """Build the LaTeX rows summarizing k-fold cross-validation results.

    Args:
        d: Top-level results dict (parsed ``resultados.json``). Must contain
            ``"kfold"``, a mapping of architecture label -> metrics dict
            with ``"accuracy_mean"``, ``"accuracy_std"``, ``"f1_mean"``
            and ``"f1_std"``.

    Returns:
        str: LaTeX table body, one ``\\\\``-terminated row per architecture,
        formatted as mean ``\\pm`` standard deviation for accuracy and macro
        F1, with the "MobileNetV3-Small" row rendered in bold.

    Side effects:
        None.

    Failure modes:
        Raises ``KeyError`` if ``"kfold"`` or a required metric is missing.
    """
    kfold_data = d["kfold"]
    rows = []
    for label, m in kfold_data.items():
        bold_start = "\\textbf{" if label == "MobileNetV3-Small" else ""
        bold_end = "}" if label == "MobileNetV3-Small" else ""
        acc = f"{_fmt(m['accuracy_mean'])}\\,$\\pm$\\,{_fmt(m['accuracy_std'])}"
        f1 = f"{_fmt(m['f1_mean'])}\\,$\\pm$\\,{_fmt(m['f1_std'])}"
        rows.append(
            f"{bold_start}{label}{bold_end} & "
            f"{bold_start}{acc}{bold_end} & {bold_start}{f1}{bold_end}\\\\")
    return "\n".join(rows)


def mcnemar_block(d):
    """Build the plain-text summary of pairwise McNemar test results.

    Args:
        d: Top-level results dict (parsed ``resultados.json``). Must contain
            ``"mcnemar"``, a mapping of "model A vs model B" label -> result
            dict with ``"b"``, ``"c"`` (discordant-pair counts) and
            ``"p_value"`` (p-value).

    Returns:
        str: One line per comparison, reporting the discordant counts, the
        p-value (comma-formatted, with 4 decimal places below 0.01), and a
        Portuguese significance verdict ("significativa" /
        "não significativa (p>=0,05)") for direct inclusion in the article.

    Side effects:
        None.

    Failure modes:
        Raises ``KeyError`` if ``"mcnemar"`` or a required field is missing.
    """
    lines = []
    for pair, r in d["mcnemar"].items():
        p_value = r["p_value"]
        significance = "significativa" if p_value < 0.05 else "não significativa (p$\\geq$0,05)"
        p_str = _fmt(p_value) if p_value >= 0.01 else f"{p_value:.4f}".replace(".", ",")
        lines.append(f"  {pair}: b={r['b']}, c={r['c']}, p={p_str} ({significance})")
    return "\n".join(lines)


def main():
    """Entry point: read the results JSON and print all LaTeX table fragments.

    Reads the results file (path taken from ``sys.argv[1]`` if given,
    otherwise ``settings.ROOT / "config" / "results" / "resultados.json"``)
    and prints, to standard output, the config header followed by whichever
    table fragments are applicable: per-class metrics and confusion matrix
    for "MobileNetV3-Small" on the fixed split, a baselines comparison table
    (if more than one architecture was evaluated on the fixed split),
    McNemar test results (if present), and a k-fold summary table (if
    present).

    Args:
        None (reads from ``sys.argv``).

    Returns:
        None.

    Side effects:
        Reads a file from disk and writes to standard output.

    Failure modes:
        Raises ``FileNotFoundError`` if the results file does not exist,
        or ``json.JSONDecodeError`` if it is not valid JSON.
    """
    default_path = settings.ROOT / "config" / "results" / "resultados.json"
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else default_path
    data = json.loads(Path(path).read_text(encoding="utf-8"))

    print("=" * 70)
    print("CONFIG:", json.dumps(data["config"], ensure_ascii=False))
    print("=" * 70)

    if "MobileNetV3-Small" in data["fixed_split"]:
        metrics = data["fixed_split"]["MobileNetV3-Small"]
        print("\n### Quantitative header (MobileNetV3-Small) ###")
        print(f"accuracy = {_fmt(metrics['accuracy'])} | macro P/R/F1 = "
              f"{_fmt(metrics['macro_precision'])}/{_fmt(metrics['macro_recall'])}/"
              f"{_fmt(metrics['macro_f1'])}")
        print("\n### tab-metrics (per class) ###")
        print(table_per_class(metrics))
        print("\n### tab-confusion (matrix) ###")
        print(confusion_table(metrics))

    if len(data["fixed_split"]) > 1:
        print("\n### tab-baselines (Architecture & Acc & MacroF1 & Params(M) & Latency(ms)) ###")
        print(baselines_table(data))

    if data["mcnemar"]:
        print("\n### McNemar ###")
        print(mcnemar_block(data))

    if data["kfold"]:
        print("\n### tab-kfold (Architecture & Acc & MacroF1) ###")
        print(kfold_table(data))


if __name__ == "__main__":
    main()
