"""Zebra knowledge base (defect -> probable cause -> corrective action).

Maps the 7 thermal-printing defect classes to their probable cause and
recommended corrective action, based on the Zebra ZT411 / ZT421 printer
documentation (Zebra Technologies, 2024). Used both for keyword-based
retrieval and to build the context sent to the LLM (Gemini), as well as
in the rule-based fallback.

This module keeps the knowledge base inline (as a Python list of dicts)
rather than loading it from ``config/data/kb_zebra.json``; that JSON file
is a separate, richer raw-extraction resource (additional defects,
source excerpts, references) not consumed by this module.
"""
from __future__ import annotations

from config.inspector import settings

# TODO: enrich with JSON extracted from the Zebra PDFs

SOURCE = "Zebra Technologies (2024)"

# --------------------------------------------------------------------------
# Knowledge base (one entry per class in settings.CLASSES)
# --------------------------------------------------------------------------
KB: list[dict] = [
    {
        "class": "no_defect",
        "appearance_pt": "Código limpo e nítido, barras uniformes, dentro da "
                     "especificação de qualidade.",
        "appearance_en": "Clean, sharp code with uniform bars, within the quality "
                        "specification.",
        "probable_cause_pt": "Impressão dentro da especificação; nenhum defeito "
                          "detectado.",
        "probable_cause_en": "Print within specification; no defect detected.",
        "corrective_action_pt": "Nada a corrigir; manter os parâmetros atuais de "
                          "darkness, velocidade e pressão.",
        "corrective_action_en": "Nothing to fix; keep the current darkness, speed and "
                             "pressure settings.",
        "parameters": [],
        "source": SOURCE,
    },
    {
        "class": "damaged_printhead_element",
        "appearance_pt": "Linhas brancas verticais contínuas / trilhas de impressão "
                     "faltando ao longo de toda a etiqueta.",
        "appearance_en": "Continuous vertical white lines / missing print tracks "
                        "running the full length of the label.",
        "probable_cause_pt": "Elemento (dot) da cabeça de impressão danificado ou "
                          "queimado.",
        "probable_cause_en": "Damaged or burnt printhead element (dot).",
        "corrective_action_pt": "Acionar a assistência técnica para troca da cabeça de "
                          "impressão; elementos queimados não se recuperam com "
                          "limpeza.",
        "corrective_action_en": "Contact service to replace the printhead; burnt "
                             "elements are not recovered by cleaning.",
        "parameters": ["printhead"],
        "source": SOURCE,
    },
    {
        "class": "wrinkled_ribbon",
        "appearance_pt": "Linhas cinza finas e angulares (diagonais) atravessando a "
                     "impressão.",
        "appearance_en": "Thin, angled (diagonal) gray lines crossing the print.",
        "probable_cause_pt": "Ribbon enrugado por tensão ou alinhamento incorretos no "
                          "percurso.",
        "probable_cause_en": "Ribbon wrinkled by incorrect tension or alignment "
                             "along the path.",
        "corrective_action_pt": "Corrigir a tensão e o alinhamento do ribbon; verificar o "
                          "percurso e a barra de tensão.",
        "corrective_action_en": "Correct the ribbon tension and alignment; check the "
                             "ribbon path and the tension bar.",
        "parameters": ["ribbon"],
        "source": SOURCE,
    },
    {
        "class": "burnt_spot",
        "appearance_pt": "Manchas escuras, borrões e barras engrossadas (excesso de "
                     "tinta/energia).",
        "appearance_en": "Dark blotches, smudges and thickened bars (excess "
                        "ink/energy).",
        "probable_cause_pt": "Nível de darkness (temperatura de queima) alto demais.",
        "probable_cause_en": "Darkness level (burn temperature) set too high.",
        "corrective_action_pt": "Reduzir o darkness; se necessário, reduzir a velocidade "
                          "de impressão.",
        "corrective_action_en": "Lower the darkness; if needed, reduce the print speed.",
        "parameters": ["darkness", "speed"],
        "source": SOURCE,
    },
    {
        "class": "light_print",
        "appearance_pt": "Impressão fraca / esmaecida (faded), baixo contraste, barras "
                     "acinzentadas.",
        "appearance_en": "Weak / faded print, low contrast, grayish bars.",
        "probable_cause_pt": "Darkness baixo, mídia/ribbon incompatíveis ou velocidade "
                          "alta demais.",
        "probable_cause_en": "Low darkness, incompatible media/ribbon, or print "
                             "speed too high.",
        "corrective_action_pt": "Elevar o darkness; usar mídia e ribbon adequados; reduzir "
                          "a velocidade se necessário.",
        "corrective_action_en": "Raise the darkness; use suitable media and ribbon; "
                             "reduce the speed if needed.",
        "parameters": ["darkness", "media", "ribbon"],
        "source": SOURCE,
    },
    {
        "class": "uneven_pressure",
        "appearance_pt": "Um lado da etiqueta impresso claro e o outro escuro "
                     "(gradiente lateral de densidade).",
        "appearance_en": "One side of the label printed light and the other dark "
                        "(lateral density gradient).",
        "probable_cause_pt": "Pressão desigual da cabeça de impressão sobre a mídia.",
        "probable_cause_en": "Uneven printhead pressure against the media.",
        "corrective_action_pt": "Ajustar a pressão da cabeça equilibrando os toggles "
                          "(molas de pressão) conforme a largura da mídia.",
        "corrective_action_en": "Adjust the printhead pressure by balancing the "
                             "toggles (pressure springs) to the media width.",
        "parameters": ["pressure"],
        "source": SOURCE,
    },
    {
        "class": "dirty_printhead",
        "appearance_pt": "Voids e falhas pontuais nas barras (pequenas áreas não "
                     "impressas espalhadas).",
        "appearance_en": "Voids and spot failures in the bars (small unprinted areas "
                        "scattered around).",
        "probable_cause_pt": "Cabeça de impressão suja (acúmulo de adesivo, poeira ou "
                          "resíduo de ribbon).",
        "probable_cause_en": "Dirty printhead (buildup of adhesive, dust or ribbon "
                             "residue).",
        "corrective_action_pt": "Limpar a cabeça de impressão e o rolete (platen) com "
                          "álcool isopropílico 99,7%.",
        "corrective_action_en": "Clean the printhead and the platen roller with 99.7% "
                             "isopropyl alcohol.",
        "parameters": ["printhead", "platen"],
        "source": SOURCE,
    },
]

