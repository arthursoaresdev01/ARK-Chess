# pyrefly: ignore [missing-import]
from ultralytics import YOLO

import os


# ============================================================
# CONFIGURAÇÕES
# ============================================================

CAMINHO_MODELO = "runs/classify/train-3/weights/best.pt"

PASTA_CASAS = "casas"


# ============================================================
# CONVERSÃO DAS CLASSES PARA FEN
# ============================================================

SIMBOLOS = {
    "vazia": ".",

    "peao_branco": "P",
    "cavalo_branco": "N",
    "bispo_branco": "B",
    "torre_branca": "R",
    "rainha_branca": "Q",
    "rei_branco": "K",

    "peao_preto": "p",
    "cavalo_preto": "n",
    "bispo_preto": "b",
    "torre_preta": "r",
    "rainha_preta": "q",
    "rei_preto": "k"
}


# ============================================================
# CARREGA O MODELO UMA ÚNICA VEZ
# ============================================================

print("Carregando modelo YOLO...")

modelo = YOLO(
    CAMINHO_MODELO
)

print("✓ Modelo carregado.")


# ============================================================
# ANALISA AS 64 CASAS
# ============================================================

def analisar_tabuleiro():

    tabuleiro = {}

    for linha in range(8):

        for coluna in range(8):

            nome_arquivo = (
                f"casa_{linha}_{coluna}.png"
            )

            caminho = os.path.join(
                PASTA_CASAS,
                nome_arquivo
            )

            if not os.path.exists(caminho):

                raise FileNotFoundError(
                    f"Casa não encontrada: {caminho}"
                )


            resultado = modelo.predict(
                source=caminho,
                imgsz=96,
                verbose=False
            )[0]


            indice = int(
                resultado.probs.top1
            )

            confianca = float(
                resultado.probs.top1conf
            )


            classe = resultado.names[
                indice
            ]


            tabuleiro[
                (linha, coluna)
            ] = (
                classe,
                confianca
            )


    return tabuleiro


# ============================================================
# MOSTRA O TABULEIRO NO TERMINAL
# ============================================================

def mostrar_tabuleiro(tabuleiro):

    print(
        "\nTABULEIRO RECONHECIDO:"
    )

    for linha in range(8):

        simbolos_linha = []

        for coluna in range(8):

            classe, _ = tabuleiro[
                (linha, coluna)
            ]

            simbolo = SIMBOLOS.get(
                classe,
                "?"
            )

            simbolos_linha.append(
                simbolo
            )


        print(
            " ".join(
                simbolos_linha
            )
        )