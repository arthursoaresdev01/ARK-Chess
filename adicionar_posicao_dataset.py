import os
import shutil


PASTA_CASAS = "casas"
PASTA_DATASET = "dataset_pecas"


# Posição correta da imagem atual.
# Já considerando a rotação feita pelo ler_tabuleiro.py.
POSICAO = [
    ["torre_preta", "vazia", "bispo_preto", "rainha_preta", "rei_preto", "vazia", "cavalo_preto", "torre_preta"],
    ["peao_preto", "vazia", "vazia", "vazia", "vazia", "peao_preto", "peao_preto", "peao_preto"],
    ["vazia", "vazia", "rainha_branca", "vazia", "peao_preto", "vazia", "vazia", "vazia"],
    ["bispo_preto", "vazia", "peao_branco", "peao_preto", "peao_branco", "vazia", "vazia", "vazia"],
    ["vazia", "vazia", "vazia", "peao_branco", "vazia", "vazia", "vazia", "vazia"],
    ["vazia", "vazia", "peao_branco", "vazia", "vazia", "cavalo_branco", "vazia", "vazia"],
    ["peao_branco", "vazia", "vazia", "vazia", "vazia", "peao_branco", "peao_branco", "peao_branco"],
    ["torre_branca", "cavalo_branco", "bispo_branco", "vazia", "rei_branco", "vazia", "vazia", "torre_branca"],
]


for linha in range(8):
    for coluna in range(8):

        classe = POSICAO[linha][coluna]

        origem = os.path.join(
            PASTA_CASAS,
            f"casa_{linha}_{coluna}.png"
        )

        pasta_classe = os.path.join(
            PASTA_DATASET,
            classe
        )

        os.makedirs(
            pasta_classe,
            exist_ok=True
        )

        destino = os.path.join(
            pasta_classe,
            f"real_pos2_{linha}_{coluna}.png"
        )

        shutil.copy2(
            origem,
            destino
        )


print("64 casas adicionadas ao dataset com sucesso!")