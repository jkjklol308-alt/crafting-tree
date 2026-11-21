"""Data models used across the application.

Deliberately plain dataclasses with no behaviour beyond simple conversion.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Item:
    id: Optional[int]
    name: str
    description: str = ''
    category: str = ''
    tags: list = field(default_factory=list)
    image_path: str = ''   # relative path from data dir, '' if none
    created_at: str = ''
    updated_at: str = ''

    def classification(self, downstreams_count: int, upstreams_count: int) -> str:
        """raw / intermediate / final (standalone items treated as raw)."""
        if downstreams_count == 0 and upstreams_count == 0:
            return 'raw'
        if downstreams_count == 0:
            return 'final'
        if upstreams_count == 0:
            return 'raw'
        return 'intermediate'


@dataclass
class ProcessMethod:
    id: Optional[int]
    name: str
    description: str = ''
    icon_path: str = ''


@dataclass
class RecipeInput:
    item_id: int
    quantity: float = 1.0


@dataclass
class RecipeOutput:
    item_id: int
    quantity: float = 1.0
    probability: float = 1.0   # 0.0 - 1.0


@dataclass
class Recipe:
    id: Optional[int]
    process_id: int
    name: str = ''
    notes: str = ''
    created_at: str = ''
    updated_at: str = ''
    inputs: list = field(default_factory=list)   # list[RecipeInput]
    outputs: list = field(default_factory=list)  # list[RecipeOutput]


def tags_to_str(tags: list) -> str:
    return json.dumps(list(tags or []), ensure_ascii=False)


def tags_from_str(tags_raw: str) -> list:
    if not tags_raw:
        return []
    try:
        data = json.loads(tags_raw)
        if isinstance(data, list):
            return [str(t) for t in data]
    except (ValueError, TypeError):
        pass
    # fallback: comma separated
    return [t.strip() for t in tags_raw.split(',') if t.strip()]


def clamp_probability(value: float) -> float:
    try:
        v = float(value)
    except (TypeError, ValueError):
        v = 1.0
    return max(0.0, min(1.0, v))


def validate_probability(value: float) -> float:
    """Strict validation: probability must be in (0, 1]."""
    v = clamp_probability(value)
    if v <= 0.0:
        raise ValueError('Probability must be greater than 0.')
    return v


def parse_tags(raw: str) -> list:
    """Parse a comma/semicolon-separated tag string into a list (trimmed)."""
    if not raw:
        return []
    parts = raw.replace(';', ',').split(',')
    return [p.strip() for p in parts if p.strip()]
