# ARK Chess V10
# Sistema de treinamento/análise contra bots.
#
# Dependências:
#   pip install mss opencv-python numpy python-chess ultralytics
#
# Requer:
#   - analisar_tabuleiro.py
#   - modelo YOLO configurado em analisar_tabuleiro.py
#   - Stockfish no caminho CAMINHO_STOCKFISH

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

import itertools
import logging
from logging.handlers import RotatingFileHandler
import os
import sys
import argparse
import time
import ctypes
from ctypes import wintypes
from dataclasses import dataclass
from pathlib import Path

from analisar_tabuleiro import (
    analisar_tabuleiro,
    mostrar_tabuleiro,
    SIMBOLOS,
)


# ============================================================
# CONFIGURAÇÕES
# ============================================================

VERSAO = "V29-GUARD"

# Região EXATA da V12 que já funcionou com o classificador.
MONITOR_FIXO_V12 = {
    "left": 390,
    "top": 147,
    "width": 816,
    "height": 816,
}

MONITOR = MONITOR_FIXO_V12.copy()

# V21: acompanha somente o DESLOCAMENTO da janela.
# Não redimensiona o board, não tenta achar 780x780 e não mexe
# na geometria que já funcionava na V12.
AUTO_ACOMPANHAR_JANELA = True
TITULOS_JANELA_CHESS = ("chess.com", "chess")
INTERVALO_ATUALIZAR_JANELA = 0.12

# V24: o board real pode ter outro tamanho na tela.
# A visão interna do ARK recebe SEMPRE 816x816.
TAMANHO_FRAME_ARK = 816

PASTA_CASAS = Path("casas")
ARQUIVO_TABULEIRO_ATUAL = Path("tabuleiro_atual.png")
ARQUIVO_LOG = Path("ark_chess.log")

# V25: diagnóstico automático quando a posição inicial não valida.
PASTA_DIAGNOSTICOS = Path("diagnosticos_v25")
DIAGNOSTICO_APOS_FALHAS = 4
INTERVALO_DIAGNOSTICO = 5.0
MAX_DIAGNOSTICOS_INICIO = 3

CAMINHO_STOCKFISH = Path(
    "stockfish-windows-x86-64-avx2"
) / "stockfish" / "stockfish-windows-x86-64-avx2.exe"

# Loop
INTERVALO_LOOP = 0.015
INTERVALO_RELEITURA_FORCADA = 0.80

# Captura estável
INTERVALO_FRAME_ESTAVEL = 0.015
MAX_TENTATIVAS_ESTABILIDADE = 2
LIMITE_PIXELS_ESTABILIDADE = 1800

# Detector rápido de mudança visual
LIMITE_PIXELS_MUDANCA = 3500

# Reconhecimento por consenso
MAX_TENTATIVAS_RECONHECIMENTO = 2
LEITURAS_IGUAIS_NECESSARIAS = 2
INTERVALO_ENTRE_LEITURAS = 0.015

# Modo agressivo: usado quando os pixels dizem que houve mudança,
# mas o classificador insiste em devolver a posição anterior.
MAX_TENTATIVAS_RECONHECIMENTO_AGRESSIVO = 3
INTERVALO_AGRESSIVO = 0.015

# Filtros do classificador
CONFIANCA_MEDIA_MINIMA = 0.52

# Recuperação de sincronização
MAX_PLIES_RECUPERACAO = 3
MAX_ESTADOS_BFS = 25000
# V22: não abandona o board confirmado por ruído temporário.
FALHAS_ATE_RESSINCRONIZAR = 4
TEMPO_MINIMO_RESSINCRONIZAR = 0.75

# Stockfish
STOCKFISH_TEMPO_ANALISE = 0.07
STOCKFISH_HASH_MB = 256
STOCKFISH_THREADS_MAX = 4

# Reduz spam no terminal
INTERVALO_STATUS = 0.70


NOMES_PECAS = {
    chess.PAWN: "Peão",
    chess.KNIGHT: "Cavalo",
    chess.BISHOP: "Bispo",
    chess.ROOK: "Torre",
    chess.QUEEN: "Rainha",
    chess.KING: "Rei",
}

NOMES_PROMOCAO = {
    chess.QUEEN: "Rainha",
    chess.ROOK: "Torre",
    chess.BISHOP: "Bispo",
    chess.KNIGHT: "Cavalo",
}


# ============================================================
# V21 — ACOMPANHAMENTO SEGURO DA JANELA
# ============================================================

_user32 = ctypes.windll.user32 if os.name == "nt" else None

if _user32 is not None:
    try:
        _user32.SetProcessDPIAware()
    except Exception:
        pass


@dataclass
class EstadoJanela:
    hwnd: int | None = None
    client_left: int = 0
    client_top: int = 0
    client_width: int = 0
    client_height: int = 0
    board_rel_x: int | None = None
    board_rel_y: int | None = None
    board_real_size: int = 816
    ultimo_update: float = 0.0


ESTADO_JANELA = EstadoJanela()


def _titulo_janela(hwnd):
    if _user32 is None:
        return ""

    tamanho = _user32.GetWindowTextLengthW(hwnd)
    if tamanho <= 0:
        return ""

    buffer = ctypes.create_unicode_buffer(tamanho + 1)
    _user32.GetWindowTextW(hwnd, buffer, tamanho + 1)
    return buffer.value.strip()


def _client_rect_screen(hwnd):
    if _user32 is None:
        return None

    rect = wintypes.RECT()
    if not _user32.GetClientRect(hwnd, ctypes.byref(rect)):
        return None

    p = wintypes.POINT(0, 0)
    if not _user32.ClientToScreen(hwnd, ctypes.byref(p)):
        return None

    width = int(rect.right - rect.left)
    height = int(rect.bottom - rect.top)

    if width <= 0 or height <= 0:
        return None

    return int(p.x), int(p.y), width, height


def encontrar_janela_chess():
    if _user32 is None:
        return None

    candidatos = []

    EnumWindowsProc = ctypes.WINFUNCTYPE(
        ctypes.c_bool,
        wintypes.HWND,
        wintypes.LPARAM,
    )

    def callback(hwnd, _):
        try:
            if not _user32.IsWindowVisible(hwnd):
                return True

            titulo = _titulo_janela(hwnd)
            if not titulo:
                return True

            titulo_lower = titulo.lower()

            if not any(
                chave in titulo_lower
                for chave in TITULOS_JANELA_CHESS
            ):
                return True

            rect = _client_rect_screen(hwnd)
            if rect is None:
                return True

            left, top, width, height = rect

            if width < 700 or height < 650:
                return True

            candidatos.append(
                (width * height, int(hwnd), titulo, rect)
            )

        except Exception:
            pass

        return True

    callback_c = EnumWindowsProc(callback)
    _user32.EnumWindows(callback_c, 0)

    if not candidatos:
        return None

    candidatos.sort(reverse=True, key=lambda item: item[0])
    _, hwnd, titulo, rect = candidatos[0]

    return hwnd, titulo, rect


def _score_checkerboard(
    imagem,
    x,
    y,
    size,
):
    """
    Confere se uma região quadrada se comporta como um tabuleiro 8x8.
    Usa pontos perto dos cantos das casas para escapar das peças.
    """
    if size < 320:
        return 0.0

    h, w = imagem.shape[:2]

    if (
        x < 0
        or y < 0
        or x + size > w
        or y + size > h
    ):
        return 0.0

    casa = size / 8.0
    amostras = []

    offsets = (
        (0.18, 0.18),
        (0.82, 0.18),
        (0.18, 0.82),
        (0.82, 0.82),
    )

    for linha in range(8):
        linha_amostras = []

        for coluna in range(8):
            cores = []

            for ox, oy in offsets:
                px = int(
                    x
                    + coluna * casa
                    + ox * casa
                )
                py = int(
                    y
                    + linha * casa
                    + oy * casa
                )

                px = max(
                    0,
                    min(w - 1, px),
                )
                py = max(
                    0,
                    min(h - 1, py),
                )

                cores.append(
                    imagem[py, px, :3].astype(
                        np.float32
                    )
                )

            linha_amostras.append(
                np.median(
                    np.stack(cores),
                    axis=0,
                )
            )

        amostras.append(linha_amostras)

    arr = np.array(
        amostras,
        dtype=np.float32,
    )

    pares = arr[
        np.indices((8, 8)).sum(axis=0) % 2 == 0
    ]
    impares = arr[
        np.indices((8, 8)).sum(axis=0) % 2 == 1
    ]

    media_a = np.median(
        pares,
        axis=0,
    )
    media_b = np.median(
        impares,
        axis=0,
    )

    distancia_cores = float(
        np.linalg.norm(
            media_a - media_b
        )
    )

    # Duas cores precisam ser claramente diferentes.
    if distancia_cores < 22:
        return 0.0

    erro = 0.0
    acertos = 0

    for linha in range(8):
        for coluna in range(8):
            pixel = arr[
                linha,
                coluna,
            ]

            da = np.linalg.norm(
                pixel - media_a
            )
            db = np.linalg.norm(
                pixel - media_b
            )

            esperado_a = (
                (linha + coluna) % 2 == 0
            )

            if (
                (esperado_a and da <= db)
                or (
                    not esperado_a
                    and db <= da
                )
            ):
                acertos += 1

            erro += min(da, db)

    taxa = acertos / 64.0
    erro_medio = erro / 64.0

    # Favorece alternância limpa e cores consistentes.
    score = (
        taxa * 100.0
        + min(
            distancia_cores,
            120.0,
        ) * 0.25
        - erro_medio * 0.20
    )

    return score


