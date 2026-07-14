"""Base de conhecimento Zebra (defeito -> causa -> ação corretiva).

Mapeamento das 7 classes de defeito de impressão térmica para a causa provável e a
ação corretiva recomendada, com base na documentação das impressoras Zebra ZT411 /
ZT421 (Zebra Technologies, 2024). Usada tanto na recuperação por palavra-chave
quanto na montagem do contexto enviado ao LLM (Gemini) e no fallback por regras.
"""
from __future__ import annotations

from inspetor import config

# TODO: enriquecer com JSON extraído dos PDFs Zebra

FONTE = "Zebra Technologies (2024)"

# --------------------------------------------------------------------------
# Base de conhecimento (uma entrada por classe de config.CLASSES)
# --------------------------------------------------------------------------
KB: list[dict] = [
    {
        "classe": "sem_defeito",
        "aparencia": "Código limpo e nítido, barras uniformes, dentro da "
                     "especificação de qualidade.",
        "aparencia_en": "Clean, sharp code with uniform bars, within the quality "
                        "specification.",
        "causa_provavel": "Impressão dentro da especificação; nenhum defeito "
                          "detectado.",
        "causa_provavel_en": "Print within specification; no defect detected.",
        "acao_corretiva": "Nada a corrigir; manter os parâmetros atuais de "
                          "darkness, velocidade e pressão.",
        "acao_corretiva_en": "Nothing to fix; keep the current darkness, speed and "
                             "pressure settings.",
        "parametros": [],
        "fonte": FONTE,
    },
    {
        "classe": "cabeca_queimada",
        "aparencia": "Linhas brancas verticais contínuas / trilhas de impressão "
                     "faltando ao longo de toda a etiqueta.",
        "aparencia_en": "Continuous vertical white lines / missing print tracks "
                        "running the full length of the label.",
        "causa_provavel": "Elemento (dot) da cabeça de impressão danificado ou "
                          "queimado.",
        "causa_provavel_en": "Damaged or burnt printhead element (dot).",
        "acao_corretiva": "Acionar a assistência técnica para troca da cabeça de "
                          "impressão; elementos queimados não se recuperam com "
                          "limpeza.",
        "acao_corretiva_en": "Contact service to replace the printhead; burnt "
                             "elements are not recovered by cleaning.",
        "parametros": ["cabeca"],
        "fonte": FONTE,
    },
    {
        "classe": "ribbon_enrugado",
        "aparencia": "Linhas cinza finas e angulares (diagonais) atravessando a "
                     "impressão.",
        "aparencia_en": "Thin, angled (diagonal) gray lines crossing the print.",
        "causa_provavel": "Ribbon enrugado por tensão ou alinhamento incorretos no "
                          "percurso.",
        "causa_provavel_en": "Ribbon wrinkled by incorrect tension or alignment "
                             "along the path.",
        "acao_corretiva": "Corrigir a tensão e o alinhamento do ribbon; verificar o "
                          "percurso e a barra de tensão.",
        "acao_corretiva_en": "Correct the ribbon tension and alignment; check the "
                             "ribbon path and the tension bar.",
        "parametros": ["ribbon"],
        "fonte": FONTE,
    },
    {
        "classe": "ponto_queimado",
        "aparencia": "Manchas escuras, borrões e barras engrossadas (excesso de "
                     "tinta/energia).",
        "aparencia_en": "Dark blotches, smudges and thickened bars (excess "
                        "ink/energy).",
        "causa_provavel": "Nível de darkness (temperatura de queima) alto demais.",
        "causa_provavel_en": "Darkness level (burn temperature) set too high.",
        "acao_corretiva": "Reduzir o darkness; se necessário, reduzir a velocidade "
                          "de impressão.",
        "acao_corretiva_en": "Lower the darkness; if needed, reduce the print speed.",
        "parametros": ["darkness", "velocidade"],
        "fonte": FONTE,
    },
    {
        "classe": "impressao_clara",
        "aparencia": "Impressão fraca / esmaecida (faded), baixo contraste, barras "
                     "acinzentadas.",
        "aparencia_en": "Weak / faded print, low contrast, grayish bars.",
        "causa_provavel": "Darkness baixo, mídia/ribbon incompatíveis ou velocidade "
                          "alta demais.",
        "causa_provavel_en": "Low darkness, incompatible media/ribbon, or print "
                             "speed too high.",
        "acao_corretiva": "Elevar o darkness; usar mídia e ribbon adequados; reduzir "
                          "a velocidade se necessário.",
        "acao_corretiva_en": "Raise the darkness; use suitable media and ribbon; "
                             "reduce the speed if needed.",
        "parametros": ["darkness", "midia", "ribbon"],
        "fonte": FONTE,
    },
    {
        "classe": "pressao_desigual",
        "aparencia": "Um lado da etiqueta impresso claro e o outro escuro "
                     "(gradiente lateral de densidade).",
        "aparencia_en": "One side of the label printed light and the other dark "
                        "(lateral density gradient).",
        "causa_provavel": "Pressão desigual da cabeça de impressão sobre a mídia.",
        "causa_provavel_en": "Uneven printhead pressure against the media.",
        "acao_corretiva": "Ajustar a pressão da cabeça equilibrando os toggles "
                          "(molas de pressão) conforme a largura da mídia.",
        "acao_corretiva_en": "Adjust the printhead pressure by balancing the "
                             "toggles (pressure springs) to the media width.",
        "parametros": ["pressao"],
        "fonte": FONTE,
    },
    {
        "classe": "cabeca_suja",
        "aparencia": "Voids e falhas pontuais nas barras (pequenas áreas não "
                     "impressas espalhadas).",
        "aparencia_en": "Voids and spot failures in the bars (small unprinted areas "
                        "scattered around).",
        "causa_provavel": "Cabeça de impressão suja (acúmulo de adesivo, poeira ou "
                          "resíduo de ribbon).",
        "causa_provavel_en": "Dirty printhead (buildup of adhesive, dust or ribbon "
                             "residue).",
        "acao_corretiva": "Limpar a cabeça de impressão e o rolete (platen) com "
                          "álcool isopropílico 99,7%.",
        "acao_corretiva_en": "Clean the printhead and the platen roller with 99.7% "
                             "isopropyl alcohol.",
        "parametros": ["cabeca", "rolete"],
        "fonte": FONTE,
    },
]

