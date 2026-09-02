# pyrefly: ignore [missing-import]
import cv2
import os


# =========================================================
# CONFIGURAÇÕES
# =========================================================

ARQUIVO_TABULEIRO = "tabuleiro_atual.png"
PASTA_SAIDA = "casas"


# =========================================================
# CARREGA A IMAGEM
# =========================================================

imagem = cv2.imread(ARQUIVO_TABULEIRO)

if imagem is None:
    print(f"Erro: não foi possível abrir {ARQUIVO_TABULEIRO}")
    exit()


# Gira 180° para ficar na orientação usada no treinamento
imagem = cv2.rotate(
    imagem,
    cv2.ROTATE_180
)

# =========================================================
# PREPARA PASTA DE SAÍDA
# =========================================================

os.makedirs(
    PASTA_SAIDA,
    exist_ok=True
)


# =========================================================
# CALCULA TAMANHO DAS CASAS
# =========================================================

altura, largura = imagem.shape[:2]

altura_casa = altura // 8
largura_casa = largura // 8


print(
    f"Imagem: {largura}x{altura}"
)

print(
    f"Cada casa: {largura_casa}x{altura_casa}"
)


# =========================================================
# RECORTA AS 64 CASAS
# =========================================================

for linha in range(8):

    for coluna in range(8):

        x1 = coluna * largura_casa
        y1 = linha * altura_casa

        x2 = (
            largura
            if coluna == 7
            else (coluna + 1) * largura_casa
        )

        y2 = (
            altura
            if linha == 7
            else (linha + 1) * altura_casa
        )

        casa = imagem[
            y1:y2,
            x1:x2
        ]

        caminho = os.path.join(
            PASTA_SAIDA,
            f"casa_{linha}_{coluna}.png"
        )

        cv2.imwrite(
            caminho,
            casa
        )


print("\n64 casas recortadas com sucesso!")
print(f"Salvas na pasta: {PASTA_SAIDA}")