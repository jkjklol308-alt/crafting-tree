"""Static regression guard for the Qt-API entry points that previously
crashed on first run (learned from the very first real GUI launch).

These are pure-source checks: no Qt import is required.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCES = list((ROOT / 'src').glob('*.py')) + [ROOT / 'app.py']

BAD_PATTERNS = [
    # Qt 6 has no setRubberBandSelectionVisible on QGraphicsView
    r'setRubberBandSelectionVisible',
    # Qt 6 itemAt does not accept an ItemSendsScenePositionToParent hint
    r'ItemSendsScenePositionToParent',
    # unscoped message-box enum members are not a PySide6 API
    r'QMessageBox\.Yes(?!\.StandardButton)',
    r'QMessageBox\.No(?!\.StandardButton)',
    r'QMessageBox\.Ok(?!\.StandardButton)',
    r'QMessageBox\.Cancel(?!\.StandardButton)',
    # itemAt on a QGraphicsScene/QGraphicsView — we use _node_at instead
    r'(scene|view|self)\.scene\(\)\.itemAt\(',
    r'self\.itemAt\(',
]

def test_no_invalid_qt_api_usage():
    problems = []
    for src in SOURCES:
        text = src.read_text(encoding='utf-8')
        for pat in BAD_PATTERNS:
            for lineno, line in enumerate(text.splitlines(), 1):
                if re.search(pat, line):
                    problems.append(f'{src.relative_to(ROOT)}:{lineno}: {line.strip()}')
    assert not problems, '\n'.join(problems)

if __name__ == '__main__':
    test_no_invalid_qt_api_usage()
    print('ALL QT API GUARD TESTS PASSED')
