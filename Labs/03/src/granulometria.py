"""Granulometria morfológica em tons de cinza (Laboratório 03 — Visão Computacional).

A ideia central é caracterizar uma imagem pela forma como ela "desaparece" quando
aplicamos aberturas morfológicas com elementos estruturantes de tamanho crescente.

Definições (Maragos, 1989):

    - f              : imagem em tons de cinza (float).
    - rB             : elemento estruturante B escalado por r (aqui, disco/elipse de raio r).
    - gamma_r(f)     : abertura de f por rB. É anti-extensiva e, quanto maior r,
                       mais estruturas finas são removidas.
    - V(r)           : "volume" de intensidade da imagem aberta = soma dos pixels.
                       V(0) = soma da imagem original (abertura por um ponto = identidade).

    Curva granulométrica (distribuição de tamanhos, cumulativa):
        Phi(r) = 1 - V(r) / V(0)          (cresce de 0 a ~1)

    Assinatura granulométrica / pattern spectrum (densidade):
        PS(r) = Phi(r) - Phi(r-1) = [V(r-1) - V(r)] / V(0)   (>= 0)

    PS(r) mede a fração de "massa" da imagem composta por estruturas de tamanho
    exatamente r. É a assinatura que descreve a distribuição de escalas da textura.
"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np


@dataclass
class Assinatura:
    """Assinatura granulométrica de uma imagem."""

    raios: np.ndarray          # raios usados (1..R)
    pattern_spectrum: np.ndarray  # PS(r), densidade normalizada (soma ~= Phi(R))
    curva_cumulativa: np.ndarray  # Phi(r) = 1 - V(r)/V(0), cresce de 0 a ~1
    classe: str = ""
    arquivo: str = ""


def _elemento(raio: int, forma: str) -> np.ndarray:
    """Elemento estruturante isotrópico de raio `raio` (tamanho 2*raio+1)."""
    formas = {
        "elipse": cv2.MORPH_ELLIPSE,   # disco (isotrópico) — padrão
        "quadrado": cv2.MORPH_RECT,
        "cruz": cv2.MORPH_CROSS,
    }
    tam = 2 * raio + 1
    return cv2.getStructuringElement(formas[forma], (tam, tam))


def calcular_assinatura(
    imagem: np.ndarray,
    raio_max: int = 25,
    passo: int = 1,
    forma: str = "elipse",
) -> Assinatura:
    """Calcula a assinatura granulométrica de uma imagem em tons de cinza.

    Args:
        imagem: array 2D (uint8 ou float) em tons de cinza.
        raio_max: maior raio do elemento estruturante (define a faixa de escalas).
        passo: incremento de raio entre escalas consecutivas.
        forma: "elipse" (disco), "quadrado" ou "cruz".

    Returns:
        Assinatura com pattern spectrum e curva cumulativa.
    """
    f = imagem.astype(np.float64)
    volume_inicial = float(f.sum())
    if volume_inicial <= 0:
        raise ValueError("Imagem sem volume de intensidade (soma <= 0).")

    raios = np.arange(passo, raio_max + 1, passo, dtype=int)

    volumes = [volume_inicial]  # V(0)
    for r in raios:
        aberta = cv2.morphologyEx(f, cv2.MORPH_OPEN, _elemento(int(r), forma))
        volumes.append(float(aberta.sum()))

    volumes = np.asarray(volumes)               # [V(0), V(r1), V(r2), ...]
    cumulativa = 1.0 - volumes[1:] / volume_inicial          # Phi(r)
    # Perda de volume entre escalas consecutivas (>= 0 pois a abertura é decrescente).
    pattern = np.maximum(0.0, -np.diff(volumes)) / volume_inicial  # PS(r)

    return Assinatura(
        raios=raios,
        pattern_spectrum=pattern,
        curva_cumulativa=cumulativa,
    )


def carregar_cinza(caminho: str, tamanho: int | None = 200) -> np.ndarray:
    """Carrega uma imagem em tons de cinza e, opcionalmente, redimensiona para
    `tamanho` x `tamanho` (interpolação por área — boa para reduzir)."""
    img = cv2.imread(caminho, cv2.IMREAD_GRAYSCALE)
    if img is None:
        raise FileNotFoundError(f"Não foi possível ler a imagem: {caminho}")
    if tamanho is not None and img.shape != (tamanho, tamanho):
        img = cv2.resize(img, (tamanho, tamanho), interpolation=cv2.INTER_AREA)
    return img
