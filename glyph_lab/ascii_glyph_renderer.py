from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any
import json

from PIL import Image

from .ascii_bridge import resolve_ascii_char
from .atlas import load_atlas_stamps
from .schema import CELL_SIZE, load_glyphs


DEFAULT_EDGE_ALIASES = {"─": "-", "│": "|"}


def render_ascii_glyphs(
    ascii_path: str | Path,
    glyphs_path: str | Path,
    atlas_path: str | Path,
    output_path: str | Path,
    *,
    mapping_path: str | Path | None = None,
    scale: int = 4,
    background: tuple[int, int, int, int] = (255, 255, 255, 255),
) -> dict[str, Any]:
    if scale < 1:
        raise ValueError("scale must be at least 1")

    rows = Path(ascii_path).read_text(encoding="utf-8").splitlines()
    if not rows:
        raise ValueError("ASCII grid is empty")
    width = max(len(row) for row in rows)
    height = len(rows)
    if width <= 0:
        raise ValueError("ASCII grid has no columns")

    glyphs = load_glyphs(glyphs_path)
    stamps = load_atlas_stamps(atlas_path, glyphs)
    active_tokens = set(stamps)
    mapping = _load_json(mapping_path) if mapping_path is not None else None
    cell_size = _single_cell_size(glyphs)
    normalized_rows = [row.ljust(width) for row in rows]

    image = Image.new("RGBA", (width * cell_size, height * cell_size), background)
    token_counts: Counter[str] = Counter()
    fallback_counts: Counter[str] = Counter()
    for row_index, row in enumerate(normalized_rows, start=1):
        for column_index, char in enumerate(row, start=1):
            if char == " ":
                continue
            token = _resolve_token(char, mapping, active_tokens)
            if token is None:
                raise ValueError(f"Unknown glyph token {char!r} at row {row_index}, column {column_index}")
            if token != char:
                fallback_counts[char] += 1
            stamp = stamps.get(token)
            if stamp is None:
                raise ValueError(f"Unknown glyph token {token!r} at row {row_index}, column {column_index}")
            image.alpha_composite(stamp, ((column_index - 1) * cell_size, (row_index - 1) * cell_size))
            token_counts[token] += 1

    if scale != 1:
        image = image.resize((image.width * scale, image.height * scale), Image.Resampling.NEAREST)

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    image.save(output)
    return {
        "input_ascii": str(ascii_path),
        "glyphs": str(glyphs_path),
        "atlas": str(atlas_path),
        "mapping": str(mapping_path) if mapping_path is not None else None,
        "output": str(output),
        "grid_width": width,
        "grid_height": height,
        "cell_size": cell_size,
        "scale": scale,
        "output_width": image.width,
        "output_height": image.height,
        "token_counts": dict(sorted(token_counts.items())),
        "fallback_counts": dict(sorted(fallback_counts.items())),
    }


def _single_cell_size(glyphs: list[Any]) -> int:
    sizes = {glyph.cell_size for glyph in glyphs}
    if not sizes:
        return CELL_SIZE
    if len(sizes) != 1:
        raise ValueError(f"ASCII glyph rendering requires one cell size, found {sorted(sizes)}")
    return sizes.pop()


def _resolve_token(char: str, mapping: dict[str, Any] | None, active_tokens: set[str]) -> str | None:
    if char in active_tokens:
        return char
    if mapping is None:
        alias = DEFAULT_EDGE_ALIASES.get(char)
        return alias if alias in active_tokens else None
    resolved = resolve_ascii_char(char, mapping, active_tokens)
    if resolved is None:
        alias = DEFAULT_EDGE_ALIASES.get(char)
        return alias if alias in active_tokens else None
    return resolved["token"]


def _load_json(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as handle:
        return json.load(handle)
