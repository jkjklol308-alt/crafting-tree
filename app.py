#!/usr/bin/env python
"""Crafting Tree — Create Mod Factory Manager.

Standalone desktop application for managing, visualising and calculating
production chains from the Minecraft Create Mod.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main():
    try:
        from PySide6.QtWidgets import QApplication
        from PySide6.QtGui import QIcon
        from src.theme import QSS
        from src.main_window import MainWindow
    except ImportError as e:
        print('Could not import PySide6. Please install dependencies:')
        print('    pip install -r requirements.txt')
        print(f'(error: {e})')
        sys.exit(1)

    app = QApplication(sys.argv)
    app.setApplicationName('Crafting Tree')
    app.setOrganizationName('Crafting Tree')
    app.setApplicationVersion('1.0.0')
    app.setStyleSheet(QSS)

    try:
        window = MainWindow()
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f'Failed to start application: {e}')
        sys.exit(2)

    window.show()
    return app.exec()


if __name__ == '__main__':
    sys.exit(main())
