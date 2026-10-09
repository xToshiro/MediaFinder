import sys
import os

# Suprimir logs espúrios do backend multimídia FFmpeg do Qt 6
os.environ.setdefault("QT_LOGGING_RULES", "qt.multimedia*=false;qt.multimedia.ffmpeg*=false;*.warning=false")
os.environ.setdefault("FFREPORT", "level=quiet")

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt, qInstallMessageHandler, QtMsgType
from PySide6.QtGui import QIcon, QFont

def qt_message_filter(mode, context, message):
    """Filtra mensagens e avisos repetitivos do backend QFFmpeg/QtMultimedia."""
    if "AV_NOPTS_VALUE" in message or "QFFmpeg" in message:
        return
    if mode == QtMsgType.QtWarningMsg and "multimedia" in message.lower():
        return
    if mode == QtMsgType.QtFatalMsg:
        sys.stderr.write(f"FATAL: {message}\n")
    elif mode == QtMsgType.QtCriticalMsg:
        sys.stderr.write(f"CRITICAL: {message}\n")

from app.__version__ import __version__, __app_name__
from app.ui.main_window import MainWindow
from app.ui.styles import DARK_THEME_QSS

def main():
    qInstallMessageHandler(qt_message_filter)

    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName(__app_name__)
    app.setApplicationDisplayName(f"{__app_name__} v{__version__} — Buscador Rápido de Mídias")

    icon_path = os.path.join(os.path.dirname(__file__), "assets", "icon.png")
    if os.path.exists(icon_path):
        app_icon = QIcon(icon_path)
        app.setWindowIcon(app_icon)

    font = QFont("Segoe UI", 10)
    app.setFont(font)
    app.setStyleSheet(DARK_THEME_QSS)

    window = MainWindow()
    if os.path.exists(icon_path):
        window.setWindowIcon(QIcon(icon_path))
    window.show()

    sys.exit(app.exec())

if __name__ == "__main__":
    main()