# Índice por classe para busca O(1).
_POR_CLASSE: dict[str, dict] = {item["classe"]: item for item in KB}

# Sufixo de campo por idioma (pt-BR usa o campo base; en-US usa "<campo>_en").
_CAMPOS_LOCALIZAVEIS = ("aparencia", "causa_provavel", "acao_corretiva")


def campo_localizado(item: dict, campo: str, idioma: str = config.IDIOMA_PADRAO) -> str:
    """Valor de um campo da KB no idioma pedido (fallback: campo em português)."""
    if not item:
        return ""
    if config.normalizar_idioma(idioma) == "en-US" and campo in _CAMPOS_LOCALIZAVEIS:
        return item.get(f"{campo}_en") or item.get(campo, "")
    return item.get(campo, "")


def buscar_por_classe(classe: str) -> dict | None:
    """Retorna a entrada da KB para a classe informada, ou None se não existir."""
    if not classe:
        return None
    return _POR_CLASSE.get(classe)


def buscar(sintomas: str) -> list[dict]:
    """Recuperação simples por palavra-chave (case-insensitive).

    Procura os termos de `sintomas` na aparência, na causa provável e no nome
    (classe / rótulo em português) de cada entrada. Retorna as entradas cujo
    conteúdo contém qualquer um dos termos.
    """
    if not sintomas:
        return []
    termos = [t for t in sintomas.lower().split() if t]
    if not termos:
        return []
    resultados: list[dict] = []
    for item in KB:
        classe = item["classe"]
        alvo = " ".join([
            item.get("aparencia", ""),
            item.get("causa_provavel", ""),
            classe,
            config.CLASSE_PT.get(classe, ""),
        ]).lower()
        if any(termo in alvo for termo in termos):
            resultados.append(item)
    return resultados


def contexto_para_llm(classe: str, indicadores: dict, leitura: dict) -> str:
    """Monta o contexto textual (KB da classe + medidas) para o prompt do LLM."""
    item = buscar_por_classe(classe)
    classe_pt = config.CLASSE_PT.get(classe, classe or "desconhecida")

    linhas: list[str] = []
    linhas.append("BASE DE CONHECIMENTO ZEBRA (ZT411/ZT421)")
    linhas.append(f"Defeito classificado: {classe_pt} ({classe or '—'})")

    if item:
        params = ", ".join(item.get("parametros") or []) or "—"
        linhas.append(f"Aparência típica: {item.get('aparencia', '—')}")
        linhas.append(f"Causa provável (KB): {item.get('causa_provavel', '—')}")
        linhas.append(f"Ação corretiva (KB): {item.get('acao_corretiva', '—')}")
        linhas.append(f"Parâmetros envolvidos: {params}")
        linhas.append(f"Fonte: {item.get('fonte', FONTE)}")
    else:
        linhas.append("Nenhuma entrada correspondente na base de conhecimento.")
        linhas.append(f"Fonte: {FONTE}")

    ind = indicadores or {}
    linhas.append("")
    linhas.append("INDICADORES MEDIDOS (visão computacional):")
    linhas.append(f"- contraste: {ind.get('contraste', '—')}")
    linhas.append(f"- uniformidade: {ind.get('uniformidade', '—')}")
    linhas.append(f"- nitidez: {ind.get('nitidez', '—')}")

    lei = leitura or {}
    linhas.append("")
    linhas.append("LEITURA DO CÓDIGO:")
    linhas.append(f"- legível: {lei.get('legivel', '—')}")
    linhas.append(f"- simbologia: {lei.get('simbologia', '—')}")
    linhas.append(f"- conteúdo: {lei.get('conteudo', '—')}")

    return "\n".join(linhas)
