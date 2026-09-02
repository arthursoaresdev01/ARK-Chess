# pyrefly: ignore [missing-import]
import mss
# pyrefly: ignore [missing-import]
import cv2
# pyrefly: ignore [missing-import]
import numpy as np
# pyrefly: ignore [missing-import]
import chess
# pyrefly: ignore [missing-import]
import chess.engine

import os
import time

from analisar_tabuleiro import (
    analisar_tabuleiro,
    mostrar_tabuleiro,
    SIMBOLOS
)

# ============================================================
# CONFIGURAÇÕES
# ============================================================

MONITOR = {
    "left": 390,
    "top": 147,
    "width": 816,
    "height": 816
}

PASTA_CASAS = "casas"
LIMITE_MUDANCA = 5000

INTERVALO_CAPTURA = 0.30
TEMPO_ESTABILIZACAO = 0.35
TENTATIVAS_ESTABILIDADE = 4
LIMITE_ESTABILIDADE = 1800

CAMINHO_STOCKFISH = (
    "stockfish-windows-x86-64-avx2/"
    "stockfish/"
    "stockfish-windows-x86-64-avx2.exe"
)

NOMES_PECAS = {
    chess.PAWN: "Peão",
    chess.KNIGHT: "Cavalo",
    chess.BISHOP: "Bispo",
    chess.ROOK: "Torre",
    chess.QUEEN: "Rainha",
    chess.KING: "Rei"
}


# ============================================================
# IMAGEM / TABULEIRO
# ============================================================

def recortar_casas(imagem):
    os.makedirs(PASTA_CASAS, exist_ok=True)

    altura, largura = imagem.shape[:2]
    altura_casa = altura // 8
    largura_casa = largura // 8

    for linha in range(8):
        for coluna in range(8):
            y1 = linha * altura_casa
            y2 = (linha + 1) * altura_casa
            x1 = coluna * largura_casa
            x2 = (coluna + 1) * largura_casa

            casa = imagem[y1:y2, x1:x2]

            caminho = os.path.join(
                PASTA_CASAS,
                f"casa_{linha}_{coluna}.png"
            )

            cv2.imwrite(caminho, casa)


def calcular_mudanca(imagem1, imagem2):
    diff = cv2.absdiff(imagem1, imagem2)
    cinza = cv2.cvtColor(diff, cv2.COLOR_BGRA2GRAY)
    return cv2.countNonZero(cinza)


def capturar_estavel(sct):
    """
    Espera o tabuleiro parar de animar.
    Retorna a imagem mais recente considerada estável.
    """
    anterior = np.array(sct.grab(MONITOR))

    for _ in range(TENTATIVAS_ESTABILIDADE):
        time.sleep(TEMPO_ESTABILIZACAO)

        atual = np.array(sct.grab(MONITOR))
        mudanca = calcular_mudanca(anterior, atual)

        if mudanca <= LIMITE_ESTABILIDADE:
            return atual

        anterior = atual

    return anterior


# ============================================================
# ORIENTAÇÃO AUTOMÁTICA
# ============================================================

def detectar_cor_em_baixo(tabuleiro):
    """
    Descobre automaticamente qual cor está embaixo olhando
    onde estão concentradas as peças brancas e pretas.

    Retorna:
        "b" -> brancas embaixo
        "p" -> pretas embaixo
    """
    brancas_baixo = 0
    pretas_baixo = 0
    brancas_cima = 0
    pretas_cima = 0

    for linha in range(8):
        for coluna in range(8):
            classe, _ = tabuleiro[(linha, coluna)]

            if classe == "vazia":
                continue

            eh_branca = classe.endswith("_branco")
            eh_preta = classe.endswith("_preto")

            if linha >= 4:
                if eh_branca:
                    brancas_baixo += 1
                elif eh_preta:
                    pretas_baixo += 1
            else:
                if eh_branca:
                    brancas_cima += 1
                elif eh_preta:
                    pretas_cima += 1

    pontuacao_brancas = brancas_baixo + pretas_cima
    pontuacao_pretas = pretas_baixo + brancas_cima

    if pontuacao_pretas > pontuacao_brancas:
        return "p"

    return "b"


def gerar_fen_pecas(tabuleiro, orientacao):
    linhas_fen = []

    for linha in range(8):
        linha_fen = ""
        vazias = 0

        for coluna in range(8):
            if orientacao == "p":
                linha_real = 7 - linha
                coluna_real = 7 - coluna
            else:
                linha_real = linha
                coluna_real = coluna

            classe, _ = tabuleiro[(linha_real, coluna_real)]
            simbolo = SIMBOLOS[classe]

            if simbolo == ".":
                vazias += 1
            else:
                if vazias > 0:
                    linha_fen += str(vazias)
                    vazias = 0

                linha_fen += simbolo

        if vazias > 0:
            linha_fen += str(vazias)

        linhas_fen.append(linha_fen)

    return "/".join(linhas_fen)


# ============================================================
# ESTADO DO XADREZ
# ============================================================

