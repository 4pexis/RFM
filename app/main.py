"""Roblox Farm Manager — ponto de entrada.

Uso:
    python -m app.main              interface desktop
    python -m app.main --headless   apenas serviços (migrações, monitoramento, backups)
"""
from __future__ import annotations

import argparse
import logging
import sys
import time


def run_gui() -> int:
    from PySide6.QtWidgets import QApplication, QMessageBox

    from app.core.bootstrap import bootstrap
    from app.core.config import APP_NAME
    from app.ui.main_window import MainWindow, app_icon
    from app.ui.theme import STYLESHEET

    qt_app = QApplication(sys.argv)
    qt_app.setApplicationName(APP_NAME)
    qt_app.setStyle("Fusion")
    qt_app.setStyleSheet(STYLESHEET)
    qt_app.setWindowIcon(app_icon())
    try:
        ctx = bootstrap()
    except Exception as exc:
        logging.getLogger(__name__).exception("Falha na inicialização")
        QMessageBox.critical(None, APP_NAME, f"Não foi possível iniciar o aplicativo:\n\n{exc}")
        return 1

    def on_uncaught(exc_type, exc, traceback) -> None:
        logging.getLogger("rfm").error("Erro não tratado", exc_info=(exc_type, exc, traceback))
        QMessageBox.critical(None, APP_NAME, f"Erro inesperado:\n{exc}\n\nDetalhes no arquivo de log.")

    sys.excepthook = on_uncaught
    window = MainWindow(ctx)
    ctx.start_workers()
    window.show()
    return qt_app.exec()


def run_headless() -> int:
    from app.core.bootstrap import bootstrap

    ctx = bootstrap()
    ctx.start_workers()
    logging.getLogger(__name__).info("Modo headless em execução (Ctrl+C para sair)")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        ctx.shutdown()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Roblox Farm Manager")
    parser.add_argument("--headless", action="store_true", help="executa apenas os serviços, sem interface")
    args = parser.parse_args()
    return run_headless() if args.headless else run_gui()


if __name__ == "__main__":
    sys.exit(main())
