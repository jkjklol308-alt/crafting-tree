"""Platform/path helpers and small shared utilities."""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path
from datetime import datetime

# MIME type used when dragging an item row from the sidebar into the graph.
# The payload is a comma-separated list of item ids (plain text).
ITEM_MIME_TYPE = 'application/x-crafting-tree-item'


def parse_mime_item_ids(text):
    """Parse a comma-separated item-id payload (from a drag source).

    Tolerates whitespace and ignores anything that is not a plain integer.
    """
    ids = []
    if not text:
        return ids
    for token in text.split(','):
        token = token.strip()
        if token.isdigit():
            ids.append(int(token))
    return ids


def data_dir() -> Path:
    """Directory that holds the SQLite database and uploaded images."""
    if sys.platform == 'win32':
        base = os.environ.get('APPDATA')
        root = Path(base) if base else Path.home() / 'AppData' / 'Roaming'
        p = root / 'CraftingTree'
    else:
        xdg = os.environ.get('XDG_DATA_HOME')
        root = Path(xdg) if xdg else Path.home() / '.local' / 'share'
        p = root / 'crafting-tree'
    p.mkdir(parents=True, exist_ok=True)
    return p


def database_path() -> Path:
    return data_dir() / 'crafting-tree.db'


def images_dir(project_id) -> Path:
    p = data_dir() / 'projects' / str(project_id) / 'images'
    p.mkdir(parents=True, exist_ok=True)
    return p


def image_absolute(stored_path: str) -> Path | None:
    """Resolve a stored image path (relative to data dir) to an absolute Path."""
    if not stored_path:
        return None
    p = data_dir() / stored_path
    return p if p.exists() else None


def store_image(project_id, source_path, stored_name: str) -> str:
    """Copy an image into the project's images folder. Returns the relative path."""
    src = Path(source_path)
    if not src.exists():
        raise FileNotFoundError(f'Image not found: {source_path}')
    dest_dir = images_dir(project_id)
    dest_path = dest_dir / stored_name
    if dest_path.exists():
        stem = dest_path.stem
        suffix = dest_path.suffix
        i = 1
        while dest_path.exists():
            dest_path = dest_dir / f'{stem}-{i}{suffix}'
            i += 1
    shutil.copy2(src, dest_path)
    return dest_path.relative_to(data_dir()).as_posix()


def unique_stored_name(source_path: str) -> str:
    """Build a unique, safe stored name for an uploaded image."""
    src = Path(source_path)
    suffix = src.suffix.lower() or '.png'
    if suffix not in ('.png', '.jpg', '.jpeg', '.webp', '.gif', '.bmp'):
        suffix = '.png'
    return f'{datetime.now().strftime("%Y%m%d%H%M%S%f")}{suffix}'


def remove_image_file(stored_path: str) -> None:
    if not stored_path:
        return
    try:
        p = data_dir() / stored_path
        if p.exists():
            p.unlink()
    except OSError:
        pass


def format_qty(value: float) -> str:
    """Format a quantity cleanly (1.50 -> '1.5', 2.00 -> '2')."""
    if value is None:
        return '0'
    if abs(value - round(value)) < 1e-9:
        return str(int(round(value)))
    return f'{value:.2f}'.rstrip('0').rstrip('.')


def format_percent(fraction: float) -> str:
    return f'{fraction * 100:.0f}%'

