from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Callable
import json

from PIL import Image

from .measure import measure_stamp
from .schema import ATLAS_COLUMNS, CELL_SIZE, Glyph, save_glyphs


PALETTE: dict[str, tuple[int, int, int, int]] = {
    "transparent": (0, 0, 0, 0),
    "ink": (34, 32, 29, 255),
    "stone_dark": (88, 83, 74, 255),
    "stone_mid": (142, 134, 118, 255),
    "stone_light": (188, 178, 154, 255),
    "highlight": (235, 226, 190, 255),
    "crack": (45, 40, 37, 255),
}


def default_glyphs() -> list[Glyph]:
    records = [
        ("empty", ".", "void", "none", "base_fill", "transparent"),
        ("solid", "#", "fill", "solid", "base_fill", "stone_mid"),
        ("top_half", "^", "fill", "half", "base_fill", "stone_light"),
        ("bottom_half", "_", "fill", "half", "base_fill", "stone_dark"),
        ("left_half", "[", "fill", "half", "base_fill", "stone_mid"),
        ("right_half", "]", "fill", "half", "base_fill", "stone_mid"),
        ("top_left_quarter", "q", "fill", "quarter", "base_fill", "stone_light"),
        ("top_right_quarter", "p", "fill", "quarter", "base_fill", "stone_light"),
        ("bottom_left_quarter", "b", "fill", "quarter", "base_fill", "stone_dark"),
        ("bottom_right_quarter", "d", "fill", "quarter", "base_fill", "stone_dark"),
        ("light_fill_sparse", ",", "fill", "texture", "base_fill", "stone_light"),
        ("mid_fill_checker", ":", "fill", "texture", "base_fill", "stone_mid"),
        ("dark_fill_dense", ";", "fill", "texture", "shadow", "stone_dark"),
        ("deep_shadow", "S", "shadow", "ambient", "shadow", "stone_dark"),
        ("horizontal_edge", "-", "edge", "horizontal", "edge", "ink"),
        ("vertical_edge", "|", "edge", "vertical", "edge", "ink"),
        ("diagonal_rise", "/", "edge", "diagonal", "edge", "ink"),
        ("diagonal_fall", "\\", "edge", "diagonal", "edge", "ink"),
        ("corner_top_left", "a", "edge", "corner", "edge", "ink"),
        ("corner_top_right", "c", "edge", "corner", "edge", "ink"),
        ("corner_bottom_left", "u", "edge", "corner", "edge", "ink"),
        ("corner_bottom_right", "n", "edge", "corner", "edge", "ink"),
        ("tee_up", "T", "edge", "junction", "edge", "ink"),
        ("tee_down", "t", "edge", "junction", "edge", "ink"),
        ("tee_left", "<", "edge", "junction", "edge", "ink"),
        ("tee_right", ">", "edge", "junction", "edge", "ink"),
        ("cross", "+", "edge", "junction", "edge", "ink"),
        ("bevel_highlight", "h", "highlight", "bevel", "detail", "highlight"),
        ("bevel_shadow", "s", "shadow", "bevel", "shadow", "stone_dark"),
        ("chip_dot", "*", "detail", "damage", "detail", "crack"),
        ("crack_short", "x", "detail", "damage", "detail", "crack"),
        ("centerline_marker", "C", "guide", "centerline", "detail", "highlight"),
    ]
    glyphs = []
    for index, (name, token, role, family, layer, palette_role) in enumerate(records):
        glyphs.append(
            Glyph(
                id=f"4.stone.{role}.{family}.{name}_{index:02d}",
                token=token,
                index=index,
                role=role,
                family=family,
                layer=layer,
                palette_role=palette_role,
                constraints=_constraints(layer),
            )
        )
    return glyphs


def stamp_for_index(index: int, palette_role: str = "ink") -> Image.Image:
    mask = _mask_for_index(index)
    color = PALETTE[palette_role]
    image = Image.new("RGBA", (CELL_SIZE, CELL_SIZE), PALETTE["transparent"])
    pixels = image.load()
    for y, row in enumerate(mask):
        for x, value in enumerate(row):
            if value:
                pixels[x, y] = color
    return image


