import os
import shutil
import random

origem = "dataset_pecas"
destino = "dataset_final"

random.seed(42)

for classe in os.listdir(origem):
    pasta_classe = os.path.join(origem, classe)

    if not os.path.isdir(pasta_classe):
        continue

    arquivos = [
        a for a in os.listdir(pasta_classe)
        if a.lower().endswith((".png", ".jpg", ".jpeg"))
    ]

    random.shuffle(arquivos)

    corte = int(len(arquivos) * 0.8)

    treino = arquivos[:corte]
    validacao = arquivos[corte:]

    for grupo, lista in [
        ("train", treino),
        ("val", validacao)
    ]:
        pasta_destino = os.path.join(
            destino,
            grupo,
            classe
        )

        os.makedirs(pasta_destino, exist_ok=True)

        for arquivo in lista:
            shutil.copy(
                os.path.join(pasta_classe, arquivo),
                os.path.join(pasta_destino, arquivo)
            )

print("Dataset dividido!")