def detectar_tabuleiro_na_janela(
    imagem,
):
    """
    Detector geométrico leve.

    A interface do Chess.com deixa o tabuleiro como um grande quadrado.
    Procuramos quadrados plausíveis na metade esquerda/central e
    pontuamos pelo padrão alternado 8x8.

    Não usa YOLO, então só roda ocasionalmente.
    """
    if imagem is None:
        return None

    h, w = imagem.shape[:2]

    if h < 500 or w < 600:
        return None

    # Trabalha em escala reduzida para ficar barato.
    escala = min(
        1.0,
        1000.0 / max(w, h),
    )

    if escala < 1.0:
        pequena = cv2.resize(
            imagem,
            (
                int(w * escala),
                int(h * escala),
            ),
            interpolation=cv2.INTER_AREA,
        )
    else:
        pequena = imagem

    hs, ws = pequena.shape[:2]

    # A busca usa tamanhos responsivos, mas limita a área horizontal.
    size_min = int(
        min(hs, ws) * 0.42
    )
    size_max = int(
        min(hs, ws) * 0.92
    )

    if size_min < 250:
        size_min = 250

    melhores = []

    # Passos relativamente grandes; a segunda etapa refina.
    for size in range(
        size_min,
        size_max + 1,
        max(24, int(size_min * 0.08)),
    ):
        passo = max(
            24,
            int(size * 0.12),
        )

        y_max = max(
            1,
            hs - size + 1,
        )

        # Chess.com normalmente deixa o board na esquerda/centro.
        x_limite = min(
            ws - size + 1,
            int(ws * 0.72),
        )

        if x_limite <= 0:
            continue

        for y in range(
            0,
            y_max,
            passo,
        ):
            for x in range(
                0,
                x_limite,
                passo,
            ):
                score = _score_checkerboard(
                    pequena,
                    x,
                    y,
                    size,
                )

                if score >= 82.0:
                    melhores.append(
                        (
                            score,
                            x,
                            y,
                            size,
                        )
                    )

    if not melhores:
        return None

    melhores.sort(
        reverse=True,
        key=lambda item: item[0],
    )

    _, bx, by, bs = melhores[0]

    # Refinamento local.
    melhor = melhores[0]
    passo_refino = max(
        4,
        int(bs * 0.02),
    )

    for size in range(
        max(250, bs - 2 * passo_refino),
        min(
            min(hs, ws),
            bs + 2 * passo_refino,
        ) + 1,
        passo_refino,
    ):
        for y in range(
            max(0, by - 2 * passo_refino),
            min(
                hs - size,
                by + 2 * passo_refino,
            ) + 1,
            passo_refino,
        ):
            for x in range(
                max(0, bx - 2 * passo_refino),
                min(
                    ws - size,
                    bx + 2 * passo_refino,
                ) + 1,
                passo_refino,
            ):
                score = _score_checkerboard(
                    pequena,
                    x,
                    y,
                    size,
                )

                if score > melhor[0]:
                    melhor = (
                        score,
                        x,
                        y,
                        size,
                    )

    _, bx, by, bs = melhor

    inverso = 1.0 / escala

    return (
        int(round(bx * inverso)),
        int(round(by * inverso)),
        int(round(bs * inverso)),
    )

def iniciar_acompanhamento_janela(sct):
    """
    Localiza o board dentro da janela do Chess.com na inicialização.
    Depois guarda x/y relativos à janela, então mover a janela funciona.
    """
    global MONITOR

    if not AUTO_ACOMPANHAR_JANELA or os.name != "nt":
        return False

    encontrado = encontrar_janela_chess()

    if encontrado is None:
        return False

    hwnd, _, rect = encontrado
    left, top, width, height = rect

    ESTADO_JANELA.hwnd = hwnd
    ESTADO_JANELA.client_left = left
    ESTADO_JANELA.client_top = top
    ESTADO_JANELA.client_width = width
    ESTADO_JANELA.client_height = height

    detectado = None

    try:
        imagem_cliente = np.array(
            sct.grab(
                {
                    "left": left,
                    "top": top,
                    "width": width,
                    "height": height,
                }
            )
        )

        detectado = detectar_tabuleiro_na_janela(
            imagem_cliente
        )
    except Exception as exc:
        logger.warning(
            "Falha ao localizar board automaticamente: %s",
            exc,
        )

    if detectado is not None:
        bx, by, bsize = detectado

        ESTADO_JANELA.board_rel_x = int(bx)
        ESTADO_JANELA.board_rel_y = int(by)
        ESTADO_JANELA.board_real_size = int(bsize)

        MONITOR = {
            "left": left + int(bx),
            "top": top + int(by),
            "width": int(bsize),
            "height": int(bsize),
        }

        logger.info(
            "Board detectado na janela: x=%s y=%s size=%s",
            bx,
            by,
            bsize,
        )
        return True

    # Fallback idêntico à V22.
    ESTADO_JANELA.board_rel_x = (
        MONITOR_FIXO_V12["left"] - left
    )
    ESTADO_JANELA.board_rel_y = (
        MONITOR_FIXO_V12["top"] - top
    )
    ESTADO_JANELA.board_real_size = 816
    MONITOR = MONITOR_FIXO_V12.copy()

    logger.warning(
        "Board automático não encontrado; fallback V12 ativado."
    )
    return True



def atualizar_posicao_janela():
    global MONITOR

    if (
        not AUTO_ACOMPANHAR_JANELA
        or ESTADO_JANELA.hwnd is None
        or ESTADO_JANELA.board_rel_x is None
        or ESTADO_JANELA.board_rel_y is None
    ):
        return False

    agora = time.time()

    if (
        agora - ESTADO_JANELA.ultimo_update
        < INTERVALO_ATUALIZAR_JANELA
    ):
        return True

    ESTADO_JANELA.ultimo_update = agora

    rect = _client_rect_screen(
        ESTADO_JANELA.hwnd
    )

    if rect is None:
        return False

    left, top, width, height = rect

    ESTADO_JANELA.client_left = left
    ESTADO_JANELA.client_top = top

    MONITOR = {
        "left": left + ESTADO_JANELA.board_rel_x,
        "top": top + ESTADO_JANELA.board_rel_y,
        "width": ESTADO_JANELA.board_real_size,
        "height": ESTADO_JANELA.board_real_size,
    }

    return True





# ============================================================
# LOG
# ============================================================

logger = logging.getLogger("ark_chess")
logger.setLevel(logging.INFO)

if not logger.handlers:
    handler = RotatingFileHandler(
        ARQUIVO_LOG,
        maxBytes=1_000_000,
        backupCount=2,
        encoding="utf-8",
    )
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(message)s"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)


# ============================================================
# TIPOS
# ============================================================

@dataclass
class LeituraVisual:
    fen_pecas: str
    imagem: np.ndarray
    tabuleiro: dict
    confianca_media: float


@dataclass
class ResultadoTransicao:
    movimentos: list
    board: chess.Board


# ============================================================
# UTILIDADES
# ============================================================

def agora_ms():
    return int(time.time() * 1000)


def nome_cor(cor):
    return "Brancas" if cor == chess.WHITE else "Pretas"


def validar_ambiente():
    problemas = []

    if not CAMINHO_STOCKFISH.exists():
        problemas.append(
            f"Stockfish não encontrado em: {CAMINHO_STOCKFISH}"
        )

    if MONITOR["width"] <= 0 or MONITOR["height"] <= 0:
        problemas.append("Região MONITOR inválida.")

    if MONITOR["width"] % 8 != 0 or MONITOR["height"] % 8 != 0:
        logger.warning(
            "A região do tabuleiro não é divisível exatamente por 8."
        )

    if problemas:
        print("\n❌ Não foi possível iniciar:")
        for problema in problemas:
            print(f"- {problema}")
        return False

    return True


def imprimir_status_controlado(mensagem, memoria):
    """
    Mostra cada status apenas quando ele muda.
    Evita aquele efeito de dezenas de mensagens iguais no PowerShell.
    """
    if mensagem == memoria.get("ultima_mensagem"):
        return

    print(
        f"\r{mensagem:<72}",
        end="",
        flush=True,
    )

    memoria["ultima_mensagem"] = mensagem
    memoria["ultimo_status"] = time.time()


def limpar_status(memoria):
    memoria["ultima_mensagem"] = None


# ============================================================
# CAPTURA
# ============================================================

def capturar_frame(sct):
    if AUTO_ACOMPANHAR_JANELA:
        atualizar_posicao_janela()

    try:
        frame = np.array(
            sct.grab(MONITOR)
        )
    except mss.exception.ScreenShotError as exc:
        logger.warning(
            "Falha MSS: %s",
            exc,
        )
        return None

    if (
        frame.shape[0] != TAMANHO_FRAME_ARK
        or frame.shape[1] != TAMANHO_FRAME_ARK
    ):
        frame = cv2.resize(
            frame,
            (
                TAMANHO_FRAME_ARK,
                TAMANHO_FRAME_ARK,
            ),
            interpolation=cv2.INTER_AREA,
        )

    return frame



def calcular_mudanca(imagem1, imagem2):
    if imagem1 is None or imagem2 is None:
        return 10**9

    if imagem1.shape != imagem2.shape:
        return 10**9

    diff = cv2.absdiff(imagem1, imagem2)

    if len(diff.shape) == 3 and diff.shape[2] == 4:
        cinza = cv2.cvtColor(diff, cv2.COLOR_BGRA2GRAY)
    else:
        cinza = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)

    return int(cv2.countNonZero(cinza))


