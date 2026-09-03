from __future__ import annotations

from dataclasses import dataclass
import ctypes
import os

# pyrefly: ignore [missing-import]
from PySide6.QtCore import QPointF, QRect, Qt
# pyrefly: ignore [missing-import]
from PySide6.QtGui import QColor, QPainter, QPen, QPolygonF
# pyrefly: ignore [missing-import]
from PySide6.QtWidgets import QWidget


@dataclass
class BoardGeometry:
    left: int = 390
    top: int = 147
    size: int = 816

    @property
    def square(self) -> float:
        return self.size / 8.0


class ArkOverlay(QWidget):
    """
    Overlay transparente e click-through para o ARK Chess.
    Recebe uma jogada como e2 -> e4 e desenha a seta no tabuleiro.
    """

    def __init__(self, geometry: BoardGeometry | None = None, parent=None):
        super().__init__(parent)

        self.board = geometry or BoardGeometry()
        self.from_square: str | None = None
        self.to_square: str | None = None
        self.white_at_bottom = True

        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
            | Qt.WindowTransparentForInput
        )

        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WA_NativeWindow, True)

        # Windows 10 2004+: impede que o overlay entre na captura do MSS.
        # Assim a seta não vira uma "jogada fantasma" para a própria visão.
        self._capture_exclusion_applied = False

        self._apply_geometry()
        self.hide()

    def _exclude_from_capture(self):
        if self._capture_exclusion_applied:
            return

        if os.name != "nt":
            return

        try:
            hwnd = int(self.winId())
            WDA_EXCLUDEFROMCAPTURE = 0x00000011
            ok = ctypes.windll.user32.SetWindowDisplayAffinity(
                hwnd,
                WDA_EXCLUDEFROMCAPTURE,
            )
            self._capture_exclusion_applied = bool(ok)
        except Exception:
            self._capture_exclusion_applied = False

    def showEvent(self, event):
        super().showEvent(event)
        self._exclude_from_capture()

    def _apply_geometry(self):
        self.setGeometry(
            QRect(
                int(self.board.left),
                int(self.board.top),
                int(self.board.size),
                int(self.board.size),
            )
        )

    def set_board_geometry(self, left: int, top: int, size: int):
        self.board = BoardGeometry(
            left=int(left),
            top=int(top),
            size=int(size),
        )
        self._apply_geometry()
        self.update()

    def set_orientation(self, white_at_bottom: bool):
        self.white_at_bottom = bool(white_at_bottom)
        self.update()

    def set_move(self, from_square: str, to_square: str):
        self.from_square = from_square.lower()
        self.to_square = to_square.lower()
        self.show()
        self.raise_()
        self.update()

    def clear_move(self):
        self.from_square = None
        self.to_square = None
        self.hide()
        self.update()

    def _indices(self, square_name: str) -> tuple[int, int]:
        file_idx = ord(square_name[0]) - ord("a")
        rank_idx = int(square_name[1]) - 1

        if self.white_at_bottom:
            col = file_idx
            row = 7 - rank_idx
        else:
            col = 7 - file_idx
            row = rank_idx

        return row, col

    def square_center(self, square_name: str) -> QPointF:
        row, col = self._indices(square_name)
        s = self.board.square
        return QPointF((col + 0.5) * s, (row + 0.5) * s)

    def square_rect(self, square_name: str) -> QRect:
        row, col = self._indices(square_name)
        s = self.board.square
        margin = int(s * 0.13)

        return QRect(
            int(col * s) + margin,
            int(row * s) + margin,
            int(s) - margin * 2,
            int(s) - margin * 2,
        )

    def paintEvent(self, event):
        if not self.from_square or not self.to_square:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        start = self.square_center(self.from_square)
        end = self.square_center(self.to_square)

        # Casas de origem e destino.
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(0, 220, 255, 70))
        painter.drawRoundedRect(self.square_rect(self.from_square), 14, 14)

        painter.setBrush(QColor(0, 255, 150, 95))
        painter.drawRoundedRect(self.square_rect(self.to_square), 14, 14)

        # Corpo da seta.
        dx = end.x() - start.x()
        dy = end.y() - start.y()
        length = max((dx * dx + dy * dy) ** 0.5, 1.0)
        ux = dx / length
        uy = dy / length

        s = self.board.square
        head_len = s * 0.34
        head_w = s * 0.23

        line_end = QPointF(
            end.x() - ux * head_len * 0.60,
            end.y() - uy * head_len * 0.60,
        )

        painter.setPen(
            QPen(
                QColor(0, 255, 180, 210),
                s * 0.12,
                Qt.SolidLine,
                Qt.RoundCap,
                Qt.RoundJoin,
            )
        )
        painter.drawLine(start, line_end)

        # Cabeça da seta.
        perp_x = -uy
        perp_y = ux
        base_x = end.x() - ux * head_len
        base_y = end.y() - uy * head_len

        p1 = end
        p2 = QPointF(base_x + perp_x * head_w, base_y + perp_y * head_w)
        p3 = QPointF(base_x - perp_x * head_w, base_y - perp_y * head_w)

        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(0, 255, 180, 220))
        painter.drawPolygon(QPolygonF([p1, p2, p3]))