# Index by class for O(1) lookup.
_BY_CLASS: dict[str, dict] = {item["class"]: item for item in KB}

# Field suffix per language (pt-BR and en-US both use an explicit
# "<field>_pt" / "<field>_en" suffix; there is no unsuffixed base field).
_LOCALIZABLE_FIELDS = ("appearance", "probable_cause", "corrective_action")


def localized_field(item: dict, field: str, language: str = settings.DEFAULT_LANGUAGE) -> str:
    """Return the value of a localizable KB field in the requested language.

    Parameters:
        item: A KB entry (one of the dicts in ``KB``), or ``None``/empty.
        field: Base field name, one of ``_LOCALIZABLE_FIELDS`` (e.g.
            ``"appearance"``, ``"probable_cause"``, ``"corrective_action"``).
            The actual dict keys are ``f"{field}_pt"`` and ``f"{field}_en"``.
        language: Requested language code (e.g. ``"pt-BR"``, ``"en-US"``);
            normalized via ``settings.normalize_language``.

    Returns:
        The value of ``f"{field}_en"`` when the normalized language is
        ``"en-US"`` and ``field`` is in ``_LOCALIZABLE_FIELDS``; otherwise
        the value of ``f"{field}_pt"``. Falls back to ``""`` if ``item`` is
        falsy, if ``field`` is not localizable, or if the resolved key is
        missing from ``item``.

    Side effects:
        None (pure function).
    """
    if not item:
        return ""
    if field not in _LOCALIZABLE_FIELDS:
        return ""
    lang_suffix = "en" if settings.normalize_language(language) == "en-US" else "pt"
    return item.get(f"{field}_{lang_suffix}", "")


