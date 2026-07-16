"""Converte resultados/resultados.json em fragmentos de tabela LaTeX (pt-BR).

Uso: python formatar_tabelas.py [caminho_json]
Imprime, na saída padrão, os blocos prontos para colar no artigo.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from inspetor import config

CLASSE_LABEL = {
    "sem_defeito": "Sem defeito",
    "cabeca_queimada": "Cabeça queimada",
    "ribbon_enrugado": "\\textit{Ribbon} enrugado",
    "ponto_queimado": "Ponto queimado",
    "impressao_clara": "Impressão clara",
    "pressao_desigual": "Pressão desigual",
    "cabeca_suja": "Cabeça suja",
}
ROT_CURTO = {
    "sem_defeito": "sem defeito",
    "cabeca_queimada": "cab. queimada",
    "ribbon_enrugado": "\\textit{ribbon} enrug.",
    "ponto_queimado": "ponto queim.",
    "impressao_clara": "impr. clara",
    "pressao_desigual": "pressão desig.",
    "cabeca_suja": "cabeça suja",
}


def v(x):
    """Formata número no padrão brasileiro (vírgula)."""
    return f"{x:.2f}".replace(".", ",")


def tabela_por_classe(m):
    linhas = []
    for c in config.CLASSES:
        pc = m["por_classe"][c]
        linhas.append(f"{CLASSE_LABEL[c]} & {v(pc['precisao'])} & {v(pc['revocacao'])} "
                      f"& {v(pc['f1'])} & {pc['n']}\\\\")
    macro = (f"\\textbf{{Macro / total}} & \\textbf{{{v(m['macro_precisao'])}}} & "
             f"\\textbf{{{v(m['macro_revocacao'])}}} & \\textbf{{{v(m['macro_f1'])}}} & "
             f"\\textbf{{{sum(m['por_classe'][c]['n'] for c in config.CLASSES)}}}\\\\")
    return "\n".join(linhas) + "\n\\midrule\n" + macro


def tabela_confusao(m):
    M = m["matriz_confusao"]
    linhas = []
    for i, c in enumerate(config.CLASSES):
        vals = " & ".join(str(x) for x in M[i])
        linhas.append(f"{CLASSE_LABEL[c]} & {vals}\\\\")
    return "\n".join(linhas)


def tabela_baselines(d):
    sf = d["split_fixo"]
    linhas = []
    for rot, m in sf.items():
        params = m.get("n_parametros", 0) / 1e6
        neg = "\\textbf{" if rot == "MobileNetV3-Small" else ""
        fim = "}" if rot == "MobileNetV3-Small" else ""
        linhas.append(
            f"{neg}{rot}{fim} & {neg}{v(m['acuracia'])}{fim} & {neg}{v(m['macro_f1'])}{fim} "
            f"& {params:.1f} & {m.get('latencia_ms','--')}\\\\")
    return "\n".join(linhas)


def tabela_kfold(d):
    kf = d["kfold"]
    linhas = []
    for rot, m in kf.items():
        neg = "\\textbf{" if rot == "MobileNetV3-Small" else ""
        fim = "}" if rot == "MobileNetV3-Small" else ""
        linhas.append(
            f"{neg}{rot}{fim} & {neg}{v(m['acuracia_media'])}\\,$\\pm$\\,{v(m['acuracia_desvio'])}{fim} "
            f"& {neg}{v(m['f1_media'])}\\,$\\pm$\\,{v(m['f1_desvio'])}{fim}\\\\")
    return "\n".join(linhas)


def bloco_mcnemar(d):
    out = []
    for par, r in d["mcnemar"].items():
        p = r["p_valor"]
        sig = "significativa" if p < 0.05 else "não significativa (p$\\geq$0,05)"
        out.append(f"  {par}: b={r['b']}, c={r['c']}, p={v(p) if p>=0.01 else f'{p:.4f}'.replace('.',',')} ({sig})")
    return "\n".join(out)


def main():
    caminho = Path(sys.argv[1]) if len(sys.argv) > 1 else config.RAIZ / "resultados" / "resultados.json"
    d = json.loads(Path(caminho).read_text(encoding="utf-8"))

    print("=" * 70)
    print("CONFIG:", json.dumps(d["config"], ensure_ascii=False))
    print("=" * 70)

    if "MobileNetV3-Small" in d["split_fixo"]:
        m = d["split_fixo"]["MobileNetV3-Small"]
        print("\n### Cabeçalho quantitativo (MobileNetV3-Small) ###")
        print(f"acurácia = {v(m['acuracia'])} | macro P/R/F1 = "
              f"{v(m['macro_precisao'])}/{v(m['macro_revocacao'])}/{v(m['macro_f1'])}")
        print("\n### tab-metricas (por classe) ###")
        print(tabela_por_classe(m))
        print("\n### tab-confusao (matriz) ###")
        print(tabela_confusao(m))

    if len(d["split_fixo"]) > 1:
        print("\n### tab-baselines (Arquitetura & Acc & MacroF1 & Params(M) & Latência(ms)) ###")
        print(tabela_baselines(d))

    if d["mcnemar"]:
        print("\n### McNemar ###")
        print(bloco_mcnemar(d))

    if d["kfold"]:
        print("\n### tab-kfold (Arquitetura & Acc & MacroF1) ###")
        print(tabela_kfold(d))


if __name__ == "__main__":
    main()
