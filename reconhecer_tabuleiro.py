# pyrefly: ignore [missing-import]
import cv2
import os


def comparar(imagem1, imagem2):
    img1 = cv2.imread(imagem1, cv2.IMREAD_GRAYSCALE)
    img2 = cv2.imread(imagem2, cv2.IMREAD_GRAYSCALE)

    img2 = cv2.resize(img2, (img1.shape[1], img1.shape[0]))

    h, w = img1.shape

    img1 = img1[10:h-10, 10:w-10]
    img2 = img2[10:h-10, 10:w-10]

    bordas1 = cv2.Canny(img1, 50, 150)
    bordas2 = cv2.Canny(img2, 50, 150)

    resultado = cv2.matchTemplate(
        bordas1,
        bordas2,
        cv2.TM_CCOEFF_NORMED
    )

    return resultado.max()


for linha in range(8):
    for coluna in range(8):

        casa = f"casas/casa_{linha}_{coluna}.png"

        img_teste = cv2.imread(
            casa,
            cv2.IMREAD_GRAYSCALE
        )

        h, w = img_teste.shape

        centro = img_teste[
            h // 4: 3 * h // 4,
            w // 4: 3 * w // 4
        ]

        pixels_claros = (centro > 230).sum()
        pixels_escuros = (centro < 70).sum()

        # Casa vazia
        if pixels_claros == 0 and pixels_escuros == 0:
            print(f"{linha},{coluna} -> VAZIA")
            continue

        # Cor
        if pixels_claros > pixels_escuros:
            cor_detectada = "brancas"
        else:
            cor_detectada = "pretas"

        melhor_nome = None
        melhor_score = -1

        # Procura somente templates da cor detectada
        pasta_cor = f"templates/{cor_detectada}"

        for peca in os.listdir(pasta_cor):

            pasta_peca = os.path.join(
                pasta_cor,
                peca
            )

            for arquivo in os.listdir(pasta_peca):

                template = os.path.join(
                    pasta_peca,
                    arquivo
                )

                score = comparar(
                    casa,
                    template
                )

                if score > melhor_score:
                    melhor_score = score
                    melhor_nome = peca

        print(
            f"{linha},{coluna} -> "
            f"{melhor_nome} {cor_detectada} "
            f"({melhor_score:.2f})"
        )