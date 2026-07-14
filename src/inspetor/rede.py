"""Rede neural convolucional (CNN) para classificação de defeitos de impressão.

Usa transferência de aprendizado sobre a MobileNetV3-Small (torchvision). Todos os
imports pesados (torch/torchvision/PIL/numpy) são LAZY — ficam dentro das funções —
para que o pacote importe e `python -m py_compile` passe mesmo sem essas libs.
"""
from __future__ import annotations

from pathlib import Path

from inspetor import config


def _dispositivo(device=None):
    """Resolve o dispositivo de execução (CPU/GPU). Requer torch (import lazy)."""
    import torch

    if device is None:
        return torch.device("cuda" if torch.cuda.is_available() else "cpu")
    return torch.device(device)


def construir_modelo(num_classes: int = len(config.CLASSES),
                     backbone: str = config.BACKBONE,
                     preTreinado: bool = True):
    """Constrói a CNN de classificação (MobileNetV3-Small).

    Carrega o backbone (com pesos ImageNet se ``preTreinado``) e substitui a última
    camada ``Linear`` do ``classifier`` por uma nova de ``num_classes`` saídas.
    """
    import torch.nn as nn
    from torchvision import models

    pesos = None
    if preTreinado:
        try:
            pesos = models.MobileNet_V3_Small_Weights.DEFAULT
        except AttributeError:          # torchvision antigo, sem enum de pesos
            pesos = None

    try:
        modelo = models.mobilenet_v3_small(weights=pesos)
    except TypeError:                    # API legada usa `pretrained=`
        modelo = models.mobilenet_v3_small(pretrained=preTreinado)

    # A última camada do classifier é a Linear final (in_features -> 1000 no ImageNet).
    entradas = modelo.classifier[-1].in_features
    modelo.classifier[-1] = nn.Linear(entradas, num_classes)
    return modelo


def transformacoes(treino: bool = False):
    """Pipeline de pré-processamento das imagens.

    Redimensiona para ``IMG_SIZE``; em treino aplica augmentação leve (rotação e
    variação de cor); converte para 3 canais em tons de cinza, tensoriza e normaliza
    com as estatísticas do ImageNet (``config.MEAN`` / ``config.STD``).
    """
    from torchvision import transforms

    passos = [transforms.Resize((config.IMG_SIZE, config.IMG_SIZE))]
    if treino:
        passos += [
            transforms.RandomRotation(8),
            transforms.ColorJitter(brightness=0.2, contrast=0.2),
        ]
    passos += [
        transforms.Grayscale(num_output_channels=3),
        transforms.ToTensor(),
        transforms.Normalize(config.MEAN, config.STD),
    ]
    return transforms.Compose(passos)


def carregar_modelo(caminho=config.MODELO_PATH, device=None):
    """Carrega o classificador treinado a partir de ``caminho`` (state_dict).

    Constrói a arquitetura, carrega os pesos com ``map_location`` no dispositivo
    escolhido e coloca o modelo em modo de avaliação. Se o arquivo não existir,
    levanta ``FileNotFoundError`` com dica de como treinar.
    """
    import torch

    caminho = Path(caminho)
    if not caminho.exists():
        raise FileNotFoundError(
            f"Modelo não encontrado em '{caminho}'. "
            "Treine primeiro com: python -m inspetor.treino"
        )

    disp = _dispositivo(device)
    modelo = construir_modelo(preTreinado=False)   # pesos vêm do state_dict
    estado = torch.load(caminho, map_location=disp)
    modelo.load_state_dict(estado)
    modelo.to(disp)
    modelo.eval()
    return modelo


def prever(caminho_ou_img, modelo=None, device=None) -> dict:
    """Classifica o defeito de uma etiqueta.

    Aceita um caminho (str/Path), um ``numpy.ndarray`` ou uma imagem PIL. Aplica o
    pré-processamento de inferência, faz softmax e retorna as probabilidades por
    classe. Degrada graciosamente: se torch/torchvision/PIL faltarem OU o modelo não
    existir, retorna ``classe=None`` com o campo ``erro`` preenchido (não levanta).
    """
    def _erro(msg: str) -> dict:
        return {"classe": None, "classe_pt": None, "confianca": 0.0, "probs": {}, "erro": msg}

    try:
        import torch
        from PIL import Image
    except ImportError as exc:
        return _erro(f"dependência ausente (torch/torchvision/PIL): {exc}")

    try:
        disp = _dispositivo(device)

        if modelo is None:
            modelo = carregar_modelo(device=disp)

        # Normaliza a entrada para uma imagem PIL RGB.
        if isinstance(caminho_ou_img, Image.Image):
            imagem = caminho_ou_img.convert("RGB")
        elif isinstance(caminho_ou_img, (str, Path)):
            imagem = Image.open(caminho_ou_img).convert("RGB")
        else:
            import numpy as np
            imagem = Image.fromarray(np.asarray(caminho_ou_img)).convert("RGB")

        tensor = transformacoes(False)(imagem).unsqueeze(0).to(disp)
        with torch.no_grad():
            logits = modelo(tensor)
            probs = torch.softmax(logits, dim=1)[0]

        idx = int(torch.argmax(probs).item())
        classe = config.CLASSES[idx]
        probs_dict = {
            config.CLASSES[i]: round(float(probs[i].item()), 4)
            for i in range(len(config.CLASSES))
        }
        return {
            "classe": classe,
            "classe_pt": config.CLASSE_PT.get(classe, classe),
            "confianca": round(float(probs[idx].item()), 4),
            "probs": probs_dict,
            "erro": None,
        }
    except FileNotFoundError as exc:
        return _erro(str(exc))
    except Exception as exc:                          # degradação graciosa
        return _erro(f"falha na predição: {exc}")