def generate_pack(pack_dir: str | Path, overwrite: bool = True) -> None:
    pack = Path(pack_dir)
    pack.mkdir(parents=True, exist_ok=True)
    glyphs = []
    features = {}
    for glyph in default_glyphs():
        stamp = stamp_for_index(glyph.index, glyph.palette_role)
        measured = measure_stamp(stamp)
        glyphs.append(replace(glyph, features=measured))
        features[glyph.token] = {"index": glyph.index, "id": glyph.id, "features": measured}

    atlas_path = pack / "atlas.png"
    if overwrite or not atlas_path.exists():
        atlas_path.parent.mkdir(parents=True, exist_ok=True)
        atlas = Image.new("RGBA", (ATLAS_COLUMNS * CELL_SIZE, 4 * CELL_SIZE), PALETTE["transparent"])
        for glyph in glyphs:
            stamp = stamp_for_index(glyph.index, glyph.palette_role)
            x = (glyph.index % ATLAS_COLUMNS) * CELL_SIZE
            y = (glyph.index // ATLAS_COLUMNS) * CELL_SIZE
            atlas.alpha_composite(stamp, (x, y))
        atlas.save(atlas_path)

    save_glyphs(pack / "glyphs.json", glyphs)
    with (pack / "features.json").open("w", encoding="utf-8") as handle:
        json.dump({"features": features}, handle, indent=2)
        handle.write("\n")


def load_atlas_stamps(atlas_path: str | Path, glyphs: list[Glyph]) -> dict[str, Image.Image]:
    atlas = Image.open(atlas_path).convert("RGBA")
    stamps = {}
    for glyph in glyphs:
        x = (glyph.index % ATLAS_COLUMNS) * glyph.cell_size
        y = (glyph.index // ATLAS_COLUMNS) * glyph.cell_size
        stamps[glyph.token] = atlas.crop((x, y, x + glyph.cell_size, y + glyph.cell_size))
    return stamps


def _constraints(layer: str) -> dict:
    if layer == "edge":
        return {
            "allowed_layers": ["edge"],
            "allowed_regions": ["silhouette_boundary", "panel_boundary"],
            "forbidden_regions": ["background"],
        }
    if layer == "shadow":
        return {
            "allowed_layers": ["shadow"],
            "allowed_regions": ["interior", "occlusion", "bevel"],
            "forbidden_regions": ["empty_background"],
        }
    if layer == "detail":
        return {
            "allowed_layers": ["detail"],
            "allowed_regions": ["surface", "centerline", "damage"],
            "forbidden_regions": ["background"],
        }
    return {
        "allowed_layers": ["base_fill"],
        "allowed_regions": ["interior", "surface"],
        "forbidden_regions": ["background"],
    }


def _mask_for_index(index: int) -> list[list[int]]:
    dot = lambda rule: [[1 if rule(x, y) else 0 for x in range(4)] for y in range(4)]
    masks: dict[int, Callable[[], list[list[int]]]] = {
        0: lambda: dot(lambda _x, _y: False),
        1: lambda: dot(lambda _x, _y: True),
        2: lambda: dot(lambda _x, y: y < 2),
        3: lambda: dot(lambda _x, y: y >= 2),
        4: lambda: dot(lambda x, _y: x < 2),
        5: lambda: dot(lambda x, _y: x >= 2),
        6: lambda: dot(lambda x, y: x < 2 and y < 2),
        7: lambda: dot(lambda x, y: x >= 2 and y < 2),
        8: lambda: dot(lambda x, y: x < 2 and y >= 2),
        9: lambda: dot(lambda x, y: x >= 2 and y >= 2),
        10: lambda: dot(lambda x, y: (x, y) in {(0, 0), (2, 1), (1, 3)}),
        11: lambda: dot(lambda x, y: (x + y) % 2 == 0),
        12: lambda: dot(lambda x, y: not ((x, y) in {(0, 0), (3, 0), (0, 3), (3, 3)})),
        13: lambda: dot(lambda x, y: y >= 2 or x == 3),
        14: lambda: dot(lambda _x, y: y in {1, 2}),
        15: lambda: dot(lambda x, _y: x in {1, 2}),
        16: lambda: dot(lambda x, y: x + y in {2, 3}),
        17: lambda: dot(lambda x, y: x - y in {0, 1}),
        18: lambda: dot(lambda x, y: x == 0 or y == 0),
        19: lambda: dot(lambda x, y: x == 3 or y == 0),
        20: lambda: dot(lambda x, y: x == 0 or y == 3),
        21: lambda: dot(lambda x, y: x == 3 or y == 3),
        22: lambda: dot(lambda x, y: y == 0 or x in {1, 2}),
        23: lambda: dot(lambda x, y: y == 3 or x in {1, 2}),
        24: lambda: dot(lambda x, y: x == 0 or y in {1, 2}),
        25: lambda: dot(lambda x, y: x == 3 or y in {1, 2}),
        26: lambda: dot(lambda x, y: x in {1, 2} or y in {1, 2}),
        27: lambda: dot(lambda x, y: y == 0 or (x, y) in {(0, 1), (1, 1)}),
        28: lambda: dot(lambda x, y: y == 3 or (x, y) in {(2, 2), (3, 2)}),
        29: lambda: dot(lambda x, y: (x, y) in {(1, 1), (2, 2)}),
        30: lambda: dot(lambda x, y: (x, y) in {(0, 1), (1, 1), (2, 2), (3, 2)}),
        31: lambda: dot(lambda x, y: x in {1, 2} and y in {0, 3}),
    }
    return masks[index]()
