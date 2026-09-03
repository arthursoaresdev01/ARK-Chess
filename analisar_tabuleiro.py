# pyrefly: ignore [missing-import]
from ultralytics import YOLO

import os


# ============================================================
# CONFIGURAÇÕES
# ============================================================

CAMINHO_MODELO = "runs/classify/train-3/weights/best.pt"
PASTA_CASAS = "casas"

# Tamanho usado no treinamento/classificação das casas.
IMGSZ = 96

# Proteção contra classificações "fantasmas".
#
# Se uma casa já tinha uma classe estável e, de repente, o YOLO
# disser que virou uma peça muito importante com confiança/margem
# insuficientes, mantemos temporariamente a leitura anterior.
#
# Isso é especialmente útil contra falsos positivos de dama/rei.
CONFIANCA_MIN_MUDANCA_CRITICA = 0.90
MARGEM_MIN_MUDANCA_CRITICA = 0.18

CLASSES_CRITICAS = {
    "rainha_branca",
    "rainha_preta",
    "rei_branco",
    "rei_preto",
}

# Memória simples entre uma leitura e outra.
_ULTIMO_TABULEIRO = None


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
# AUXILIARES
# ============================================================

def _listar_casas():
    """
    Retorna as 64 casas SEMPRE na ordem:
    (0,0), (0,1), ... (7,7)

    Também valida todos os arquivos antes de iniciar a inferência.
    """
    casas = []

    for linha in range(8):
        for coluna in range(8):
            nome_arquivo = f"casa_{linha}_{coluna}.png"
            caminho = os.path.join(
                PASTA_CASAS,
                nome_arquivo
            )

            if not os.path.exists(caminho):
                raise FileNotFoundError(
                    f"Casa não encontrada: {caminho}"
                )

            casas.append(
                (
                    linha,
                    coluna,
                    caminho
                )
            )

    return casas


def _top2(resultado):
    """
    Retorna:
    classe_top1, confianca_top1, confianca_top2

    A diferença top1 - top2 ajuda a detectar classificações
    duvidosas mesmo quando a confiança absoluta parece razoável.
    """
    probs = resultado.probs

    indice_top1 = int(probs.top1)
    confianca_top1 = float(probs.top1conf)

    classe_top1 = resultado.names[
        indice_top1
    ]

    confianca_top2 = 0.0

    try:
        top5 = probs.top5
        top5conf = probs.top5conf

        if len(top5) >= 2:
            confianca_top2 = float(
                top5conf[1]
            )
    except Exception:
        pass

    return (
        classe_top1,
        confianca_top1,
        confianca_top2,
    )


def _proteger_mudanca_critica(
    posicao,
    classe_nova,
    confianca_nova,
    confianca_top2,
):
    """
    Evita que uma leitura isolada invente uma dama/rei em uma casa.

    Não bloqueia a primeira leitura da partida, porque ainda não há
    estado anterior para comparar.
    """
    global _ULTIMO_TABULEIRO

    if _ULTIMO_TABULEIRO is None:
        return classe_nova, confianca_nova

    anterior = _ULTIMO_TABULEIRO.get(
        posicao
    )

    if anterior is None:
        return classe_nova, confianca_nova

    classe_anterior, confianca_anterior = anterior

    if classe_nova == classe_anterior:
        return classe_nova, confianca_nova

    if classe_nova not in CLASSES_CRITICAS:
        return classe_nova, confianca_nova

    margem = (
        confianca_nova - confianca_top2
    )

    mudanca_segura = (
        confianca_nova
        >= CONFIANCA_MIN_MUDANCA_CRITICA
        and margem
        >= MARGEM_MIN_MUDANCA_CRITICA
    )

    if mudanca_segura:
        return classe_nova, confianca_nova

    # Mantém a classe anterior, mas derruba um pouco a confiança
    # para sinalizar que houve conflito na leitura.
    confianca_protegida = min(
        float(confianca_anterior),
        0.60,
    )

    return (
        classe_anterior,
        confianca_protegida,
    )


# ============================================================
# ANALISA AS 64 CASAS EM LOTE
# ============================================================

def analisar_tabuleiro():
    """
    VERSÃO OTIMIZADA

    Antes:
        64 chamadas separadas de modelo.predict()

    Agora:
        1 chamada com as 64 imagens em lote.

    Isso reduz bastante o overhead de Python/Ultralytics,
    principalmente na inicialização do ARK.
    """
    global _ULTIMO_TABULEIRO

    casas = _listar_casas()

    caminhos = [
        caminho
        for _, _, caminho in casas
    ]

    resultados = modelo.predict(
        source=caminhos,
        imgsz=IMGSZ,
        verbose=False,
    )

    if len(resultados) != 64:
        raise RuntimeError(
            "YOLO retornou quantidade inesperada "
            f"de resultados: {len(resultados)}"
        )

    tabuleiro = {}

    for (
        (linha, coluna, _),
        resultado,
    ) in zip(casas, resultados):

        (
            classe,
            confianca,
            confianca_top2,
        ) = _top2(resultado)

        posicao = (
            linha,
            coluna,
        )

        (
            classe,
            confianca,
        ) = _proteger_mudanca_critica(
            posicao,
            classe,
            confianca,
            confianca_top2,
        )

        tabuleiro[posicao] = (
            classe,
            confianca,
        )

    _ULTIMO_TABULEIRO = (
        tabuleiro.copy()
    )

    return tabuleiro



# ============================================================
# FAST-TRACK 2.0 — CLASSIFICA SOMENTE CASAS ESPECÍFICAS
# ============================================================

def analisar_casas_imagem(imagem, posicoes):
    """
    Classifica apenas as casas solicitadas diretamente do frame 816x816.

    Retorna:
        {(linha, coluna): (classe_top1, conf_top1, conf_top2)}

    Não altera a memória global do tabuleiro. É usada apenas como
    confirmação rápida de um lance já candidato pela diferença visual.
    """
    if imagem is None:
        return {}

    altura, largura = imagem.shape[:2]
    if altura < 8 or largura < 8:
        return {}

    posicoes = sorted(set(posicoes))
    if not posicoes:
        return {}

    ys = [int(round(i * altura / 8)) for i in range(9)]
    xs = [int(round(i * largura / 8)) for i in range(9)]

    fontes = []
    validas = []

    for linha, coluna in posicoes:
        if not (0 <= linha < 8 and 0 <= coluna < 8):
            continue

        recorte = imagem[
            ys[linha]:ys[linha + 1],
            xs[coluna]:xs[coluna + 1],
        ]

        if recorte.size == 0:
            continue

        fontes.append(recorte)
        validas.append((linha, coluna))

    if not fontes:
        return {}

    resultados = modelo.predict(
        source=fontes,
        imgsz=IMGSZ,
        verbose=False,
        batch=len(fontes),
    )

    if len(resultados) != len(validas):
        return {}

    saida = {}
    for posicao, resultado in zip(validas, resultados):
        classe, conf1, conf2 = _top2(resultado)
        saida[posicao] = (classe, conf1, conf2)

    return saida

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
