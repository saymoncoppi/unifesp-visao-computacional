"""Dataset PyTorch para as imagens de etiquetas rotuladas.

Lê ``config.LABELS_CSV`` (colunas: filename,split,classe,simbologia,payload,params),
filtra por split e entrega pares ``(imagem_transformada, indice_classe)``. O índice
da classe segue a ORDEM de ``config.CLASSES``.

Observação: para respeitar a regra de imports LAZY (torch nunca no topo), a classe
``DatasetDefeitos`` NÃO herda de ``torch.utils.data.Dataset`` — ela é um dataset
map-style compatível por duck typing (implementa ``__len__`` e ``__getitem__``), o
que basta para o ``DataLoader``.
"""
from __future__ import annotations

import csv
from pathlib import Path

from inspetor import config


class DatasetDefeitos:
    """Dataset de defeitos de impressão, filtrado por split.

    Parâmetros
    ----------
    split : str
        "train", "val" ou "test".
    dataset_dir : Path
        Raiz do dataset; ``filename`` no CSV é relativo a ela.
    transform : callable | None
        Transformação aplicada à imagem PIL. Se ``None``, usa
        ``rede.transformacoes(treino=split == "train")``.
    """

    def __init__(self, split: str = "train", dataset_dir=config.DATASET_DIR, transform=None):
        self.split = split
        self.dataset_dir = Path(dataset_dir)
        self.transform = transform
        self.classe_para_indice = {classe: i for i, classe in enumerate(config.CLASSES)}

        csv_path = self.dataset_dir / "labels.csv"
        if not csv_path.exists():
            csv_path = Path(config.LABELS_CSV)

        self.linhas: list[dict] = []
        with open(csv_path, newline="", encoding="utf-8") as arquivo:
            leitor = csv.DictReader(arquivo)
            for linha in leitor:
                if linha.get("split") == split:
                    self.linhas.append(linha)

    def _garantir_transform(self):
        """Resolve a transformação padrão (lazy) quando nenhuma foi fornecida."""
        if self.transform is None:
            from inspetor import rede
            self.transform = rede.transformacoes(treino=self.split == "train")
        return self.transform

    def __len__(self) -> int:
        return len(self.linhas)

    def __getitem__(self, indice: int):
        from PIL import Image

        linha = self.linhas[indice]
        caminho = self.dataset_dir / linha["filename"]
        imagem = Image.open(caminho).convert("RGB")
        imagem = self._garantir_transform()(imagem)
        alvo = self.classe_para_indice[linha["classe"]]
        return imagem, alvo


def carregar_loaders(dataset_dir=config.DATASET_DIR, batch_size: int = 32, num_workers: int = 2) -> dict:
    """Cria os ``DataLoader`` de treino, validação e teste.

    Aplica augmentação apenas no split de treino (que também é embaralhado).
    Retorna ``{"train": DataLoader, "val": DataLoader, "test": DataLoader}``.
    """
    from torch.utils.data import DataLoader
    from inspetor import rede

    loaders = {}
    for split in ("train", "val", "test"):
        eh_treino = split == "train"
        conjunto = DatasetDefeitos(
            split=split,
            dataset_dir=dataset_dir,
            transform=rede.transformacoes(treino=eh_treino),
        )
        loaders[split] = DataLoader(
            conjunto,
            batch_size=batch_size,
            shuffle=eh_treino,
            num_workers=num_workers,
        )
    return loaders
