import re
import sys
from pathlib import Path

# pyrefly: ignore [missing-import]
from PySide6.QtCore import QProcess, Qt
# pyrefly: ignore [missing-import]
from PySide6.QtGui import QFont, QGuiApplication
# pyrefly: ignore [missing-import]
from PySide6.QtWidgets import (
    QApplication, QComboBox, QFrame, QHBoxLayout, QLabel,
    QMainWindow, QPushButton, QTextEdit, QVBoxLayout, QWidget
)

BACKEND = Path(__file__).with_name("testar_captura_v26.py")


class ArkCard(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("card")


class ArkChessWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.processo = None
        self.esperando_melhor_jogada = False
        self.expandido = False

        # Mantém o ARK visível quando você clica no Chess.com.
        self.setWindowFlag(Qt.WindowStaysOnTopHint, True)

        self.setWindowTitle("ARK Chess")
        self.resize(500, 720)
        self.setMinimumWidth(430)
        self.setMinimumHeight(560)

        self.aplicar_estilo()
        self.montar_interface()

        # Começa no lado direito da tela para não cobrir o board.
        self.auto_posicionar()

    def aplicar_estilo(self):
        self.setStyleSheet("""
            QMainWindow { background: #0d1117; }
            QWidget {
                color: #e6edf3;
                font-family: "Segoe UI";
                font-size: 13px;
            }
            #sidebar {
                background: #111827;
                border-bottom: 1px solid #1f2937;
            }
            #card {
                background: #161b22;
                border: 1px solid #263241;
                border-radius: 14px;
            }
            QPushButton {
                background: #1f6feb;
                border: none;
                border-radius: 9px;
                padding: 10px 14px;
                font-weight: 600;
            }
            QPushButton:hover { background: #388bfd; }
            QPushButton#secondary {
                background: transparent;
                border: 1px solid #334155;
            }
            QPushButton#secondary:hover { background: #1e293b; }
            QLabel#muted { color: #8b949e; }
            QLabel#move {
                font-size: 24px;
                font-weight: 700;
            }
            QLabel#online {
                color: #3fb950;
                font-weight: 700;
            }
            QLabel#offline {
                color: #f85149;
                font-weight: 700;
            }
            QTextEdit {
                background: #0d1117;
                border: 1px solid #263241;
                border-radius: 10px;
                padding: 8px;
                font-family: Consolas;
                font-size: 12px;
            }
            QComboBox {
                background: #0d1117;
                border: 1px solid #334155;
                border-radius: 8px;
                padding: 8px;
            }
        """)

    def montar_interface(self):
        root = QWidget()
        self.setCentralWidget(root)

        body = QVBoxLayout(root)
        body.setContentsMargins(14, 14, 14, 14)
        body.setSpacing(12)

        topo = QFrame()
        topo.setObjectName("sidebar")
        tl = QHBoxLayout(topo)
        tl.setContentsMargins(14, 10, 14, 10)

        logo = QLabel("♟ ARK CHESS")
        logo.setFont(QFont("Segoe UI", 18, QFont.Bold))
        tl.addWidget(logo)

        tl.addStretch()

        self.status_sidebar = QLabel("● OFFLINE")
        self.status_sidebar.setObjectName("offline")
        tl.addWidget(self.status_sidebar)

        body.addWidget(topo)

        engine = ArkCard()
        el = QVBoxLayout(engine)
        el.setContentsMargins(16, 14, 16, 14)

        linha_titulo = QHBoxLayout()
        titulo = QLabel("ARK Engine")
        titulo.setFont(QFont("Segoe UI", 15, QFont.Bold))
        linha_titulo.addWidget(titulo)
        linha_titulo.addStretch()

        self.btn_expandir = QPushButton("▣")
        self.btn_expandir.setObjectName("secondary")
        self.btn_expandir.setFixedWidth(42)
        self.btn_expandir.clicked.connect(self.alternar_tamanho)
        linha_titulo.addWidget(self.btn_expandir)

        el.addLayout(linha_titulo)

        self.status_engine = QLabel("Aguardando inicialização")
        self.status_engine.setObjectName("muted")
        el.addWidget(self.status_engine)

        turno_txt = QLabel("Ao abrir uma partida já em andamento:")
        turno_txt.setObjectName("muted")
        el.addWidget(turno_txt)

        self.combo_turno = QComboBox()
        self.combo_turno.addItem("Automático", "auto")
        self.combo_turno.addItem("Minha vez agora", "minha")
        self.combo_turno.addItem("Vez do bot agora", "bot")
        el.addWidget(self.combo_turno)

        self.btn_start = QPushButton("▶  INICIAR ARK")
        self.btn_start.clicked.connect(self.alternar_ark)
        el.addWidget(self.btn_start)

        body.addWidget(engine)

        partida = ArkCard()
        pl = QVBoxLayout(partida)
        pl.setContentsMargins(16, 14, 16, 14)

        pt = QLabel("Partida")
        pt.setFont(QFont("Segoe UI", 15, QFont.Bold))
        pl.addWidget(pt)

        self.lbl_cor = QLabel("Sua cor: —")
        self.lbl_turno = QLabel("Vez: —")
        self.lbl_estado = QLabel("Estado: aguardando")
        self.lbl_estado.setObjectName("muted")

        pl.addWidget(self.lbl_cor)
        pl.addWidget(self.lbl_turno)
        pl.addWidget(self.lbl_estado)

        mt = QLabel("Melhor jogada")
        mt.setObjectName("muted")
        pl.addWidget(mt)

        self.lbl_jogada = QLabel("—")
        self.lbl_jogada.setObjectName("move")
        self.lbl_jogada.setWordWrap(True)
        pl.addWidget(self.lbl_jogada)

        body.addWidget(partida)

        self.log_card = ArkCard()
        ll = QVBoxLayout(self.log_card)
        ll.setContentsMargins(16, 14, 16, 14)

        lt = QLabel("Log")
        lt.setFont(QFont("Segoe UI", 14, QFont.Bold))
        ll.addWidget(lt)

        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.append("ARK Front V3 pronto.")
        self.log.append("Backend esperado: testar_captura_v26.py")
        ll.addWidget(self.log)

        body.addWidget(self.log_card, 1)

    def auto_posicionar(self):
        tela = QGuiApplication.primaryScreen()
        if tela is None:
            return

        area = tela.availableGeometry()

        margem = 12
        x = area.x() + area.width() - self.width() - margem
        y = area.y() + margem

        self.move(max(area.x(), x), y)

    def alternar_tamanho(self):
        self.expandido = not self.expandido

        if self.expandido:
            self.resize(620, 820)
            self.btn_expandir.setText("▤")
        else:
            self.resize(500, 720)
            self.btn_expandir.setText("▣")

        self.auto_posicionar()

    def mudar_status(self, online):
        if online:
            self.status_sidebar.setText("● ONLINE")
            self.status_sidebar.setObjectName("online")
        else:
            self.status_sidebar.setText("● OFFLINE")
            self.status_sidebar.setObjectName("offline")

        self.status_sidebar.style().unpolish(self.status_sidebar)
        self.status_sidebar.style().polish(self.status_sidebar)

    def alternar_ark(self):
        if self.processo and self.processo.state() != QProcess.NotRunning:
            self.parar_ark()
        else:
            self.iniciar_ark()

    def iniciar_ark(self):
        if not BACKEND.exists():
            self.log.append(f"ERRO: não encontrei {BACKEND.name}")
            self.status_engine.setText("Backend V26 não encontrado")
            return

        self.lbl_jogada.setText("—")
        self.lbl_cor.setText("Sua cor: —")
        self.lbl_turno.setText("Vez: —")
        self.lbl_estado.setText("Estado: iniciando...")

        opcao_turno = self.combo_turno.currentData()

        self.processo = QProcess(self)
        self.processo.setWorkingDirectory(str(BACKEND.parent))
        self.processo.setProcessChannelMode(QProcess.MergedChannels)
        self.processo.readyReadStandardOutput.connect(self.ler_saida)
        self.processo.finished.connect(self.backend_finalizado)

        argumentos = [
            "-u",
            str(BACKEND),
            "--turno-inicial",
            str(opcao_turno),
        ]

        self.processo.start(sys.executable, argumentos)

        self.combo_turno.setEnabled(False)
        self.btn_start.setText("■  PARAR ARK")
        self.status_engine.setText("Iniciando backend V26...")
        self.mudar_status(True)
        self.log.append(
            f"Iniciando ARK V26 • turno inicial: {opcao_turno}"
        )

    def parar_ark(self):
        if not self.processo:
            return

        self.status_engine.setText("Encerrando...")
        self.processo.terminate()

        if not self.processo.waitForFinished(1500):
            self.processo.kill()

    def backend_finalizado(self, exit_code, _status):
        self.btn_start.setText("▶  INICIAR ARK")
        self.combo_turno.setEnabled(True)
        self.status_engine.setText(f"ARK parado • código {exit_code}")
        self.lbl_estado.setText("Estado: parado")
        self.mudar_status(False)
        self.log.append("ARK encerrado.")

    def ler_saida(self):
        if not self.processo:
            return

        texto = bytes(self.processo.readAllStandardOutput()).decode(
            "utf-8", errors="replace"
        )

        for linha in texto.splitlines():
            linha = linha.strip()
            if linha:
                self.processar_evento(linha)

    def processar_evento(self, linha):
        # Evita despejar linhas de desenho do tabuleiro no painel.
        if not re.fullmatch(r"[rnbqkpRNBQKP\.\s]+", linha):
            self.log.append(linha)

        if "Sua cor:" in linha:
            m = re.search(r"Sua cor:\s*(Brancas|Pretas)", linha, re.I)
            if m:
                self.lbl_cor.setText(f"Sua cor: {m.group(1)}")

        if linha.startswith("Vez:"):
            turno = linha.split(":", 1)[1].strip()
            self.lbl_turno.setText(f"Vez: {turno}")

        if "SUA VEZ" in linha:
            self.lbl_estado.setText("Estado: sua vez")
        elif "Aguardando jogada do adversário" in linha:
            self.lbl_estado.setText("Estado: aguardando bot")
        elif "ARK CHESS ATIVO" in linha:
            self.status_engine.setText("Sistema ativo")
            self.lbl_estado.setText("Estado: monitorando")
        elif "Procurando posição válida" in linha:
            self.status_engine.setText("Procurando tabuleiro...")
        elif "Tabuleiro reconhecido e confirmado" in linha:
            self.status_engine.setText("Tabuleiro reconhecido")
        elif "SINCRONIZAÇÃO RECUPERADA" in linha:
            self.lbl_estado.setText("Estado: sincronização recuperada")
        elif "Turno e estado sincronizados" in linha:
            self.lbl_estado.setText("Estado: sincronizado")
        elif "recuperou roque visualmente" in linha.lower():
            self.lbl_estado.setText("Estado: roque reconhecido")

        if "MELHOR JOGADA:" in linha:
            self.esperando_melhor_jogada = True
            return

        if self.esperando_melhor_jogada:
            if re.search(r"\b[a-h][1-8]\s*->\s*[a-h][1-8]\b", linha):
                self.lbl_jogada.setText(linha.replace("->", "→"))
                self.esperando_melhor_jogada = False

    def closeEvent(self, event):
        if self.processo and self.processo.state() != QProcess.NotRunning:
            self.processo.kill()
            self.processo.waitForFinished(1000)

        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ArkChessWindow()
    window.show()
    sys.exit(app.exec())
