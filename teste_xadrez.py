# pyrefly: ignore [missing-import]
import chess
# pyrefly: ignore [missing-import]
import chess.engine

tabuleiro = chess.Board("rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2")

motor = chess.engine.SimpleEngine.popen_uci(
    r"stockfish-windows-x86-64-avx2\stockfish\stockfish-windows-x86-64-avx2.exe"
)

resultado = motor.play(
    tabuleiro,
    chess.engine.Limit(depth=15)
)

print("Melhor jogada:", resultado.move)

motor.quit()