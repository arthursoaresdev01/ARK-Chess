import os
import shutil

origem_base = "templates"
destino_base = "dataset_pecas"

mapa = {
    "brancas/peao": "peao_branco",
    "brancas/cavalo": "cavalo_branco",
    "brancas/bispo": "bispo_branco",
    "brancas/torre": "torre_branca",
    "brancas/rainha": "rainha_branca",
    "brancas/rei": "rei_branco",

    "pretas/peao": "peao_preto",
    "pretas/cavalo": "cavalo_preto",
    "pretas/bispo": "bispo_preto",
    "pretas/torre": "torre_preta",
    "pretas/rainha": "rainha_preta",
    "pretas/rei": "rei_preto",
}

for origem, destino in mapa.items():
    pasta_origem = os.path.join(origem_base, origem)
    pasta_destino = os.path.join(destino_base, destino)

    for arquivo in os.listdir(pasta_origem):
        shutil.copy(
            os.path.join(pasta_origem, arquivo),
            os.path.join(pasta_destino, arquivo)
        )

print("Dataset inicial montado!")