"""Script de treino do classificador de defeitos (transferência de aprendizado).

Uso:
    python -m inspetor.treino [--epocas N] [--lr LR] [--batch B] [--saida CAMINHO]
                              [--sem-congelar]

Imports pesados são LAZY (dentro das funções) — o módulo importa/compila sem torch.
"""
from __future__ import annotations

from pathlib import Path

from inspetor import config


def _avaliar(modelo, loader, dispositivo, num_classes: int):
    """Calcula a acurácia global e por classe sobre um ``DataLoader``."""
    import torch

    modelo.eval()
    corretos = 0
    total = 0
    corretos_classe = [0] * num_classes
    total_classe = [0] * num_classes

    with torch.no_grad():
        for imagens, alvos in loader:
            imagens = imagens.to(dispositivo)
            alvos = alvos.to(dispositivo)
            saidas = modelo(imagens)
            preds = saidas.argmax(dim=1)
            corretos += int((preds == alvos).sum().item())
            total += int(alvos.size(0))
            for alvo, pred in zip(alvos.view(-1).tolist(), preds.view(-1).tolist()):
                total_classe[alvo] += 1
                if alvo == pred:
                    corretos_classe[alvo] += 1

    acuracia = corretos / total if total else 0.0
    por_classe = {}
    for i in range(num_classes):
        nome = config.CLASSES[i]
        por_classe[nome] = round(corretos_classe[i] / total_classe[i], 4) if total_classe[i] else 0.0
    return acuracia, por_classe


def treinar(epocas: int = 10, lr: float = 1e-3, batch_size: int = 32,
            dataset_dir=config.DATASET_DIR, saida=config.MODELO_PATH,
            congelar_backbone: bool = True) -> dict:
    """Treina a CNN com transferência de aprendizado e salva o melhor modelo.

    - Perda: ``CrossEntropyLoss``; otimizador: ``Adam(lr)``.
    - Se ``congelar_backbone``, treina apenas o ``classifier`` (backbone congelado).
    - Salva em ``saida`` (criando ``MODELOS_DIR``) o state_dict de maior ``val_acc``.

    Retorna ``{"val_acc", "test_acc", "por_classe"}``.
    """
    import torch
    import torch.nn as nn

    from inspetor import rede
    from inspetor.dataset import carregar_loaders

    dispositivo = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    num_classes = len(config.CLASSES)

    modelo = rede.construir_modelo(num_classes=num_classes, preTreinado=True)
    modelo.to(dispositivo)

    if congelar_backbone:
        for parametro in modelo.parameters():
            parametro.requires_grad = False
        for parametro in modelo.classifier.parameters():
            parametro.requires_grad = True
        parametros = [p for p in modelo.parameters() if p.requires_grad]
    else:
        parametros = list(modelo.parameters())

    criterio = nn.CrossEntropyLoss()
    otimizador = torch.optim.Adam(parametros, lr=lr)

    loaders = carregar_loaders(dataset_dir=dataset_dir, batch_size=batch_size)

    saida = Path(saida)
    saida.parent.mkdir(parents=True, exist_ok=True)

    melhor_val = -1.0
    for _ in range(epocas):
        modelo.train()
        for imagens, alvos in loaders["train"]:
            imagens = imagens.to(dispositivo)
            alvos = alvos.to(dispositivo)
            otimizador.zero_grad()
            saidas = modelo(imagens)
            perda = criterio(saidas, alvos)
            perda.backward()
            otimizador.step()

        val_acc, _ = _avaliar(modelo, loaders["val"], dispositivo, num_classes)
        if val_acc > melhor_val:
            melhor_val = val_acc
            torch.save(modelo.state_dict(), saida)

    # Recarrega o melhor checkpoint antes de medir no teste.
    if saida.exists():
        modelo.load_state_dict(torch.load(saida, map_location=dispositivo))
    test_acc, por_classe = _avaliar(modelo, loaders["test"], dispositivo, num_classes)

    return {
        "val_acc": round(melhor_val if melhor_val >= 0 else 0.0, 4),
        "test_acc": round(test_acc, 4),
        "por_classe": por_classe,
    }


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Treina o classificador de defeitos (CNN MobileNetV3-Small)."
    )
    parser.add_argument("--epocas", type=int, default=10, help="número de épocas")
    parser.add_argument("--lr", type=float, default=1e-3, help="taxa de aprendizado")
    parser.add_argument("--batch", type=int, default=32, help="tamanho do batch")
    parser.add_argument("--saida", type=str, default=str(config.MODELO_PATH),
                        help="caminho de saída do modelo (.pt)")
    parser.add_argument("--sem-congelar", action="store_true",
                        help="treina também o backbone (fine-tuning completo)")
    args = parser.parse_args()

    metricas = treinar(
        epocas=args.epocas,
        lr=args.lr,
        batch_size=args.batch,
        saida=args.saida,
        congelar_backbone=not args.sem_congelar,
    )

    print("Métricas finais:")
    print(f"  val_acc : {metricas['val_acc']}")
    print(f"  test_acc: {metricas['test_acc']}")
    print("  por classe:")
    for nome, acc in metricas["por_classe"].items():
        print(f"    {nome}: {acc}")
    print(f"Modelo salvo em: {args.saida}")
