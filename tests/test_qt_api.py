"""Static regression guard for the Qt-API entry points that previously
crashed on first run (learned from the very first real GUI launch).

These are pure-source checks: no Qt import is required.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCES = list((ROOT / 'src').glob('*.py')) + [ROOT / 'app.py']

BAD_PATTERNS = [
    # QGraphicsTextItem in Qt 6 has setPlainText, not setText (in graph.py,
    # every setText user is a QGraphicsTextItem-derived item)
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
    # QGraphicsTextItem has no setText() in Qt 6 — in graph.py, every
    # .setText( call belongs to a QGraphicsTextItem-derived item and must be
    # setPlainText().
    graph_src = ROOT / 'src' / 'graph.py'
    for lineno, line in enumerate(graph_src.read_text(encoding='utf-8').splitlines(), 1):
        if re.search(r'\.setText\(', line):
            problems.append(f'{graph_src.relative_to(ROOT)}:{lineno}: {line.strip()}')
    assert not problems, '\n'.join(problems)

def test_wheel_event_uses_position():
    """Qt 6 QWheelEvent is not a QMouseEvent: it has position(), not pos()."""
    graph_src = ROOT / 'src' / 'graph.py'
    text = graph_src.read_text(encoding='utf-8')
    start = text.index('def wheelEvent')
    end = text.index('\n    def ', start + 10)
    body = text[start:end]
    assert '.pos()' not in body, (
        'QWheelEvent has no pos() in Qt 6 — use position() (see contextMenuEvent, which does use pos() on QContextMenuEvent)\n' + body)
    assert '.position()' in body, 'wheelEvent should use event.position() in Qt 6'


def test_set_model_accepts_lists_and_dicts():
    """set_model must not blindly dict()() a list (the main window passes lists)."""
    graph_src = ROOT / 'src' / 'graph.py'
    text = graph_src.read_text(encoding='utf-8')
    start = text.index('def set_model')
    end = text.index('\n    def ', start + 10)
    body = text[start:end]
    # Unconditional dict(items) / dict(processes) on a plain list raises
    # TypeError. set_model must only call dict() inside the isinstance(...)
    # branch (deeper indent), with an id-keyed comprehension otherwise.
    assert '\n        self.items = dict(items)' not in body
    assert '\n        self.processes = dict(processes)' not in body
    assert 'isinstance(items' in body and 'isinstance(processes' in body


def test_sidebar_has_no_duplicate_create_buttons():
    """+ Item/+ Recipe buttons duplicated the top bar; they are removed."""
    sidebar_src = ROOT / 'src' / 'sidebar.py'
    text = sidebar_src.read_text(encoding='utf-8')
    assert '+ Item' not in text and '+ Recipe' not in text
    assert 'new_item_requested' not in text
    assert 'new_recipe_requested' not in text


if __name__ == '__main__':
    test_no_invalid_qt_api_usage()
    test_wheel_event_uses_position()
    test_set_model_accepts_lists_and_dicts()
    test_sidebar_has_no_duplicate_create_buttons()
    print('ALL QT API GUARD TESTS PASSED')
