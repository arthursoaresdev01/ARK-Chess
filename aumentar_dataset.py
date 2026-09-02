# pyrefly: ignore [missing-import]
import cv2
import os

pasta_base = "dataset_pecas"

for classe in os.listdir(pasta_base):
    pasta_classe = os.path.join(pasta_base, classe)

    if not os.path.isdir(pasta_classe):
        continue

    arquivos = os.listdir(pasta_classe)

    for arquivo in arquivos:
        caminho = os.path.join(pasta_classe, arquivo)

        imagem = cv2.imread(caminho)

        if imagem is None:
            continue

        nome, ext = os.path.splitext(arquivo)

        # Mais clara
        clara = cv2.convertScaleAbs(imagem, alpha=1.1, beta=15)
        cv2.imwrite(
            os.path.join(pasta_classe, f"{nome}_clara{ext}"),
            clara
        )

        # Mais escura
        escura = cv2.convertScaleAbs(imagem, alpha=0.9, beta=-15)
        cv2.imwrite(
            os.path.join(pasta_classe, f"{nome}_escura{ext}"),
            escura
        )

        # Levemente desfocada
        blur = cv2.GaussianBlur(imagem, (3, 3), 0)
        cv2.imwrite(
            os.path.join(pasta_classe, f"{nome}_blur{ext}"),
            blur
        )

print("Dataset aumentado!")