def capturar_estavel(sct):
    anterior = capturar_frame(sct)

    if anterior is None:
        return None

    melhor = anterior
    menor_mudanca = 10**18

    for _ in range(MAX_TENTATIVAS_ESTABILIDADE):
        time.sleep(INTERVALO_FRAME_ESTAVEL)

        atual = capturar_frame(sct)

        if atual is None:
            continue

        mudanca = calcular_mudanca(anterior, atual)

        if mudanca < menor_mudanca:
            menor_mudanca = mudanca
            melhor = atual

        if mudanca <= LIMITE_PIXELS_ESTABILIDADE:
            return atual

        anterior = atual

    # Em vez de falhar totalmente, devolve o frame mais estável encontrado.
    return melhor



# ============================================================
# V28 ULTRA — RASTREAMENTO DE LANCE SEM YOLO
# ============================================================

def _square_para_tela(square, orientacao):
    arquivo = chess.square_file(square)
    rank = chess.square_rank(square)

    if orientacao == "p":
        linha = rank
        coluna = 7 - arquivo
    else:
        linha = 7 - rank
        coluna = arquivo

    return linha, coluna


def _diferencas_por_casa(imagem_antiga, imagem_nova):
    """
    Mede somente a região central de cada casa.
    Isso reduz bastante hover, bordas e highlights do Chess.com.
    """
    if (
        imagem_antiga is None
        or imagem_nova is None
        or imagem_antiga.shape != imagem_nova.shape
    ):
        return None

    if imagem_antiga.shape[2] == 4:
        antiga = cv2.cvtColor(imagem_antiga, cv2.COLOR_BGRA2GRAY)
        nova = cv2.cvtColor(imagem_nova, cv2.COLOR_BGRA2GRAY)
    else:
        antiga = cv2.cvtColor(imagem_antiga, cv2.COLOR_BGR2GRAY)
        nova = cv2.cvtColor(imagem_nova, cv2.COLOR_BGR2GRAY)

    altura, largura = antiga.shape[:2]
    ys = np.linspace(0, altura, 9, dtype=int)
    xs = np.linspace(0, largura, 9, dtype=int)

    valores = {}

    for linha in range(8):
        for coluna in range(8):
            y1, y2 = ys[linha], ys[linha + 1]
            x1, x2 = xs[coluna], xs[coluna + 1]

            h = y2 - y1
            w = x2 - x1

            # Centro da casa: mantém peça, elimina boa parte de hover/bordas.
            my = max(2, int(h * 0.16))
            mx = max(2, int(w * 0.16))

            a = antiga[y1 + my:y2 - my, x1 + mx:x2 - mx]
            b = nova[y1 + my:y2 - my, x1 + mx:x2 - mx]

            if a.size == 0 or b.size == 0:
                valores[(linha, coluna)] = 0.0
                continue

            valores[(linha, coluna)] = float(
                np.mean(cv2.absdiff(a, b))
            )

    return valores


def _casas_esperadas_lance(board, movimento, orientacao):
    casas = {
        _square_para_tela(movimento.from_square, orientacao),
        _square_para_tela(movimento.to_square, orientacao),
    }

    if board.is_castling(movimento):
        if movimento.to_square == chess.G1:
            extras = (chess.H1, chess.F1)
        elif movimento.to_square == chess.C1:
            extras = (chess.A1, chess.D1)
        elif movimento.to_square == chess.G8:
            extras = (chess.H8, chess.F8)
        else:
            extras = (chess.A8, chess.D8)

        for sq in extras:
            casas.add(_square_para_tela(sq, orientacao))

    if board.is_en_passant(movimento):
        capturada = (
            movimento.to_square - 8
            if board.turn == chess.WHITE
            else movimento.to_square + 8
        )
        casas.add(_square_para_tela(capturada, orientacao))

    return casas


def detectar_lance_visual_rapido(
    board,
    imagem_antiga,
    imagem_nova,
    orientacao,
):
    """
    Escolhe o lance legal que melhor explica as casas que mudaram.
    Não chama YOLO e não escreve 64 PNGs no disco.
    """
    diffs = _diferencas_por_casa(
        imagem_antiga,
        imagem_nova,
    )

    if not diffs:
        return None, 0.0

    valores = np.array(list(diffs.values()), dtype=np.float32)
    mediana = float(np.median(valores))
    desvio = float(np.std(valores))

    # Threshold dinâmico. Hover isolado normalmente muda uma casa;
    # um lance real muda origem + destino.
    limiar = max(5.0, mediana + max(3.5, desvio * 0.55))

    ranking = sorted(
        diffs.items(),
        key=lambda item: item[1],
        reverse=True,
    )
    top = {casa for casa, _ in ranking[:5]}

    melhor = None
    melhor_score = float("-inf")
    segundo_score = None

    for movimento in board.legal_moves:
        esperadas = _casas_esperadas_lance(
            board,
            movimento,
            orientacao,
        )

        valores_esperados = [diffs[c] for c in esperadas]
        if len(valores_esperados) < 2:
            continue

        origem = _square_para_tela(
            movimento.from_square,
            orientacao,
        )
        destino = _square_para_tela(
            movimento.to_square,
            orientacao,
        )

        # Origem e destino precisam ter alteração real.
        minimo_principal = min(
            diffs[origem],
            diffs[destino],
        )

        if minimo_principal < limiar * 0.72:
            continue

        esperado_medio = float(np.mean(valores_esperados))
        cobertura_top = len(esperadas & top)

        inesperadas = [
            valor
            for casa, valor in ranking[:6]
            if casa not in esperadas
        ]
        ruido = (
            float(np.mean(inesperadas[:2]))
            if inesperadas
            else 0.0
        )

        score = (
            esperado_medio
            + minimo_principal * 0.75
            + cobertura_top * 6.0
            - ruido * 0.28
        )

        if score > melhor_score:
            if melhor is not None:
                segundo_score = melhor_score
            melhor_score = score
            melhor = movimento
        elif segundo_score is None or score > segundo_score:
            segundo_score = score

    if melhor is None:
        return None, 0.0

    separacao = (
        max(0.0, melhor_score - segundo_score)
        if segundo_score is not None
        else 0.0
    )

    # Score apenas informativo; sem números artificiais gigantes.
    confianca = melhor_score + min(separacao, 80.0) * 0.35

    # Evita aceitar hover/ruído como lance.
    if confianca < 18.0:
        return None, confianca

    return melhor, confianca


def mostrar_estado_rapido(board, minha_cor, movimento):
    print("\n\n========================================")
    print("⚡ LANCE ULTRA CONFIRMADO")
    print("========================================")
    print("\nLance detectado:")
    print(f"- {movimento.uci()}")
    print(f"\nFEN:\n{board.fen()}")
    print(f"\nVez: {nome_cor(board.turn)}")

    if board.turn == minha_cor:
        print("\n✓ SUA VEZ")
    else:
        print("\nAguardando jogada do adversário...")

# ============================================================
# VISÃO
# ============================================================

def recortar_casas(imagem):
    PASTA_CASAS.mkdir(parents=True, exist_ok=True)

    altura, largura = imagem.shape[:2]

    # Usa limites calculados por proporção. Isso evita perder pixels
    # se o tamanho da região não for múltiplo exato de 8.
    ys = np.linspace(0, altura, 9, dtype=int)
    xs = np.linspace(0, largura, 9, dtype=int)

    for linha in range(8):
        for coluna in range(8):
            casa = imagem[
                ys[linha]:ys[linha + 1],
                xs[coluna]:xs[coluna + 1],
            ]

            caminho = PASTA_CASAS / f"casa_{linha}_{coluna}.png"
            cv2.imwrite(str(caminho), casa)


def confianca_media_tabuleiro(tabuleiro):
    valores = []

    for classe, confianca in tabuleiro.values():
        try:
            valor = float(confianca)
        except (TypeError, ValueError):
            continue

        # A classe vazia também é informação real do classificador.
        if classe:
            valores.append(valor)

    if not valores:
        return 0.0

    return sum(valores) / len(valores)


def estrutura_visual_plausivel(tabuleiro):
    contagem = {}

    for classe, _ in tabuleiro.values():
        contagem[classe] = contagem.get(classe, 0) + 1

    if contagem.get("rei_branco", 0) != 1:
        return False

    if contagem.get("rei_preto", 0) != 1:
        return False

    if contagem.get("peao_branco", 0) > 8:
        return False

    if contagem.get("peao_preto", 0) > 8:
        return False

    pecas_brancas = sum(
        quantidade
        for classe, quantidade in contagem.items()
        if classe.endswith("_branco")
    )

    pecas_pretas = sum(
        quantidade
        for classe, quantidade in contagem.items()
        if classe.endswith("_preto")
    )

    if pecas_brancas > 16 or pecas_pretas > 16:
        return False

    # Um tabuleiro real precisa ter pelo menos os dois reis.
    if pecas_brancas < 1 or pecas_pretas < 1:
        return False

    return True



def motivo_estrutura_visual_invalida(tabuleiro):
    contagem = {}

    for classe, _ in tabuleiro.values():
        contagem[classe] = contagem.get(classe, 0) + 1

    motivos = []

    if contagem.get("rei_branco", 0) != 1:
        motivos.append(
            f"rei_branco={contagem.get('rei_branco', 0)} (esperado 1)"
        )

    if contagem.get("rei_preto", 0) != 1:
        motivos.append(
            f"rei_preto={contagem.get('rei_preto', 0)} (esperado 1)"
        )

    if contagem.get("peao_branco", 0) > 8:
        motivos.append(
            f"peao_branco={contagem.get('peao_branco', 0)} (>8)"
        )

    if contagem.get("peao_preto", 0) > 8:
        motivos.append(
            f"peao_preto={contagem.get('peao_preto', 0)} (>8)"
        )

    pecas_brancas = sum(
        quantidade
        for classe, quantidade in contagem.items()
        if classe.endswith("_branco")
    )

    pecas_pretas = sum(
        quantidade
        for classe, quantidade in contagem.items()
        if classe.endswith("_preto")
    )

    if pecas_brancas > 16:
        motivos.append(f"pecas_brancas={pecas_brancas} (>16)")

    if pecas_pretas > 16:
        motivos.append(f"pecas_pretas={pecas_pretas} (>16)")

    if pecas_brancas < 1:
        motivos.append("nenhuma peça branca reconhecida")

    if pecas_pretas < 1:
        motivos.append("nenhuma peça preta reconhecida")

    if not motivos:
        motivos.append("estrutura passou; falha ocorreu em outra etapa")

    return motivos, contagem


