"""Pipeline do Laboratório 03 — Granulometria Morfológica sobre a base KTH-TIPS.

Fluxo:
    1. Carrega o subconjunto (3 classes) em tons de cinza.
    2. Calcula a assinatura granulométrica (pattern spectrum) de cada imagem.
    3. Exporta as assinaturas para CSV.
    4. Gera as figuras: exemplos da base, assinaturas individuais + média por
       classe, comparação das médias e curvas cumulativas.
    5. Faz a análise quantitativa de separabilidade: matriz de distâncias entre
       as assinaturas médias e um classificador 1-NN leave-one-out (com matriz
       de confusão) sobre as assinaturas individuais.

Uso:
    uv run python executar.py
"""

from __future__ import annotations

import glob
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from granulometria import calcular_assinatura, carregar_cinza

# --------------------------------------------------------------------------- #
# Configuração do experimento
# --------------------------------------------------------------------------- #
AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
DIR_DADOS = os.path.join(RAIZ, "dados")
DIR_SAIDA = os.path.join(RAIZ, "resultados")

CLASSES = ["corduroy", "cotton", "linen"]  # 2 tecidos finos (semelhantes) + veludo cotelê
N_POR_CLASSE = 20                          # imagens por classe (faixa permitida: 10–20)
TAMANHO = 200                              # todas as imagens em 200x200 tons de cinza
RAIO_MAX = 25                              # faixa de escalas: raios 1..25
FORMA = "elipse"                           # elemento estruturante isotrópico (disco)

# Paleta consistente e amigável a daltônicos (uma cor por classe).
CORES = {"corduroy": "#4C72B0", "cotton": "#DD8452", "linen": "#55A868"}


# --------------------------------------------------------------------------- #
# 1–2. Carregamento e cálculo das assinaturas
# --------------------------------------------------------------------------- #
def listar_imagens(classe: str) -> list[str]:
    arquivos = sorted(glob.glob(os.path.join(DIR_DADOS, classe, "*.png")))
    if len(arquivos) < N_POR_CLASSE:
        raise RuntimeError(f"Classe '{classe}': {len(arquivos)} imagens (< {N_POR_CLASSE}).")
    return arquivos[:N_POR_CLASSE]


def computar_assinaturas() -> tuple[dict, np.ndarray]:
    """Retorna {classe: matriz (N x R) de pattern spectra} e o vetor de raios."""
    assinaturas: dict[str, np.ndarray] = {}
    raios = None
    for classe in CLASSES:
        linhas = []
        for caminho in listar_imagens(classe):
            img = carregar_cinza(caminho, TAMANHO)
            a = calcular_assinatura(img, raio_max=RAIO_MAX, forma=FORMA)
            linhas.append(a.pattern_spectrum)
            raios = a.raios
        assinaturas[classe] = np.vstack(linhas)
        print(f"  {classe:10s}: {assinaturas[classe].shape[0]} assinaturas x {len(raios)} raios")
    return assinaturas, raios


def curvas_cumulativas() -> dict[str, np.ndarray]:
    """Curvas Phi(r) médias por classe (para a figura cumulativa)."""
    medias = {}
    for classe in CLASSES:
        linhas = [
            calcular_assinatura(carregar_cinza(c, TAMANHO), raio_max=RAIO_MAX, forma=FORMA).curva_cumulativa
            for c in listar_imagens(classe)
        ]
        medias[classe] = np.vstack(linhas).mean(axis=0)
    return medias


# --------------------------------------------------------------------------- #
# 3. Exportação das assinaturas para CSV
# --------------------------------------------------------------------------- #
def exportar_csv(assinaturas: dict, raios: np.ndarray) -> None:
    registros = []
    for classe in CLASSES:
        for i, ps in enumerate(assinaturas[classe]):
            reg = {"classe": classe, "imagem": i}
            reg.update({f"r{r}": v for r, v in zip(raios, ps)})
            registros.append(reg)
    df = pd.DataFrame(registros)
    caminho = os.path.join(DIR_SAIDA, "assinaturas.csv")
    df.to_csv(caminho, index=False)
    print(f"  CSV salvo: {caminho}")


