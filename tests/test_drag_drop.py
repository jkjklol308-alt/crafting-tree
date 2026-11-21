"""Pure-python tests for the sidebar -> graph drag-and-drop payload helpers."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.util import ITEM_MIME_TYPE, parse_mime_item_ids


def test_parse_single():
    assert parse_mime_item_ids('42') == [42]


def test_parse_multiple_with_whitespace():
    assert parse_mime_item_ids(' 7 , 8 , 9 ') == [7, 8, 9]


def test_parse_ignores_junk_and_empty():
    assert parse_mime_item_ids('') == []
    assert parse_mime_item_ids('abc,44,') == [44]
    assert parse_mime_item_ids(',') == []


def test_mime_type_is_custom_and_stable():
    assert ITEM_MIME_TYPE == 'application/x-crafting-tree-item'


if __name__ == '__main__':
    test_parse_single()
    test_parse_multiple_with_whitespace()
    test_parse_ignores_junk_and_empty()
    test_mime_type_is_custom_and_stable()
    print('ALL DRAG-DROP HELPER TESTS PASSED')