def salvar_diagnostico_inicio(imagem, tabuleiro, numero):
    """
    Salva exatamente o que o ARK estava vendo quando não conseguiu
    validar o tabuleiro. Não altera a lógica de reconhecimento.
    """
    try:
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        pasta = PASTA_DIAGNOSTICOS / f"{timestamp}_{numero:02d}"
        pasta.mkdir(parents=True, exist_ok=True)

        cv2.imwrite(str(pasta / "frame_816.png"), imagem)

        # recortar_casas já criou os 64 arquivos; copiamos um snapshot
        # sem depender de bibliotecas extras.
        pasta_casas = pasta / "casas"
        pasta_casas.mkdir(parents=True, exist_ok=True)

        for linha in range(8):
            for coluna in range(8):
                origem = PASTA_CASAS / f"casa_{linha}_{coluna}.png"
                destino = pasta_casas / origem.name

                if origem.exists():
                    dados = origem.read_bytes()
                    destino.write_bytes(dados)

        motivos, contagem = motivo_estrutura_visual_invalida(tabuleiro)
        confianca = confianca_media_tabuleiro(tabuleiro)

        linhas = []
        linhas.append(f"ARK Chess {VERSAO} - Diagnóstico de visão")
        linhas.append(f"Data/hora: {timestamp}")
        linhas.append(f"Região capturada: {MONITOR}")
        linhas.append(f"Confiança média: {confianca:.4f}")
        linhas.append("")
        linhas.append("MOTIVO(S) DA REJEIÇÃO:")
        for motivo in motivos:
            linhas.append(f"- {motivo}")

        linhas.append("")
        linhas.append("CONTAGEM POR CLASSE:")
        for classe in sorted(contagem):
            linhas.append(f"- {classe}: {contagem[classe]}")

        linhas.append("")
        linhas.append("GRADE RECONHECIDA:")
        for linha in range(8):
            partes = []
            for coluna in range(8):
                classe, conf = tabuleiro[(linha, coluna)]
                try:
                    conf_txt = f"{float(conf):.3f}"
                except (TypeError, ValueError):
                    conf_txt = str(conf)

                partes.append(
                    f"[{linha},{coluna}] {classe} ({conf_txt})"
                )
            linhas.append(" | ".join(partes))

        # Tenta gerar uma FEN nas duas orientações apenas para diagnóstico.
        linhas.append("")
        linhas.append("FEN DE DIAGNÓSTICO:")
        try:
            linhas.append(
                f"- brancas embaixo: {gerar_fen_pecas(tabuleiro, 'b')}"
            )
        except Exception as exc:
            linhas.append(f"- brancas embaixo: ERRO {exc}")

        try:
            linhas.append(
                f"- pretas embaixo: {gerar_fen_pecas(tabuleiro, 'p')}"
            )
        except Exception as exc:
            linhas.append(f"- pretas embaixo: ERRO {exc}")

        (pasta / "diagnostico.txt").write_text(
            "\n".join(linhas),
            encoding="utf-8",
        )

        print("")
        print("⚠ DIAGNÓSTICO V25 SALVO")
        print(f"  Pasta: {pasta}")
        print("  Arquivos: frame_816.png, diagnostico.txt e 64 casas")
        print("")

        logger.warning(
            "Diagnóstico V25 salvo em %s | motivos=%s",
            pasta,
            motivos,
        )

        return pasta

    except Exception as exc:
        logger.exception(
            "Falha ao salvar diagnóstico V25: %s",
            exc,
        )
        return None