def search_by_class(defect_class: str) -> dict | None:
    """Look up the KB entry for a given defect class.

    Parameters:
        defect_class: One of the keys in ``settings.CLASSES`` (e.g.
            ``"no_defect"``), or ``None``/empty.

    Returns:
        The matching entry from ``KB``, or ``None`` if ``defect_class`` is
        falsy or has no corresponding entry.

    Side effects:
        None (pure function; does not mutate ``KB``).
    """
    if not defect_class:
        return None
    return _BY_CLASS.get(defect_class)


def search(symptoms: str) -> list[dict]:
    """Simple case-insensitive keyword retrieval over the knowledge base.

    Parameters:
        symptoms: Free-text description of observed symptoms. Split on
            whitespace into individual (lowercased) search terms.

    Returns:
        The list of KB entries (in ``KB`` order) whose appearance, probable
        cause, class key, or Portuguese display label contain at least one
        of the search terms. Returns an empty list if ``symptoms`` is
        empty/falsy or contains no usable terms.

    Side effects:
        None (pure function; does not mutate ``KB``).
    """
    if not symptoms:
        return []
    terms = [t for t in symptoms.lower().split() if t]
    if not terms:
        return []
    results: list[dict] = []
    for item in KB:
        defect_class = item["class"]
        haystack = " ".join([
            item.get("appearance_pt", ""),
            item.get("appearance_en", ""),
            item.get("probable_cause_pt", ""),
            item.get("probable_cause_en", ""),
            defect_class,
            settings.CLASS_LABELS_PT.get(defect_class, ""),
        ]).lower()
        if any(term in haystack for term in terms):
            results.append(item)
    return results


def context_for_llm(defect_class: str, indicators: dict, reading: dict) -> str:
    """Build the textual context (KB entry + measurements) for the LLM prompt.

    Parameters:
        defect_class: One of the keys in ``settings.CLASSES``, or
            ``None``/empty when no class is available.
        indicators: Computer-vision indicators dict, expected keys
            ``contrast``, ``uniformity``, ``sharpness`` (any may be absent).
        reading: Barcode/QR reading dict, expected keys ``readable``,
            ``symbology``, ``content`` (any may be absent).

    Returns:
        A multi-line string combining: the KB entry (appearance, probable
        cause, corrective action, related parameters, source) for
        ``defect_class`` — or a "no matching entry" notice if none exists —
        followed by the measured indicators and the code reading, ready to
        be embedded in the prompt sent to the LLM (Gemini).

    Side effects:
        None (pure function; does not call the LLM itself).
    """
    item = search_by_class(defect_class)
    class_label_pt = settings.CLASS_LABELS_PT.get(defect_class, defect_class or "desconhecida")

    lines: list[str] = []
    lines.append("BASE DE CONHECIMENTO ZEBRA (ZT411/ZT421)")
    lines.append(f"Defeito classificado: {class_label_pt} ({defect_class or '—'})")

    if item:
        params = ", ".join(item.get("parameters") or []) or "—"
        lines.append(f"Aparência típica: {item.get('appearance_pt', '—')}")
        lines.append(f"Causa provável (KB): {item.get('probable_cause_pt', '—')}")
        lines.append(f"Ação corretiva (KB): {item.get('corrective_action_pt', '—')}")
        lines.append(f"Parâmetros envolvidos: {params}")
        lines.append(f"Fonte: {item.get('source', SOURCE)}")
    else:
        lines.append("Nenhuma entrada correspondente na base de conhecimento.")
        lines.append(f"Fonte: {SOURCE}")

    ind = indicators or {}
    lines.append("")
    lines.append("INDICADORES MEDIDOS (visão computacional):")
    lines.append(f"- contraste: {ind.get('contrast', '—')}")
    lines.append(f"- uniformidade: {ind.get('uniformity', '—')}")
    lines.append(f"- nitidez: {ind.get('sharpness', '—')}")

    read = reading or {}
    lines.append("")
    lines.append("LEITURA DO CÓDIGO:")
    lines.append(f"- legível: {read.get('readable', '—')}")
    lines.append(f"- simbologia: {read.get('symbology', '—')}")
    lines.append(f"- conteúdo: {read.get('content', '—')}")

    return "\n".join(lines)
