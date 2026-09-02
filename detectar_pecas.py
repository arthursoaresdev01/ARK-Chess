# pyrefly: ignore [missing-import]
import cv2
import os
import shutil

pasta = "casas"

os.makedirs("dataset/com_peca", exist_ok=True)
os.makedirs("dataset/vazia", exist_ok=True)

for arquivo in sorted(os.listdir(pasta)):
    caminho = os.path.join(pasta, arquivo)

    imagem = cv2.imread(caminho)
    cinza = cv2.cvtColor(imagem, cv2.COLOR_BGR2GRAY)
    bordas = cv2.Canny(cinza, 50, 150)

    quantidade_bordas = cv2.countNonZero(bordas)

    if quantidade_bordas > 400:
        destino = "dataset/com_peca"
    else:
        destino = "dataset/vazia"

    shutil.copy(caminho, os.path.join(destino, arquivo))

print("Dataset separado!")