def detectar_cor_em_baixo(tabuleiro):
    """
    Retorna:
        ("b", score) -> Brancas embaixo
        ("p", score) -> Pretas embaixo

    score maior = orientação mais clara.
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

    score_brancas = brancas_baixo + pretas_cima
    score_pretas = pretas_baixo + brancas_cima

    diferenca = abs(score_brancas - score_pretas)

    if score_pretas > score_brancas:
        return "p", diferenca

    return "b", diferenca


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
            simbolo = SIMBOLOS.get(classe, ".")

            if simbolo == ".":
                vazias += 1
            else:
                if vazias:
                    linha_fen += str(vazias)
                    vazias = 0

                linha_fen += simbolo

        if vazias:
            linha_fen += str(vazias)

        linhas_fen.append(linha_fen)

    return "/".join(linhas_fen)


def fen_basica_sintaticamente_valida(fen_pecas):
    try:
        board = chess.Board(
            f"{fen_pecas} w - - 0 1"
        )
    except ValueError:
        return False

    rei_branco = board.king(chess.WHITE)
    rei_preto = board.king(chess.BLACK)

    return (
        rei_branco is not None
        and rei_preto is not None
    )


def ler_tabuleiro_uma_vez(sct, orientacao):
    imagem = capturar_estavel(sct)

    if imagem is None:
        return None

    recortar_casas(imagem)

    try:
        tabuleiro = analisar_tabuleiro()
    except Exception as exc:
        logger.exception("Falha no classificador: %s", exc)
        return None

    if not estrutura_visual_plausivel(tabuleiro):
        return None

    confianca = confianca_media_tabuleiro(tabuleiro)

    if confianca < CONFIANCA_MEDIA_MINIMA:
        logger.info(
            "Leitura descartada por baixa confiança: %.3f",
            confianca,
        )
        return None

    fen = gerar_fen_pecas(tabuleiro, orientacao)

    try:
        chess.Board(
            f"{fen} w - - 0 1"
        )
    except ValueError:
        return None

    return LeituraVisual(
        fen_pecas=fen,
        imagem=imagem,
        tabuleiro=tabuleiro,
        confianca_media=confianca,
    )


def reconhecer_consenso(sct, orientacao):
    """
    Procura duas leituras iguais. Isso filtra:
    - animação de peça;
    - arraste inválido;
    - peça voltando;
    - frame intermediário;
    - classificação isolada errada.
    """
    contador = {}
    melhor_por_fen = {}

    for _ in range(MAX_TENTATIVAS_RECONHECIMENTO):
        leitura = ler_tabuleiro_uma_vez(
            sct,
            orientacao,
        )

        if leitura is not None:
            fen = leitura.fen_pecas
            contador[fen] = contador.get(fen, 0) + 1

            anterior = melhor_por_fen.get(fen)

            if (
                anterior is None
                or leitura.confianca_media > anterior.confianca_media
            ):
                melhor_por_fen[fen] = leitura

            if contador[fen] >= LEITURAS_IGUAIS_NECESSARIAS:
                return melhor_por_fen[fen]

        time.sleep(INTERVALO_ENTRE_LEITURAS)

    return None


def reconhecer_consenso_agressivo(
    sct,
    orientacao,
    fen_anterior=None,
):
    """
    Quando existe uma mudança visual forte, faz mais leituras e prefere
    qualquer FEN válido diferente do estado anterior.

    Isso evita perder um lance porque uma leitura isolada do YOLO
    devolveu acidentalmente o tabuleiro antigo.
    """
    contador = {}
    melhor_por_fen = {}

    for _ in range(
        MAX_TENTATIVAS_RECONHECIMENTO_AGRESSIVO
    ):
        leitura = ler_tabuleiro_uma_vez(
            sct,
            orientacao,
        )

        if leitura is not None:
            fen = leitura.fen_pecas

            contador[fen] = contador.get(
                fen,
                0,
            ) + 1

            anterior = melhor_por_fen.get(fen)

            if (
                anterior is None
                or leitura.confianca_media
                > anterior.confianca_media
            ):
                melhor_por_fen[fen] = leitura

            # Se já vimos duas vezes uma posição NOVA, aceita imediatamente.
            if (
                fen != fen_anterior
                and contador[fen] >= 2
            ):
                return melhor_por_fen[fen]

        time.sleep(
            INTERVALO_AGRESSIVO
        )

    # Fallback: escolhe a posição diferente mais repetida.
    candidatos = [
        (
            quantidade,
            melhor_por_fen[fen]
        )
        for fen, quantidade in contador.items()
        if fen != fen_anterior
    ]

    if candidatos:
        candidatos.sort(
            key=lambda item: (
                item[0],
                item[1].confianca_media,
            ),
            reverse=True,
        )
        return candidatos[0][1]

    return None


def reconhecer_inicio(sct):
    memoria = {}
    falhas_invalidas = 0
    diagnosticos_salvos = 0
    ultimo_diagnostico = 0.0

    while True:
        imagem = capturar_estavel(sct)

        if imagem is None:
            imprimir_status_controlado(
                "⟳ Aguardando captura da tela...",
                memoria,
            )
            time.sleep(0.5)
            continue

        recortar_casas(imagem)

        try:
            tabuleiro = analisar_tabuleiro()
        except Exception as exc:
            logger.exception(
                "Falha reconhecendo posição inicial: %s",
                exc,
            )
            time.sleep(0.5)
            continue

        if not estrutura_visual_plausivel(tabuleiro):
            falhas_invalidas += 1

            imprimir_status_controlado(
                "⟳ Procurando um tabuleiro válido...",
                memoria,
            )

            agora = time.monotonic()

            if (
                falhas_invalidas >= DIAGNOSTICO_APOS_FALHAS
                and diagnosticos_salvos < MAX_DIAGNOSTICOS_INICIO
                and (
                    diagnosticos_salvos == 0
                    or agora - ultimo_diagnostico >= INTERVALO_DIAGNOSTICO
                )
            ):
                diagnosticos_salvos += 1
                salvar_diagnostico_inicio(
                    imagem,
                    tabuleiro,
                    diagnosticos_salvos,
                )
                ultimo_diagnostico = agora

            time.sleep(0.4)
            continue

        # Se voltou a enxergar uma estrutura plausível, zera a sequência.
        falhas_invalidas = 0

        orientacao, score = detectar_cor_em_baixo(tabuleiro)

        leitura = reconhecer_consenso(
            sct,
            orientacao,
        )

        if leitura is None:
            imprimir_status_controlado(
                "⟳ Confirmando tabuleiro...",
                memoria,
            )
            continue

        # Recalcula orientação em cima da leitura confirmada.
        orientacao_confirmada, score_confirmado = detectar_cor_em_baixo(
            leitura.tabuleiro
        )

        if orientacao_confirmada != orientacao:
            orientacao = orientacao_confirmada
            leitura = reconhecer_consenso(
                sct,
                orientacao,
            )

            if leitura is None:
                continue

        print(
            "\r✓ Tabuleiro reconhecido e confirmado.                    "
        )

        logger.info(
            "Tabuleiro inicial: %s | orientacao=%s | score=%s | conf=%.3f",
            leitura.fen_pecas,
            orientacao,
            max(score, score_confirmado),
            leitura.confianca_media,
        )

        return leitura, orientacao


# ============================================================
# ESTADO DE XADREZ
# ============================================================

FEN_INICIAL = (
    "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR"
)


def eh_posicao_inicial(fen_pecas):
    return fen_pecas == FEN_INICIAL


def direitos_roque_maximos(fen_pecas):
    """
    Descobre o máximo de direitos de roque POSSÍVEIS pela posição
    das peças. Em uma reabertura no meio do jogo isso ainda pode ser
    ambíguo, então V10 trata esse estado como provisório.
    """
    try:
        board = chess.Board(
            f"{fen_pecas} w - - 0 1"
        )
    except ValueError:
        return ""

    direitos = ""

    rei = board.piece_at(chess.E1)

    if (
        rei
        and rei.piece_type == chess.KING
        and rei.color == chess.WHITE
    ):
        torre = board.piece_at(chess.H1)
        if (
            torre
            and torre.piece_type == chess.ROOK
            and torre.color == chess.WHITE
        ):
            direitos += "K"

        torre = board.piece_at(chess.A1)
        if (
            torre
            and torre.piece_type == chess.ROOK
            and torre.color == chess.WHITE
        ):
            direitos += "Q"

    rei = board.piece_at(chess.E8)

    if (
        rei
        and rei.piece_type == chess.KING
        and rei.color == chess.BLACK
    ):
        torre = board.piece_at(chess.H8)
        if (
            torre
            and torre.piece_type == chess.ROOK
            and torre.color == chess.BLACK
        ):
            direitos += "k"

        torre = board.piece_at(chess.A8)
        if (
            torre
            and torre.piece_type == chess.ROOK
            and torre.color == chess.BLACK
        ):
            direitos += "q"

    return direitos


def criar_board(
    fen_pecas,
    lado,
    direitos_roque="",
    ep_square="-",
):
    roques = direitos_roque if direitos_roque else "-"

    fen = (
        f"{fen_pecas} "
        f"{'w' if lado == chess.WHITE else 'b'} "
        f"{roques} "
        f"{ep_square} "
        f"0 1"
    )

    try:
        board = chess.Board(fen)
    except ValueError:
        return None

    if not board.is_valid():
        return None

    return board


def gerar_candidatos_reabertura(fen_pecas):
    """
    Em uma posição de meio de jogo a imagem não informa:
    - de quem é a vez;
    - se rei/torre já moveram e voltaram;
    - en passant.

    Para não inventar um estado, cria candidatos plausíveis e deixa
    o próximo lance real eliminar os impossíveis.
    """
    max_roques = direitos_roque_maximos(fen_pecas)
    candidatos = []

    # Todos os subconjuntos dos direitos máximos.
    subconjuntos = set()

    for tamanho in range(len(max_roques) + 1):
        for combo in itertools.combinations(max_roques, tamanho):
            subconjuntos.add("".join(combo))

    for lado in (chess.WHITE, chess.BLACK):
        for roques in subconjuntos:
            board = criar_board(
                fen_pecas,
                lado,
                roques,
            )

            if board is not None:
                candidatos.append(board)

    # Remove duplicatas pelo FEN completo.
    unicos = {}
    for board in candidatos:
        unicos[board.fen()] = board

    return list(unicos.values())


def assinatura_estado(board):
    return (
        board.board_fen(),
        board.turn,
        board.castling_rights,
        board.ep_square,
    )


def procurar_transicao(
    board_inicial,
    fen_alvo,
    max_plies=MAX_PLIES_RECUPERACAO,
):
    """
    BFS legal limitada.
    Aceita somente estados que podem ser PROVADOS por lances legais.
    """
    if board_inicial.board_fen() == fen_alvo:
        return ResultadoTransicao(
            movimentos=[],
            board=board_inicial.copy(stack=True),
        )

    fila = [
        (
            board_inicial.copy(stack=True),
            [],
        )
    ]

    visitados = set()
    estados_processados = 0

    for _profundidade in range(1, max_plies + 1):
        proxima = []

        for board_atual, caminho in fila:
            assinatura = assinatura_estado(board_atual)

            if assinatura in visitados:
                continue

            visitados.add(assinatura)

            for movimento in list(board_atual.legal_moves):
                teste = board_atual.copy(stack=True)
                teste.push(movimento)

                estados_processados += 1

                if estados_processados > MAX_ESTADOS_BFS:
                    logger.warning(
                        "BFS interrompida no limite de %s estados.",
                        MAX_ESTADOS_BFS,
                    )
                    return None

                novo_caminho = caminho + [movimento]

                if teste.board_fen() == fen_alvo:
                    return ResultadoTransicao(
                        movimentos=novo_caminho,
                        board=teste,
                    )

                proxima.append(
                    (
                        teste,
                        novo_caminho,
                    )
                )

        fila = proxima

    return None


def sincronizar_candidatos(candidatos, fen_alvo):
    """
    Usa um NOVO lance real para descobrir o turno.

    Direitos históricos de roque podem continuar ambíguos depois de
    reabrir o ARK. Isso não deve impedir a sincronização inteira.
    Quando todos os estados finais concordam sobre board_fen + turno,
    criamos um estado conservador usando apenas os direitos de roque
    presentes em TODOS os candidatos.
    """
    encontrados = []

    for candidato in candidatos:
        resultado = procurar_transicao_v26(
            candidato,
            fen_alvo,
            max_plies=1,
        )

        if (
            resultado is not None
            and len(resultado.movimentos) == 1
        ):
            encontrados.append(resultado)

    if not encontrados:
        return None, candidatos

    # Todos precisam concordar com a posição visual final.
    por_posicao_turno = {}

    for resultado in encontrados:
        chave = (
            resultado.board.board_fen(),
            resultado.board.turn,
        )
        por_posicao_turno.setdefault(
            chave,
            []
        ).append(resultado)

    # Se só existe um board_fen + turno possível, o turno está provado.
    if len(por_posicao_turno) == 1:
        grupo = next(
            iter(por_posicao_turno.values())
        )

        representante = grupo[0]
        board_seguro = representante.board.copy(
            stack=True
        )

        # Interseção: só mantém um direito de roque se TODOS os
        # candidatos compatíveis também o possuírem.
        direitos = grupo[0].board.castling_rights

        for resultado in grupo[1:]:
            direitos &= (
                resultado.board.castling_rights
            )

        board_seguro.castling_rights = direitos

        # O en passant vem do lance recém-observado. Se houver
        # divergência entre candidatos, removemos por segurança.
        eps = {
            resultado.board.ep_square
            for resultado in grupo
        }

        if len(eps) == 1:
            board_seguro.ep_square = next(
                iter(eps)
            )
        else:
            board_seguro.ep_square = None

        return ResultadoTransicao(
            movimentos=representante.movimentos,
            board=board_seguro,
        ), [board_seguro]

    # Ainda há mais de um turno possível.
    proximos = []

    vistos = set()

    for resultado in encontrados:
        chave = assinatura_estado(
            resultado.board
        )

        if chave not in vistos:
            vistos.add(chave)
            proximos.append(
                resultado.board
            )

    return None, proximos



def confirmar_fim_visual(sct, board, orientacao):
    """
    Um mate/empate lógico só encerra o ARK se a posição física da tela
    confirmar a mesma colocação de peças em duas leituras.
    Isso impede que um fast-track falso encerre a partida.
    """
    alvo = board.board_fen()
    acertos = 0

    for _ in range(2):
        leitura = ler_tabuleiro_uma_vez(
            sct,
            orientacao,
        )

        if (
            leitura is not None
            and leitura.fen_pecas == alvo
        ):
            acertos += 1

        time.sleep(0.025)

    return acertos >= 2


def verificar_fim_partida_confirmado(
    sct,
    board,
    minha_cor,
    orientacao,
):
    if not board.is_game_over(claim_draw=False):
        return False

    print(
        "\n⟳ Possível fim de partida detectado; "
        "confirmando visualmente..."
    )

    if not confirmar_fim_visual(
        sct,
        board,
        orientacao,
    ):
        print(
            "⚠ Fim lógico rejeitado: a tela não confirmou "
            "essa posição."
        )
        return False

    return verificar_fim_partida(
        board,
        minha_cor,
    )



def verificar_fim_partida(board, minha_cor):
    if not board.is_game_over(claim_draw=False):
        return False

    outcome = board.outcome(claim_draw=False)

    print("\n\n========================================")
    print("              FIM DE PARTIDA")
    print("========================================")

    if outcome is None:
        print("\nPartida encerrada.")
        return True

    if outcome.winner is None:
        print("\n🤝 EMPATE")
    elif outcome.winner == minha_cor:
        print("\n🏆 VOCÊ VENCEU!")
    else:
        print("\nVitória do adversário.")

    motivos = {
        chess.Termination.CHECKMATE: "Xeque-mate",
        chess.Termination.STALEMATE: "Afogamento",
        chess.Termination.INSUFFICIENT_MATERIAL: "Material insuficiente",
        chess.Termination.SEVENTYFIVE_MOVES: "Regra dos 75 lances",
        chess.Termination.FIVEFOLD_REPETITION: "Repetição quíntupla",
        chess.Termination.FIFTY_MOVES: "Regra dos 50 lances",
        chess.Termination.THREEFOLD_REPETITION: "Repetição tripla",
        chess.Termination.VARIANT_WIN: "Vitória",
        chess.Termination.VARIANT_LOSS: "Derrota",
        chess.Termination.VARIANT_DRAW: "Empate",
    }

    print(
        f"Motivo: {motivos.get(outcome.termination, str(outcome.termination))}"
    )

    print("========================================")

    logger.info(
        "Fim de partida: %s",
        outcome,
    )

    return True


# ============================================================
# STOCKFISH
# ============================================================

class StockfishSeguro:
    def __init__(self):
        self.engine = None

    def iniciar(self):
        self.encerrar()

        self.engine = chess.engine.SimpleEngine.popen_uci(
            str(CAMINHO_STOCKFISH)
        )

        threads = min(
            STOCKFISH_THREADS_MAX,
            max(1, os.cpu_count() or 1),
        )

        opcoes = {
            "Threads": threads,
            "Hash": STOCKFISH_HASH_MB,
        }

        try:
            self.engine.configure(opcoes)
        except Exception as exc:
            logger.warning(
                "Não consegui configurar Stockfish: %s",
                exc,
            )

        logger.info(
            "Stockfish iniciado | Threads=%s | Hash=%s",
            threads,
            STOCKFISH_HASH_MB,
        )

    def encerrar(self):
        if self.engine is None:
            return

        try:
            self.engine.quit()
        except Exception:
            pass

        self.engine = None

    def analisar(self, board):
        if self.engine is None:
            self.iniciar()

        try:
            return self.engine.analyse(
                board,
                chess.engine.Limit(
                    time=STOCKFISH_TEMPO_ANALISE
                ),
            )
        except (
            chess.engine.EngineTerminatedError,
            chess.engine.EngineError,
            BrokenPipeError,
            OSError,
        ) as exc:
            logger.warning(
                "Stockfish falhou; reiniciando: %s",
                exc,
            )

            self.iniciar()

            return self.engine.analyse(
                board,
                chess.engine.Limit(
                    time=STOCKFISH_TEMPO_ANALISE
                ),
            )


def formatar_melhor_jogada(board, movimento):
    origem = chess.square_name(
        movimento.from_square
    )

    destino = chess.square_name(
        movimento.to_square
    )

    peca = board.piece_at(
        movimento.from_square
    )

    nome = (
        NOMES_PECAS.get(peca.piece_type, "Peça")
        if peca is not None
        else "Peça"
    )

    sufixos = []

    if board.is_castling(movimento):
        sufixos.append("roque")

    if board.is_capture(movimento):
        sufixos.append("captura")

    if movimento.promotion:
        promocao = NOMES_PROMOCAO.get(
            movimento.promotion,
            "Peça",
        )
        sufixos.append(
            f"promove para {promocao}"
        )

    teste = board.copy(stack=False)

    try:
        teste.push(movimento)

        if teste.is_checkmate():
            sufixos.append("xeque-mate")
        elif teste.is_check():
            sufixos.append("xeque")
    except Exception:
        pass

    texto = f"{nome} {origem} -> {destino}"

    if sufixos:
        texto += " (" + ", ".join(sufixos) + ")"

    return texto


def analisar_stockfish(stockfish, board):
    if board.is_game_over():
        return

    print("\nStockfish analisando...")

    try:
        analise = stockfish.analisar(board)
    except Exception as exc:
        logger.exception(
            "Falha definitiva no Stockfish: %s",
            exc,
        )
        print(
            "\n⚠ Não consegui analisar esta posição agora."
        )
        return

    pv = analise.get("pv", [])

    if not pv:
        print("\nNenhuma jogada encontrada.")
        return

    movimento = pv[0]

    print("\nMELHOR JOGADA:\n")
    print(
        formatar_melhor_jogada(
            board,
            movimento,
        )
    )


# ============================================================
# APRESENTAÇÃO DE ESTADO
# ============================================================

def mostrar_estado(
    leitura,
    board,
    minha_cor,
    movimentos=None,
    recuperado=False,
):
    print("\n\n========================================")

    if recuperado:
        print("✓ SINCRONIZAÇÃO RECUPERADA")
    else:
        print("✓ NOVA POSIÇÃO CONFIRMADA")

    print("========================================")

    if movimentos:
        print("\nLance(s) detectado(s):")

        temp = board.copy(stack=True)

        # O board recebido já está depois dos movimentos. Para evitar
        # reconstrução errada de SAN aqui, exibimos UCI de forma segura.
        for movimento in movimentos:
            print(f"- {movimento.uci()}")

    print("\nTABULEIRO RECONHECIDO:")
    mostrar_tabuleiro(
        leitura.tabuleiro
    )

    print(
        f"\nFEN:\n{board.fen()}"
    )

    print(
        f"\nVez: {nome_cor(board.turn)}"
    )

    if board.turn == minha_cor:
        print("\n✓ SUA VEZ")
    else:
        print("\nAguardando jogada do adversário...")


# ============================================================
# V26 — SINCRONIZAÇÃO INICIAL + ROQUE ROBUSTO
# ============================================================

def ler_argumentos():
    parser = argparse.ArgumentParser(add_help=True)
    parser.add_argument(
        "--turno-inicial",
        choices=("minha", "bot"),
        default="minha",
        help=(
            "Em partida já iniciada, informe explicitamente "
            "se é sua vez ou a vez do bot."
        ),
    )
    return parser.parse_args()


def lado_inicial_escolhido(opcao, minha_cor):
    if opcao == "minha":
        return minha_cor

    if opcao == "bot":
        return not minha_cor

    return None


def criar_board_turno_manual(fen_pecas, lado):
    """
    Cria um estado utilizável imediatamente quando o usuário informa
    de quem é a vez. Direitos históricos de roque não podem ser vistos
    numa imagem estática, então começamos conservadoramente sem direitos.
    Se um roque real aparecer depois, o fallback visual da V26 recupera
    esse direito com segurança a partir da própria mudança observada.
    """
    return criar_board(
        fen_pecas,
        lado,
        direitos_roque="",
        ep_square="-",
    )


def tentar_roque_visual(board_inicial, fen_alvo):
    """
    Se o histórico perdeu um direito de roque durante uma reabertura/
    ressincronização, o python-chess pode considerar o roque ilegal.
    A V26 testa SOMENTE os quatro roques possíveis e aceita apenas se
    a posição visual final bater exatamente com o FEN observado.
    """
    possibilidades = (
        (chess.WHITE, chess.E1, chess.H1, chess.E1, chess.G1, chess.Move.from_uci("e1g1")),
        (chess.WHITE, chess.E1, chess.A1, chess.E1, chess.C1, chess.Move.from_uci("e1c1")),
        (chess.BLACK, chess.E8, chess.H8, chess.E8, chess.G8, chess.Move.from_uci("e8g8")),
        (chess.BLACK, chess.E8, chess.A8, chess.E8, chess.C8, chess.Move.from_uci("e8c8")),
    )

    for cor, casa_rei, casa_torre, _, _, movimento in possibilidades:
        if board_inicial.turn != cor:
            continue

        rei = board_inicial.piece_at(casa_rei)
        torre = board_inicial.piece_at(casa_torre)

        if (
            rei is None
            or rei.piece_type != chess.KING
            or rei.color != cor
            or torre is None
            or torre.piece_type != chess.ROOK
            or torre.color != cor
        ):
            continue

        teste = board_inicial.copy(stack=True)

        # Reativa APENAS o direito correspondente para testar o fato visual.
        if movimento == chess.Move.from_uci("e1g1"):
            teste.castling_rights |= chess.BB_H1
        elif movimento == chess.Move.from_uci("e1c1"):
            teste.castling_rights |= chess.BB_A1
        elif movimento == chess.Move.from_uci("e8g8"):
            teste.castling_rights |= chess.BB_H8
        elif movimento == chess.Move.from_uci("e8c8"):
            teste.castling_rights |= chess.BB_A8

        if movimento not in teste.legal_moves:
            continue

        teste.push(movimento)

        if teste.board_fen() == fen_alvo:
            logger.info(
                "V26 recuperou roque visualmente: %s",
                movimento.uci(),
            )
            return ResultadoTransicao(
                movimentos=[movimento],
                board=teste,
            )

    return None


def procurar_transicao_v26(
    board_inicial,
    fen_alvo,
    max_plies=MAX_PLIES_RECUPERACAO,
):
    resultado = procurar_transicao(
        board_inicial,
        fen_alvo,
        max_plies=max_plies,
    )

    if resultado is not None:
        return resultado

    return tentar_roque_visual(
        board_inicial,
        fen_alvo,
    )


# ============================================================
# LOOP PRINCIPAL
# ============================================================

def main():
    args = ler_argumentos()

    print("\n========================================")
    print(f"          ARK CHESS {VERSAO}")
    print("       SISTEMA DE TREINAMENTO")
    print("========================================")
    print("Base: V28 Ultra + proteção anti-fantasma")
    print("Acompanhamento da janela: ON")
    print("Localização automática do board: ON")
    print("Frame da visão normalizado: 816x816")
    print("Cronômetro: OFF")
    print("Proteção contra espera/ruído: ON")
    print("Diagnóstico automático de visão: ON")
    print("Recuperação explícita de roque: ON")
    print("Fast-Track sem YOLO durante os lances: ON")
    print("Confirmação visual de fim de partida: ON")
    print(f"Turno inicial: {args.turno_inicial}")

    if not validar_ambiente():
        return 1

    stockfish = StockfishSeguro()

    try:
        print("\nIniciando Stockfish...")
        stockfish.iniciar()
    except Exception as exc:
        logger.exception(
            "Erro iniciando Stockfish: %s",
            exc,
        )
        print(
            "\n❌ Não consegui iniciar o Stockfish."
        )
        return 1

    try:
        with mss.MSS() as sct:
            print("\nAbra o tabuleiro contra o bot.")

            if iniciar_acompanhamento_janela(sct):
                print("✓ Janela do Chess.com encontrada.")
                print("✓ Board localizado dentro da janela.")
                print(f"  Região real: {MONITOR}")
                print("  Frame da visão: 816x816")
            else:
                print("⚠ Janela não localizada; usando região fixa da V12.")

            print("Procurando posição válida...")

            leitura_inicial, orientacao = reconhecer_inicio(
                sct
            )

            minha_cor = (
                chess.WHITE
                if orientacao == "b"
                else chess.BLACK
            )

            print(
                f"\n✓ Sua cor: {nome_cor(minha_cor)} "
                "(detectada pela orientação)"
            )

            imagem_referencia = leitura_inicial.imagem.copy()

            board_confirmado = None
            candidatos = []
            estado_provisorio = False
            fen_base_provisoria = None

            if eh_posicao_inicial(
                leitura_inicial.fen_pecas
            ):
                board_confirmado = chess.Board()
                estado_provisorio = False

                print(
                    "\n✓ Partida inicial detectada. "
                    "Turno e roques conhecidos."
                )

            else:
                lado_manual = lado_inicial_escolhido(
                    args.turno_inicial,
                    minha_cor,
                )

                if lado_manual is not None:
                    board_manual = criar_board_turno_manual(
                        leitura_inicial.fen_pecas,
                        lado_manual,
                    )

                    if board_manual is not None:
                        board_confirmado = board_manual
                        candidatos = []
                        estado_provisorio = False
                        fen_base_provisoria = None

                        print(
                            "\n✓ Partida em andamento sincronizada "
                            "pelo turno escolhido no Front."
                        )
                        print(
                            f"✓ Vez inicial definida como: "
                            f"{nome_cor(board_confirmado.turn)}"
                        )
                    else:
                        candidatos = gerar_candidatos_reabertura(
                            leitura_inicial.fen_pecas
                        )
                        candidatos = [
                            board
                            for board in candidatos
                            if board.turn == lado_manual
                        ]

                        estado_provisorio = True
                        fen_base_provisoria = (
                            leitura_inicial.fen_pecas
                        )

                        print(
                            "\n⚠ O turno foi informado, mas o estado "
                            "precisa de uma confirmação visual."
                        )

            if board_confirmado is not None:
                mostrar_estado(
                    leitura_inicial,
                    board_confirmado,
                    minha_cor,
                )

                if verificar_fim_partida_confirmado(
                    sct,
                    board_confirmado,
                    minha_cor,
                    orientacao,
                    ):
                    return 0

                if board_confirmado.turn == minha_cor:
                    analisar_stockfish(
                        stockfish,
                        board_confirmado,
                    )

            print("\n========================================")
            print("ARK CHESS ATIVO")
            print("Ctrl + C para encerrar.")
            print("========================================")

            ultima_releitura = time.time()
            falhas_mesma_posicao = 0
            ultimo_fen_falhou = None
            inicio_falha_persistente = None
            memoria_status = {}

            while True:
                time.sleep(INTERVALO_LOOP)

                frame = capturar_frame(sct)

                if frame is None:
                    imprimir_status_controlado(
                        "⟳ Captura indisponível. Tentando novamente...",
                        memoria_status,
                    )
                    continue

                pixels = calcular_mudanca(
                    imagem_referencia,
                    frame,
                )

                agora = time.time()

                releitura_forcada = (
                    agora - ultima_releitura
                    >= INTERVALO_RELEITURA_FORCADA
                )

                if (
                    pixels <= LIMITE_PIXELS_MUDANCA
                    and not releitura_forcada
                ):
                    continue

                mudanca_visual_forte = (
                    pixels > LIMITE_PIXELS_MUDANCA
                )

                fen_referencia_logica = None

                # V28 ULTRA: tenta primeiro descobrir o lance somente
                # pelas casas alteradas + lista de lances legais.
                # YOLO vira fallback, não o caminho normal.
                if (
                    board_confirmado is not None
                    and mudanca_visual_forte
                ):
                    movimento_ultra, confianca_ultra = (
                        detectar_lance_visual_rapido(
                            board_confirmado,
                            imagem_referencia,
                            frame,
                            orientacao,
                        )
                    )

                    if movimento_ultra is not None:
                        board_confirmado.push(
                            movimento_ultra
                        )

                        # Captura curta pós-animação; sem YOLO.
                        time.sleep(0.018)
                        frame_pos = capturar_frame(sct)
                        imagem_referencia = (
                            frame_pos.copy()
                            if frame_pos is not None
                            else frame.copy()
                        )

                        ultima_releitura = time.time()
                        falhas_mesma_posicao = 0
                        ultimo_fen_falhou = None
                        inicio_falha_persistente = None
                        limpar_status(memoria_status)

                        print(
                            f"\n⚡ Fast-track visual "
                            f"({confianca_ultra:.1f})"
                        )

                        mostrar_estado_rapido(
                            board_confirmado,
                            minha_cor,
                            movimento_ultra,
                        )

                        if verificar_fim_partida_confirmado(
                            sct,
                            board_confirmado,
                            minha_cor,
                            orientacao,
                            ):
                            break

                        if board_confirmado.turn == minha_cor:
                            analisar_stockfish(
                                stockfish,
                                board_confirmado,
                            )

                        continue

                if board_confirmado is not None:
                    fen_referencia_logica = (
                        board_confirmado.board_fen()
                    )
                elif estado_provisorio:
                    fen_referencia_logica = (
                        fen_base_provisoria
                    )

                if mudanca_visual_forte:
                    leitura = reconhecer_consenso_agressivo(
                        sct,
                        orientacao,
                        fen_referencia_logica,
                    )
                else:
                    leitura = reconhecer_consenso(
                        sct,
                        orientacao,
                    )

                ultima_releitura = time.time()

                if leitura is None:
                    imprimir_status_controlado(
                        "⟳ Revalidando tabuleiro...",
                        memoria_status,
                    )
                    continue

                fen_novo = leitura.fen_pecas

                # Se a orientação atual não está produzindo um caminho
                # viável repetidamente, testaremos a orientação oposta
                # apenas no mecanismo de recuperação abaixo.

                if board_confirmado is not None:
                    if (
                        fen_novo
                        == board_confirmado.board_fen()
                    ):
                        # Se os pixels NÃO mudaram de verdade, atualiza a
                        # referência normalmente.
                        #
                        # Se os pixels mudaram forte mas o YOLO ainda devolveu
                        # o FEN antigo, NÃO consumimos a evidência visual.
                        # Assim a próxima iteração continua tentando reconhecer
                        # o lance em vez de "esquecer" que houve mudança.
                        if not mudanca_visual_forte:
                            imagem_referencia = (
                                leitura.imagem.copy()
                            )

                        falhas_mesma_posicao = 0
                        ultimo_fen_falhou = None
                        inicio_falha_persistente = None

                        if mudanca_visual_forte:
                            imprimir_status_controlado(
                                "⟳ Mudança detectada; confirmando peças...",
                                memoria_status,
                            )
                        continue

                    resultado = procurar_transicao_v26(
                        board_confirmado,
                        fen_novo,
                    )

                    if resultado is not None:
                        recuperado = (
                            len(resultado.movimentos) > 1
                        )

                        board_confirmado = resultado.board
                        imagem_referencia = leitura.imagem.copy()

                        falhas_mesma_posicao = 0
                        ultimo_fen_falhou = None
                        inicio_falha_persistente = None

                        ARQUIVO_TABULEIRO_ATUAL.parent.mkdir(
                            parents=True,
                            exist_ok=True,
                        )

                        cv2.imwrite(
                            str(ARQUIVO_TABULEIRO_ATUAL),
                            leitura.imagem,
                        )

                        limpar_status(
                            memoria_status
                        )

                        mostrar_estado(
                            leitura,
                            board_confirmado,
                            minha_cor,
                            movimentos=resultado.movimentos,
                            recuperado=recuperado,
                        )

                        if verificar_fim_partida_confirmado(
                            sct,
                            board_confirmado,
                            minha_cor,
                            orientacao,
                            ):
                            break

                        if board_confirmado.turn == minha_cor:
                            analisar_stockfish(
                                stockfish,
                                board_confirmado,
                            )

                        continue

                    # ------------------------------------------------
                    # V22 — TRANSIÇÃO NÃO PROVADA / PROTEÇÃO DE IDLE
                    # ------------------------------------------------
                    #
                    # IMPORTANTE:
                    # não substituímos imagem_referencia aqui.
                    #
                    # Na V21, uma leitura errada causada por animação,
                    # destaque, hover ou uma longa espera podia virar a nova
                    # referência visual. Depois de algumas leituras ruins,
                    # o ARK podia abandonar um board que estava correto.
                    #
                    # Agora a referência só muda quando:
                    #   1) o mesmo board confirmado é visto sem mudança forte; ou
                    #   2) uma transição LEGAL é realmente provada.

                    agora_falha = time.time()

                    if fen_novo == ultimo_fen_falhou:
                        falhas_mesma_posicao += 1
                    else:
                        ultimo_fen_falhou = fen_novo
                        falhas_mesma_posicao = 1
                        inicio_falha_persistente = agora_falha

                    if inicio_falha_persistente is None:
                        inicio_falha_persistente = agora_falha

                    tempo_falhando = (
                        agora_falha - inicio_falha_persistente
                    )

                    falha_realmente_persistente = (
                        falhas_mesma_posicao
                        >= FALHAS_ATE_RESSINCRONIZAR
                        and tempo_falhando
                        >= TEMPO_MINIMO_RESSINCRONIZAR
                    )

                    if not falha_realmente_persistente:
                        imprimir_status_controlado(
                            "⟳ Movimento/ruído detectado; mantendo sincronização e confirmando...",
                            memoria_status,
                        )
                        continue

                    # Pode ter ocorrido:
                    # - mais de 3 plies enquanto ARK estava fora;
                    # - troca para outra partida;
                    # - reabertura;
                    # - orientação invertida;
                    # - erro persistente de visão.
                    #
                    # Em vez de alterar o board no chute, entramos em
                    # modo provisório e exigimos um próximo lance legal.
                    orientacao_teste = (
                        "p"
                        if orientacao == "b"
                        else "b"
                    )

                    leitura_oposta = reconhecer_consenso(
                        sct,
                        orientacao_teste,
                    )

                    if (
                        leitura_oposta is not None
                        and (
                            eh_posicao_inicial(
                                leitura_oposta.fen_pecas
                            )
                            or (
                                not eh_posicao_inicial(fen_novo)
                                and estrutura_visual_plausivel(
                                    leitura_oposta.tabuleiro
                                )
                            )
                        )
                    ):
                        # Só troca orientação automaticamente se ela
                        # produzir uma posição inicial perfeita, ou se a
                        # orientação atual claramente deixou de sincronizar.
                        if eh_posicao_inicial(
                            leitura_oposta.fen_pecas
                        ):
                            orientacao = orientacao_teste
                            minha_cor = (
                                chess.WHITE
                                if orientacao == "b"
                                else chess.BLACK
                            )
                            leitura = leitura_oposta
                            fen_novo = leitura.fen_pecas

                    if eh_posicao_inicial(fen_novo):
                        board_confirmado = chess.Board()
                        candidatos = []
                        estado_provisorio = False
                        fen_base_provisoria = None

                        # A orientação determina quem está embaixo.
                        orientacao_detectada, _ = detectar_cor_em_baixo(
                            leitura.tabuleiro
                        )

                        orientacao = orientacao_detectada
                        minha_cor = (
                            chess.WHITE
                            if orientacao == "b"
                            else chess.BLACK
                        )

                        falhas_mesma_posicao = 0
                        ultimo_fen_falhou = None
                        inicio_falha_persistente = None

                        print(
                            "\n\n✓ Nova partida detectada. "
                            "Estado reiniciado com segurança."
                        )

                        mostrar_estado(
                            leitura,
                            board_confirmado,
                            minha_cor,
                        )

                        if board_confirmado.turn == minha_cor:
                            analisar_stockfish(
                                stockfish,
                                board_confirmado,
                            )

                        continue

                    # V28: em vez de congelar aguardando outro lance,
                    # usa a posição visual atual como fallback imediato.
                    # Mantém o lado esperado pela alternância do último estado.
                    lado_fallback = (
                        not board_confirmado.turn
                        if board_confirmado is not None
                        else minha_cor
                    )

                    board_fallback = criar_board_turno_manual(
                        fen_novo,
                        lado_fallback,
                    )

                    if board_fallback is not None:
                        board_confirmado = board_fallback
                        estado_provisorio = False
                        candidatos = []
                        fen_base_provisoria = None
                        imagem_referencia = leitura.imagem.copy()

                        falhas_mesma_posicao = 0
                        ultimo_fen_falhou = None
                        inicio_falha_persistente = None

                        print(
                            "\n\n⚡ Ressincronização visual imediata."
                        )
                        mostrar_estado(
                            leitura,
                            board_confirmado,
                            minha_cor,
                        )

                        if board_confirmado.turn == minha_cor:
                            analisar_stockfish(
                                stockfish,
                                board_confirmado,
                            )

                        continue

                    # Só entra no modo provisório se até o fallback visual falhar.
                    candidatos = gerar_candidatos_reabertura(fen_novo)
                    board_confirmado = None
                    estado_provisorio = True
                    fen_base_provisoria = fen_novo
                    continue

                # ====================================================
                # ESTADO PROVISÓRIO / REABERTURA
                # ====================================================

                if estado_provisorio:
                    # Se a posição lógica ainda é a mesma:
                    # - sem mudança visual: estamos só esperando;
                    # - com mudança visual forte: NÃO substitui a imagem-base,
                    #   pois isso faria o ARK perder a prova de que algo mudou.
                    if (
                        fen_base_provisoria is not None
                        and fen_novo == fen_base_provisoria
                    ):
                        if not mudanca_visual_forte:
                            imagem_referencia = (
                                leitura.imagem.copy()
                            )
                            imprimir_status_controlado(
                                "⟳ Aguardando o próximo lance real...",
                                memoria_status,
                            )
                        else:
                            imprimir_status_controlado(
                                "⟳ Movimento visual detectado; tentando reconhecer...",
                                memoria_status,
                            )

                        continue

                    # Só agora, com um FEN realmente novo, a nova imagem vira
                    # referência.
                    imagem_referencia = (
                        leitura.imagem.copy()
                    )

                    # Agora sim houve mudança de peças.
                    resultado, candidatos_novos = (
                        sincronizar_candidatos(
                            candidatos,
                            fen_novo,
                        )
                    )

                    if resultado is not None:
                        board_confirmado = (
                            resultado.board
                        )
                        candidatos = []
                        estado_provisorio = False
                        fen_base_provisoria = None

                        limpar_status(
                            memoria_status
                        )

                        print(
                            "\n\n✓ Turno e estado sincronizados automaticamente."
                        )

                        mostrar_estado(
                            leitura,
                            board_confirmado,
                            minha_cor,
                            movimentos=resultado.movimentos,
                        )

                        if verificar_fim_partida_confirmado(
                            sct,
                            board_confirmado,
                            minha_cor,
                            orientacao,
                            ):
                            break

                        if (
                            board_confirmado.turn
                            == minha_cor
                        ):
                            analisar_stockfish(
                                stockfish,
                                board_confirmado,
                            )

                        continue

                    if candidatos_novos:
                        candidatos = (
                            candidatos_novos
                        )

                        # A mudança foi parcialmente útil, então ela vira
                        # a nova base visual para o próximo lance.
                        fen_base_provisoria = (
                            fen_novo
                        )

                        imprimir_status_controlado(
                            "⟳ Lance visto; refinando sincronização...",
                            memoria_status,
                        )
                        continue

                    # Nenhum candidato explicou o novo tabuleiro.
                    if eh_posicao_inicial(
                        fen_novo
                    ):
                        board_confirmado = (
                            chess.Board()
                        )
                        candidatos = []
                        estado_provisorio = False
                        fen_base_provisoria = None

                        orientacao, _ = (
                            detectar_cor_em_baixo(
                                leitura.tabuleiro
                            )
                        )

                        minha_cor = (
                            chess.WHITE
                            if orientacao == "b"
                            else chess.BLACK
                        )

                        print(
                            "\n\n✓ Nova partida inicial detectada."
                        )

                        mostrar_estado(
                            leitura,
                            board_confirmado,
                            minha_cor,
                        )

                        if (
                            board_confirmado.turn
                            == minha_cor
                        ):
                            analisar_stockfish(
                                stockfish,
                                board_confirmado,
                            )

                    else:
                        # Em vez de ficar usando candidatos velhos
                        # eternamente, transforma a posição visual atual
                        # na nova base provisória.
                        candidatos = (
                            gerar_candidatos_reabertura(
                                fen_novo
                            )
                        )

                        fen_base_provisoria = (
                            fen_novo
                        )

                        imprimir_status_controlado(
                            "⟳ Nova base adquirida; aguardando lance real...",
                            memoria_status,
                        )

    except KeyboardInterrupt:
        print("\n\n========================================")
        print("ARK Chess encerrado pelo usuário.")
        print("========================================")
        return 0

    except Exception as exc:
        logger.exception(
            "Erro inesperado no loop principal: %s",
            exc,
        )

        print("\n\n❌ O ARK encontrou um erro inesperado.")
        print(
            f"Detalhes foram salvos em: {ARQUIVO_LOG}"
        )
        print(
            f"Erro: {type(exc).__name__}: {exc}"
        )

        return 1

    finally:
        stockfish.encerrar()
        print("\nStockfish encerrado.")


if __name__ == "__main__":
    sys.exit(main())
