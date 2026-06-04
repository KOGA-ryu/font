from __future__ import annotations

from .schema import Glyph


class GridValidationError(ValueError):
    pass


def glyph_map(glyphs: list[Glyph]) -> dict[str, Glyph]:
    mapping = {}
    for glyph in glyphs:
        if glyph.token in mapping:
            raise ValueError(f"duplicate glyph token {glyph.token!r}")
        mapping[glyph.token] = glyph
    return mapping


def read_control_grid(path: str) -> list[str]:
    with open(path, "r", encoding="utf-8") as handle:
        rows = [line.rstrip("\n") for line in handle]
    return validate_grid(rows)


def validate_grid(rows: list[str]) -> list[str]:
    if not rows:
        raise GridValidationError("control grid is empty")
    width = len(rows[0])
    if width == 0:
        raise GridValidationError("control grid has an empty first row")
    for row_index, row in enumerate(rows, start=1):
        if len(row) != width:
            raise GridValidationError(
                f"control grid row {row_index} has width {len(row)}, expected {width}"
            )
    return rows


def validate_tokens(rows: list[str], tokens: set[str]) -> None:
    for row_index, row in enumerate(rows, start=1):
        for column_index, char in enumerate(row, start=1):
            if char != " " and char not in tokens:
                raise GridValidationError(
                    f"unknown token at row {row_index}, column {column_index}: {char!r}"
                )
