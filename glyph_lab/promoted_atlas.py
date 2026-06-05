from __future__ import annotations

from pathlib import Path
from typing import Any

from PIL import Image

from .atlas import ATLAS_COLUMNS, PALETTE
from .schema import CELL_SIZE, load_glyphs
from .transforms import bitmask_to_stamp


def build_promoted_atlas(
    base_atlas_path: str | Path,
    glyphs_path: str | Path,
    output_path: str | Path,
) -> dict[str, Any]:
    glyphs = load_glyphs(glyphs_path)
    max_index = max((glyph.index for glyph in glyphs), default=-1)
    with Image.open(base_atlas_path) as base_image:
        base = base_image.convert("RGBA")
    rows = max(1, (max_index // ATLAS_COLUMNS) + 1, (base.height + CELL_SIZE - 1) // CELL_SIZE)
    atlas = Image.new("RGBA", (ATLAS_COLUMNS * CELL_SIZE, rows * CELL_SIZE), PALETTE["transparent"])
    atlas.alpha_composite(base, (0, 0))

    copied_count = 0
    generated_count = 0
    missing_bitmask: list[str] = []
    for glyph in glyphs:
        x = (glyph.index % ATLAS_COLUMNS) * glyph.cell_size
        y = (glyph.index // ATLAS_COLUMNS) * glyph.cell_size
        if x + glyph.cell_size <= base.width and y + glyph.cell_size <= base.height:
            copied_count += 1
            continue
        bitmask = glyph.features.get("bitmask")
        if bitmask is None:
            missing_bitmask.append(glyph.id)
            continue
        color = PALETTE.get(glyph.palette_role, PALETTE["ink"])
        atlas.alpha_composite(bitmask_to_stamp(int(bitmask), color), (x, y))
        generated_count += 1

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    atlas.save(output_path)
    return {
        "atlas_path": str(output_path),
        "glyphs_path": str(glyphs_path),
        "width": atlas.width,
        "height": atlas.height,
        "cell_size": CELL_SIZE,
        "columns": ATLAS_COLUMNS,
        "glyph_count": len(glyphs),
        "copied_count": copied_count,
        "generated_count": generated_count,
        "missing_bitmask": missing_bitmask,
    }