# --------------------------------------------------------------------------- #
# 4. Figuras
# --------------------------------------------------------------------------- #
def fig_exemplos() -> None:
    """Grade com exemplos de cada classe."""
    n_ex = 4
    fig, axes = plt.subplots(len(CLASSES), n_ex, figsize=(2.2 * n_ex, 2.2 * len(CLASSES)))
    for lin, classe in enumerate(CLASSES):
        for col, caminho in enumerate(listar_imagens(classe)[:n_ex]):
            ax = axes[lin, col]
            ax.imshow(carregar_cinza(caminho, TAMANHO), cmap="gray")
            ax.set_xticks([]); ax.set_yticks([])
            if col == 0:
                ax.set_ylabel(classe, fontsize=12, color=CORES[classe], fontweight="bold")
    fig.suptitle("Exemplos da base KTH-TIPS (tons de cinza, 200×200)", fontsize=13)
    fig.tight_layout()
    _salvar(fig, "exemplos_base.png")


def fig_individuais(assinaturas: dict, raios: np.ndarray) -> None:
    """Assinaturas individuais (finas) + média (grossa) por classe."""
    fig, axes = plt.subplots(1, len(CLASSES), figsize=(5 * len(CLASSES), 4), sharey=True)
    for ax, classe in zip(axes, CLASSES):
        M = assinaturas[classe]
        for ps in M:
            ax.plot(raios, ps, color=CORES[classe], alpha=0.25, linewidth=1)
        ax.plot(raios, M.mean(axis=0), color="black", linewidth=2.5, linestyle="--", label="média")
        ax.set_title(f"{classe}  (n={M.shape[0]})", color=CORES[classe], fontweight="bold")
        ax.set_xlabel("raio r do elemento estruturante")
        ax.grid(alpha=0.3)
        ax.legend()
    axes[0].set_ylabel("PS(r) — fração de massa na escala r")
    fig.suptitle("Assinaturas granulométricas individuais e média por classe", fontsize=13)
    fig.tight_layout()
    _salvar(fig, "assinaturas_individuais.png")


def fig_comparacao(assinaturas: dict, raios: np.ndarray) -> None:
    """Médias das classes sobrepostas, com banda de ±1 desvio-padrão."""
    fig, ax = plt.subplots(figsize=(8, 5))
    for classe in CLASSES:
        M = assinaturas[classe]
        media, desvio = M.mean(axis=0), M.std(axis=0)
        ax.plot(raios, media, color=CORES[classe], linewidth=2.5, label=classe)
        ax.fill_between(raios, media - desvio, media + desvio, color=CORES[classe], alpha=0.15)
    ax.set_xlabel("raio r do elemento estruturante")
    ax.set_ylabel("PS(r) — fração de massa na escala r")
    ax.set_title("Comparação das assinaturas granulométricas médias (±1 desvio)")
    ax.grid(alpha=0.3)
    ax.legend()
    fig.tight_layout()
    _salvar(fig, "assinaturas_comparacao.png")


def fig_cumulativa(cumul: dict, raios: np.ndarray) -> None:
    """Curvas granulométricas cumulativas médias Phi(r)."""
    fig, ax = plt.subplots(figsize=(8, 5))
    for classe in CLASSES:
        ax.plot(raios, cumul[classe], color=CORES[classe], linewidth=2.5, label=classe)
    ax.set_xlabel("raio r do elemento estruturante")
    ax.set_ylabel(r"$\Phi(r) = 1 - V(r)/V(0)$")
    ax.set_title("Curvas granulométricas cumulativas médias por classe")
    ax.grid(alpha=0.3)
    ax.legend()
    fig.tight_layout()
    _salvar(fig, "curvas_cumulativas.png")


def fig_confusao(matriz: np.ndarray, titulo: str, nome: str) -> None:
    fig, ax = plt.subplots(figsize=(4.5, 4))
    im = ax.imshow(matriz, cmap="Blues")
    ax.set_xticks(range(len(CLASSES))); ax.set_xticklabels(CLASSES, rotation=30, ha="right")
    ax.set_yticks(range(len(CLASSES))); ax.set_yticklabels(CLASSES)
    ax.set_xlabel("classe prevista"); ax.set_ylabel("classe verdadeira")
    limite = matriz.max()
    for i in range(len(CLASSES)):
        for j in range(len(CLASSES)):
            ax.text(j, i, int(matriz[i, j]), ha="center", va="center",
                    color="white" if matriz[i, j] > limite / 2 else "black", fontsize=12)
    ax.set_title(titulo)
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    fig.tight_layout()
    _salvar(fig, nome)


