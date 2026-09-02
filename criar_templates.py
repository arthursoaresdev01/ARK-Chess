import os
import shutil

mapa = {
    "casa_7_4.png": "templates/brancas/rei/rei.png",
    "casa_7_3.png": "templates/brancas/rainha/rainha.png",
    "casa_7_0.png": "templates/brancas/torre/torre1.png",
    "casa_7_7.png": "templates/brancas/torre/torre2.png",
    "casa_7_2.png": "templates/brancas/bispo/bispo1.png",
    "casa_7_5.png": "templates/brancas/bispo/bispo2.png",
    "casa_7_1.png": "templates/brancas/cavalo/cavalo1.png",
    "casa_7_6.png": "templates/brancas/cavalo/cavalo2.png",

    "casa_0_4.png": "templates/pretas/rei/rei.png",
    "casa_0_3.png": "templates/pretas/rainha/rainha.png",
    "casa_0_0.png": "templates/pretas/torre/torre1.png",
    "casa_0_7.png": "templates/pretas/torre/torre2.png",
    "casa_0_2.png": "templates/pretas/bispo/bispo1.png",
    "casa_0_5.png": "templates/pretas/bispo/bispo2.png",
    "casa_0_1.png": "templates/pretas/cavalo/cavalo1.png",
    "casa_0_6.png": "templates/pretas/cavalo/cavalo2.png",
}

for coluna in range(8):
    mapa[f"casa_6_{coluna}.png"] = f"templates/brancas/peao/peao{coluna + 1}.png"
    mapa[f"casa_1_{coluna}.png"] = f"templates/pretas/peao/peao{coluna + 1}.png"

for origem, destino in mapa.items():
    shutil.copy(os.path.join("casas", origem), destino)

print("Templates criados!")