def descobrir_roques(fen_pecas):
    try:
        board = chess.Board(
            f"{fen_pecas} w - - 0 1"
        )
    except ValueError:
        return "-"

    roques = ""

    rei_branco = board.piece_at(chess.E1)

    if (
        rei_branco is not None
        and rei_branco.piece_type == chess.KING
        and rei_branco.color == chess.WHITE
    ):
        torre_h1 = board.piece_at(chess.H1)
        torre_a1 = board.piece_at(chess.A1)

        if (
            torre_h1 is not None
            and torre_h1.piece_type == chess.ROOK
            and torre_h1.color == chess.WHITE
        ):
            roques += "K"

        if (
            torre_a1 is not None
            and torre_a1.piece_type == chess.ROOK
            and torre_a1.color == chess.WHITE
        ):
            roques += "Q"

    rei_preto = board.piece_at(chess.E8)

    if (
        rei_preto is not None
        and rei_preto.piece_type == chess.KING
        and rei_preto.color == chess.BLACK
    ):
        torre_h8 = board.piece_at(chess.H8)
        torre_a8 = board.piece_at(chess.A8)

        if (
            torre_h8 is not None
            and torre_h8.piece_type == chess.ROOK
            and torre_h8.color == chess.BLACK
        ):
            roques += "k"

        if (
            torre_a8 is not None
            and torre_a8.piece_type == chess.ROOK
            and torre_a8.color == chess.BLACK
        ):
            roques += "q"

    return roques if roques else "-"


def criar_board(fen_pecas, lado):
    roques = descobrir_roques(fen_pecas)

    fen = (
        f"{fen_pecas} "
        f"{'w' if lado == chess.WHITE else 'b'} "
        f"{roques} "
        f"- 0 1"
    )

    try:
        board = chess.Board(fen)
    except ValueError:
        return None

    if not board.is_valid():
        return None

    return board


def descobrir_lance(board_antigo, fen_novo):
    """
    Tenta achar 1 lance legal que transforme board_antigo em fen_novo.
    """
    for movimento in list(board_antigo.legal_moves):
        teste = board_antigo.copy(stack=True)
        teste.push(movimento)

        if teste.board_fen() == fen_novo:
            return movimento, teste

    return None, None


def recuperar_lance_perdido(board_antigo, fen_novo):
    """
    Se uma captura foi perdida, tenta avançar DOIS lances legais.
    Isso permite recuperar a sincronização sem inverter o turno errado.
    """
    for movimento1 in list(board_antigo.legal_moves):
        board1 = board_antigo.copy(stack=True)
        board1.push(movimento1)

        if board1.board_fen() == fen_novo:
            return [movimento1], board1

        for movimento2 in list(board1.legal_moves):
            board2 = board1.copy(stack=True)
            board2.push(movimento2)

            if board2.board_fen() == fen_novo:
                return [movimento1, movimento2], board2

    return None, None


def ressincronizar_por_cor(fen_novo):
    """
    Último recurso: tenta criar o board com ambos os lados.
    """
    board_w = criar_board(fen_novo, chess.WHITE)
    board_b = criar_board(fen_novo, chess.BLACK)

    if board_w is not None and board_b is None:
        return board_w

    if board_b is not None and board_w is None:
        return board_b

    return None


# ============================================================
# STOCKFISH
# ============================================================

def analisar_stockfish(engine, board):
    print("\nStockfish analisando...")

    analises = engine.analyse(
        board,
        chess.engine.Limit(depth=15),
        multipv=3
    )

    print("\n3 MELHORES JOGADAS:\n")

    for numero, analise in enumerate(
        analises,
        start=1
    ):
        pv = analise["pv"]

        if not pv:
            continue

        movimento = pv[0]
        destino = chess.square_name(
            movimento.to_square
        )

        peca = board.piece_at(
            movimento.from_square
        )

        if peca is None:
            nome_peca = "Peça"
        else:
            nome_peca = NOMES_PECAS[
                peca.piece_type
            ]

        print(
            f"{numero}. {nome_peca} {destino}"
        )


# ============================================================
# INÍCIO
# ============================================================

print("\n========================================")
print("             ARK CHESS")
print("       SISTEMA DE TREINAMENTO")
print("========================================")

print("\nIniciando Stockfish...")

engine = chess.engine.SimpleEngine.popen_uci(
    CAMINHO_STOCKFISH
)


