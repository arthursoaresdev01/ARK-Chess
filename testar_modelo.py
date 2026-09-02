# pyrefly: ignore [missing-import]
from ultralytics import YOLO
import os
# pyrefly: ignore [missing-import]
import chess
# pyrefly: ignore [missing-import]
import chess.engine


# =========================================================
# CONFIGURAÇÕES
# =========================================================

CAMINHO_MODELO = "runs/classify/train-2/weights/best.pt"

CAMINHO_STOCKFISH = (
    "stockfish-windows-x86-64-avx2/"
    "stockfish/"
    "stockfish-windows-x86-64-avx2.exe"
)

PASTA_CASAS = "casas"


# =========================================================
# CARREGA O MODELO
# =========================================================

model = YOLO(CAMINHO_MODELO)


# =========================================================
# ANALISA AS 64 CASAS
# =========================================================

resultados_yolo = model(PASTA_CASAS, verbose=False)

tabuleiro = {}

for resultado_yolo in resultados_yolo:

    nome_arquivo = os.path.basename(resultado_yolo.path)

    partes = (
        nome_arquivo
        .replace(".png", "")
        .split("_")
    )

    linha = int(partes[1])
    coluna = int(partes[2])

    classe_id = resultado_yolo.probs.top1

    confianca = resultado_yolo.probs.top1conf.item()

    classe = resultado_yolo.names[classe_id]

    tabuleiro[(linha, coluna)] = (
        classe,
        confianca
    )


# =========================================================
# MOSTRA DETECÇÃO DAS CASAS
# =========================================================

print("\nCASAS DETECTADAS:")

for linha in range(8):

    for coluna in range(8):

        classe, confianca = tabuleiro[(linha, coluna)]

        print(
            f"{linha},{coluna} -> "
            f"{classe} ({confianca:.2%})"
        )


# =========================================================
# SÍMBOLOS DAS PEÇAS
# =========================================================

simbolos = {

    "rei_branco": "K",
    "rainha_branca": "Q",
    "torre_branca": "R",
    "bispo_branco": "B",
    "cavalo_branco": "N",
    "peao_branco": "P",

    "rei_preto": "k",
    "rainha_preta": "q",
    "torre_preta": "r",
    "bispo_preto": "b",
    "cavalo_preto": "n",
    "peao_preto": "p",

    "vazia": "."
}


# =========================================================
# MOSTRA TABULEIRO
# =========================================================

print("\nTABULEIRO:")

for linha in range(8):

    for coluna in range(8):

        classe, _ = tabuleiro[(linha, coluna)]

        print(
            simbolos[classe],
            end=" "
        )

    print()


# =========================================================
# GERA FEN
# =========================================================

def gerar_fen(tabuleiro, simbolos):

    linhas_fen = []

    for linha in range(8):

        casas_vazias = 0

        texto_linha = ""

        for coluna in range(8):

            classe, _ = tabuleiro[(linha, coluna)]

            peca = simbolos[classe]

            if peca == ".":

                casas_vazias += 1

            else:

                if casas_vazias > 0:

                    texto_linha += str(casas_vazias)

                    casas_vazias = 0

                texto_linha += peca

        if casas_vazias > 0:

            texto_linha += str(casas_vazias)

        linhas_fen.append(texto_linha)

    return "/".join(linhas_fen)


fen_pecas = gerar_fen(
    tabuleiro,
    simbolos
)


# =========================================================
# LADO A JOGAR
# =========================================================

# "w" = brancas
# "b" = pretas

escolha = input("\nQuem joga? [b] Brancas / [p] Pretas: ").strip().lower()

if escolha == "p":
    lado_a_jogar = "b"
else:
    lado_a_jogar = "w"


# =========================================================
# DIREITOS DE ROQUE
# =========================================================

direitos_roque = ""

