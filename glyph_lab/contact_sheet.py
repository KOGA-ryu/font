from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .atlas import load_atlas_stamps
from .schema import ATLAS_COLUMNS, load_glyphs
from .transforms import scale_nearest


def generate_contact_sheet(
    atlas_path: str | Path,
    glyphs_path: str | Path,
    output_path: str | Path,
    cell_pixels: int = 64,
) -> None:
    glyphs = load_glyphs(glyphs_path)
    stamps = load_atlas_stamps(atlas_path, glyphs)
    rows = (len(glyphs) + ATLAS_COLUMNS - 1) // ATLAS_COLUMNS
    sheet = Image.new("RGBA", (ATLAS_COLUMNS * cell_pixels, rows * cell_pixels), (244, 241, 232, 255))
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()

    for glyph in glyphs:
        col = glyph.index % ATLAS_COLUMNS
        row = glyph.index // ATLAS_COLUMNS
        left = col * cell_pixels
        top = row * cell_pixels
        draw.rectangle((left, top, left + cell_pixels - 1, top + cell_pixels - 1), outline=(120, 112, 100, 255))
        stamp = scale_nearest(stamps[glyph.token], 10)
        sheet.alpha_composite(stamp, (left + 12, top + 6))
        label = f"{glyph.index:02d} {glyph.token}"
        draw.text((left + 5, top + 49), label, fill=(30, 28, 24, 255), font=font)

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output_path)