def _salvar(fig, nome: str) -> None:
    caminho = os.path.join(DIR_SAIDA, nome)
    fig.savefig(caminho, dpi=150)
    plt.close(fig)
    print(f"  Figura salva: {caminho}")


# --------------------------------------------------------------------------- #
# 5. Análise quantitativa de separabilidade
# --------------------------------------------------------------------------- #
def matriz_distancias(assinaturas: dict) -> pd.DataFrame:
    """Distância L1 entre as assinaturas médias das classes."""
    medias = {c: assinaturas[c].mean(axis=0) for c in CLASSES}
    D = np.zeros((len(CLASSES), len(CLASSES)))
    for i, a in enumerate(CLASSES):
        for j, b in enumerate(CLASSES):
            D[i, j] = np.abs(medias[a] - medias[b]).sum()
    return pd.DataFrame(D, index=CLASSES, columns=CLASSES)


def classificar_loo(assinaturas: dict) -> tuple[float, np.ndarray]:
    """1-NN leave-one-out sobre as assinaturas individuais (distância L1).

    Mede, de forma objetiva, o quanto as assinaturas separam as classes.
    """
    X, y = [], []
    for idx, classe in enumerate(CLASSES):
        for ps in assinaturas[classe]:
            X.append(ps); y.append(idx)
    X = np.vstack(X); y = np.asarray(y)
    n = len(y)
    confusao = np.zeros((len(CLASSES), len(CLASSES)), dtype=int)
    acertos = 0
    for i in range(n):
        dist = np.abs(X - X[i]).sum(axis=1)
        dist[i] = np.inf  # exclui a própria amostra
        pred = y[int(np.argmin(dist))]
        confusao[y[i], pred] += 1
        acertos += int(pred == y[i])
    return acertos / n, confusao


# --------------------------------------------------------------------------- #
# Orquestração
# --------------------------------------------------------------------------- #
def main() -> None:
    os.makedirs(DIR_SAIDA, exist_ok=True)
    print("== Configuração ==")
    print(f"  classes={CLASSES}  n/classe={N_POR_CLASSE}  raio_max={RAIO_MAX}  forma={FORMA}\n")

    print("== Calculando assinaturas ==")
    assinaturas, raios = computar_assinaturas()
    cumul = curvas_cumulativas()

    print("\n== Exportando dados ==")
    exportar_csv(assinaturas, raios)

    print("\n== Gerando figuras ==")
    fig_exemplos()
    fig_individuais(assinaturas, raios)
    fig_comparacao(assinaturas, raios)
    fig_cumulativa(cumul, raios)

    print("\n== Análise quantitativa ==")
    D = matriz_distancias(assinaturas)
    D.to_csv(os.path.join(DIR_SAIDA, "distancias_L1.csv"))
    print("Distância L1 entre assinaturas médias:")
    print(D.round(3).to_string())

    acc, confusao = classificar_loo(assinaturas)
    fig_confusao(confusao, f"1-NN LOO — acurácia {acc:.1%}", "matriz_confusao.png")

    # Raio de pico e massa total por classe (para a análise do relatório).
    print("\nResumo por classe:")
    resumo = []
    for classe in CLASSES:
        m = assinaturas[classe].mean(axis=0)
        raio_pico = int(raios[int(np.argmax(m))])
        massa = float(m.sum())
        resumo.append({"classe": classe, "raio_pico": raio_pico, "massa_total_PS": round(massa, 3)})
        print(f"  {classe:10s} raio_pico={raio_pico:2d}  massa_total_PS={massa:.3f}")
    pd.DataFrame(resumo).to_csv(os.path.join(DIR_SAIDA, "resumo_classes.csv"), index=False)

    print(f"\n1-NN leave-one-out: acurácia = {acc:.1%}")
    print("Matriz de confusão (linha=verdadeira, coluna=prevista):")
    print(pd.DataFrame(confusao, index=CLASSES, columns=CLASSES).to_string())
    print("\nConcluído. Resultados em:", DIR_SAIDA)


if __name__ == "__main__":
    main()