try:
    with mss.MSS() as sct:
        print("\nAbra o tabuleiro.")
        print("Começando em 5 segundos...")

        time.sleep(5)

        print("\nCapturando posição inicial...")

        imagem_referencia = np.array(
            sct.grab(MONITOR)
        )

        recortar_casas(
            imagem_referencia
        )

        tabuleiro_inicial = (
            analisar_tabuleiro()
        )

        # Descobre automaticamente quem está embaixo.
        orientacao = detectar_cor_em_baixo(
            tabuleiro_inicial
        )

        if orientacao == "b":
            minha_cor_chess = chess.WHITE
            nome_minha_cor = "Brancas"
        else:
            minha_cor_chess = chess.BLACK
            nome_minha_cor = "Pretas"

        print(
            f"\n✓ Cor detectada automaticamente: "
            f"{nome_minha_cor}"
        )

        fen_inicial = gerar_fen_pecas(
            tabuleiro_inicial,
            orientacao
        )

        # Como o programa é iniciado para dar a sugestão do usuário,
        # começamos assumindo que é a vez da cor que está embaixo.
        board_anterior = criar_board(
            fen_inicial,
            minha_cor_chess
        )

        if board_anterior is None:
            print(
                "\n❌ Não consegui reconhecer "
                "uma posição inicial válida."
            )
            raise SystemExit

        print("\n========================================")
        print("✓ POSIÇÃO INICIAL RECONHECIDA")
        print("========================================")

        mostrar_tabuleiro(
            tabuleiro_inicial
        )

        print(
            f"\nFEN:\n{board_anterior.fen()}"
        )

        if board_anterior.turn == minha_cor_chess:
            print("\n✓ SUA VEZ")
            analisar_stockfish(
                engine,
                board_anterior
            )
        else:
            print(
                "\nAguardando jogada do adversário..."
            )

        print("\n========================================")
        print("ARK CHESS ATIVO")
        print("Aguardando jogada...")
        print("Ctrl + C para encerrar.")
        print("========================================")

        while True:
            time.sleep(
                INTERVALO_CAPTURA
            )

            try:
                imagem_atual = np.array(
                    sct.grab(MONITOR)
                )
            except mss.exception.ScreenShotError:
                time.sleep(1)
                continue

            pixels_mudaram = calcular_mudanca(
                imagem_referencia,
                imagem_atual
            )

            if pixels_mudaram <= LIMITE_MUDANCA:
                continue

            try:
                imagem_estavel = capturar_estavel(
                    sct
                )
            except mss.exception.ScreenShotError:
                continue

            recortar_casas(
                imagem_estavel
            )

            tabuleiro_novo = (
                analisar_tabuleiro()
            )

            fen_novo = gerar_fen_pecas(
                tabuleiro_novo,
                orientacao
            )

            # Mudou visualmente, mas as peças continuam iguais.
            if (
                fen_novo
                == board_anterior.board_fen()
            ):
                imagem_referencia = (
                    imagem_estavel.copy()
                )
                continue

            movimento, board_novo = descobrir_lance(
                board_anterior,
                fen_novo
            )

            if (
                movimento is not None
                and board_novo is not None
            ):
                try:
                    nome_lance = (
                        board_anterior.san(
                            movimento
                        )
                    )
                except Exception:
                    nome_lance = (
                        movimento.uci()
                    )

                print("\n========================================")
                print("✓ NOVO LANCE DETECTADO")
                print("========================================")
                print(f"\nLance: {nome_lance}")

            else:
                # NOVO: tenta recuperar se um lance inteiro passou batido.
                movimentos, board_recuperado = (
                    recuperar_lance_perdido(
                        board_anterior,
                        fen_novo
                    )
                )

                if (
                    movimentos is not None
                    and board_recuperado is not None
                ):
                    board_novo = board_recuperado

                    print("\n========================================")
                    print("✓ SINCRONIZAÇÃO RECUPERADA")
                    print("========================================")
                    print(
                        f"\nO ARK recuperou "
                        f"{len(movimentos)} lance(s) "
                        f"que passaram entre capturas."
                    )

                else:
                    # Não troca turno no chute.
                    # Se não der para provar a posição, ignora e mantém
                    # o estado anterior para tentar de novo na próxima captura.
                    board_teste = ressincronizar_por_cor(
                        fen_novo
                    )

                    if board_teste is None:
                        print(
                            "\n⚠ Mudança ignorada: "
                            "não consegui provar um estado "
                            "válido e sincronizado."
                        )

                        # IMPORTANTE:
                        # não altera board_anterior.
                        # Assim não perde o turno real.
                        imagem_referencia = (
                            imagem_estavel.copy()
                        )
                        continue

                    board_novo = board_teste

                    print(
                        "\n✓ Posição ressincronizada "
                        "automaticamente."
                    )

            cv2.imwrite(
                "tabuleiro_atual.png",
                imagem_estavel
            )

            mostrar_tabuleiro(
                tabuleiro_novo
            )

            print(
                f"\nFEN:\n{board_novo.fen()}"
            )

            jogador = (
                "Brancas"
                if board_novo.turn == chess.WHITE
                else "Pretas"
            )

            print(
                f"\nVez: {jogador}"
            )

            if board_novo.turn == minha_cor_chess:
                print("\n✓ SUA VEZ")

                analisar_stockfish(
                    engine,
                    board_novo
                )
            else:
                print(
                    "\nAguardando jogada do adversário..."
                )

            board_anterior = board_novo

            imagem_referencia = (
                imagem_estavel.copy()
            )

            print("\n----------------------------------------")
            print("Aguardando próxima jogada...")
            print("----------------------------------------")


except KeyboardInterrupt:
    print("\n\n========================================")
    print("ARK Chess encerrado.")
    print("========================================")


finally:
    engine.quit()
    print("Stockfish encerrado.")