# Brancas: rei em e1 + torre em h1
if board_pecas := tabuleiro:
    rei_e1 = tabuleiro[(7, 4)][0] == "rei_branco"
    torre_h1 = tabuleiro[(7, 7)][0] == "torre_branca"
    torre_a1 = tabuleiro[(7, 0)][0] == "torre_branca"

    if rei_e1 and torre_h1:
        resposta = input(
            "Brancas ainda podem rocar pequeno? [s/n]: "
        ).strip().lower()

        if resposta == "s":
            direitos_roque += "K"

    if rei_e1 and torre_a1:
        resposta = input(
            "Brancas ainda podem rocar grande? [s/n]: "
        ).strip().lower()

        if resposta == "s":
            direitos_roque += "Q"


# Pretas: rei em e8 + torres em h8/a8
rei_e8 = tabuleiro[(0, 4)][0] == "rei_preto"
torre_h8 = tabuleiro[(0, 7)][0] == "torre_preta"
torre_a8 = tabuleiro[(0, 0)][0] == "torre_preta"

if rei_e8 and torre_h8:
    resposta = input(
        "Pretas ainda podem rocar pequeno? [s/n]: "
    ).strip().lower()

    if resposta == "s":
        direitos_roque += "k"

if rei_e8 and torre_a8:
    resposta = input(
        "Pretas ainda podem rocar grande? [s/n]: "
    ).strip().lower()

    if resposta == "s":
        direitos_roque += "q"


if direitos_roque == "":
    direitos_roque = "-"


# =========================================================
# FEN COMPLETA
# =========================================================

fen_completa = (
    fen_pecas
    + f" {lado_a_jogar} {direitos_roque} - 0 1"
)

print("\nFEN COMPLETA:")
print(fen_completa)


# =========================================================
# CRIA TABULEIRO CHESS
# =========================================================

board = chess.Board(
    fen_completa
)


print("\nPOSIÇÃO VÁLIDA:")
print(board.is_valid())


# =========================================================
# PARA SE A POSIÇÃO FOR INVÁLIDA
# =========================================================

if not board.is_valid():

    print(
        "\nERRO: posição detectada é inválida."
    )

    exit()


# =========================================================
# NOMES HUMANOS DAS PEÇAS
# =========================================================

nomes_pecas = {

    chess.PAWN: "Peão",

    chess.KNIGHT: "Cavalo",

    chess.BISHOP: "Bispo",

    chess.ROOK: "Torre",

    chess.QUEEN: "Rainha",

    chess.KING: "Rei"
}


# =========================================================
# INICIA STOCKFISH
# =========================================================

engine = chess.engine.SimpleEngine.popen_uci(
    CAMINHO_STOCKFISH
)


# =========================================================
# ANALISA AS 3 MELHORES JOGADAS
# =========================================================

analises = engine.analyse(

    board,

    chess.engine.Limit(
        depth=15
    ),

    multipv=3
)


print("\n3 MELHORES JOGADAS:")


# =========================================================
# MOSTRA RESULTADOS
# =========================================================

for numero, analise in enumerate(
    analises,
    start=1
):

    movimento = analise["pv"][0]

    peca = board.piece_at(
        movimento.from_square
    )

    origem = chess.square_name(
        movimento.from_square
    )

    destino = chess.square_name(
        movimento.to_square
    )

    nome_peca = nomes_pecas[
        peca.piece_type
    ]


    # =====================================================
    # AVALIAÇÃO
    # =====================================================

    score = analise["score"].white()


    # Se Stockfish encontrou mate
    if score.is_mate():

        mate = score.mate()

        avaliacao_texto = (
            f"Mate em {abs(mate)}"
        )

    else:

        centipawns = score.score()

        avaliacao = (
            centipawns / 100
        )

        avaliacao_texto = (
            f"{avaliacao:+.2f}"
        )


    print(
        f"{numero}. "
        f"{nome_peca} "
        f"{origem} → {destino} "
        f"| Avaliação: "
        f"{avaliacao_texto}"
    )


# =========================================================
# FINALIZA STOCKFISH
# =========================================================

engine.quit()