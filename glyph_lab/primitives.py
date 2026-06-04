from __future__ import annotations

import random
from typing import Callable

from PIL import Image

from .schema import CELL_SIZE


INK = (34, 32, 29, 255)


def point(x: int, y: int, color: tuple[int, int, int, int] = INK) -> Image.Image:
    _require_range("x", x, 0, CELL_SIZE - 1)
    _require_range("y", y, 0, CELL_SIZE - 1)
    return _stamp([(x, y)], color)


def line(
    orientation: str,
    thickness: int = 1,
    broken: bool = False,
    color: tuple[int, int, int, int] = INK,
) -> Image.Image:
    _require_choice("orientation", orientation, {"horizontal", "vertical", "diagonal_rise", "diagonal_fall"})
    _require_choice("thickness", thickness, {1, 2})
    coords: set[tuple[int, int]] = set()
    if orientation == "horizontal":
        rows = [1] if thickness == 1 else [1, 2]
        coords = {(x, y) for x in range(CELL_SIZE) for y in rows}
    elif orientation == "vertical":
        cols = [1] if thickness == 1 else [1, 2]
        coords = {(x, y) for x in cols for y in range(CELL_SIZE)}
    elif orientation == "diagonal_rise":
        bands = {3} if thickness == 1 else {2, 3}
        coords = {(x, y) for x in range(CELL_SIZE) for y in range(CELL_SIZE) if x + y in bands}
    elif orientation == "diagonal_fall":
        bands = {0} if thickness == 1 else {0, 1}
        coords = {(x, y) for x in range(CELL_SIZE) for y in range(CELL_SIZE) if x - y in bands}

    if broken:
        coords = _break_line(coords, orientation)
    return _stamp(sorted(coords), color)


def block(kind: str, color: tuple[int, int, int, int] = INK) -> Image.Image:
    _require_choice(
        "kind",
        kind,
        {
            "solid",
            "top_half",
            "bottom_half",
            "left_half",
            "right_half",
            "top_left_quarter",
            "top_right_quarter",
            "bottom_left_quarter",
            "bottom_right_quarter",
            "three_quarter_no_top_left",
            "three_quarter_no_top_right",
            "three_quarter_no_bottom_left",
            "three_quarter_no_bottom_right",
        },
    )
    rules: dict[str, Callable[[int, int], bool]] = {
        "solid": lambda _x, _y: True,
        "top_half": lambda _x, y: y < 2,
        "bottom_half": lambda _x, y: y >= 2,
        "left_half": lambda x, _y: x < 2,
        "right_half": lambda x, _y: x >= 2,
        "top_left_quarter": lambda x, y: x < 2 and y < 2,
        "top_right_quarter": lambda x, y: x >= 2 and y < 2,
        "bottom_left_quarter": lambda x, y: x < 2 and y >= 2,
        "bottom_right_quarter": lambda x, y: x >= 2 and y >= 2,
        "three_quarter_no_top_left": lambda x, y: not (x < 2 and y < 2),
        "three_quarter_no_top_right": lambda x, y: not (x >= 2 and y < 2),
        "three_quarter_no_bottom_left": lambda x, y: not (x < 2 and y >= 2),
        "three_quarter_no_bottom_right": lambda x, y: not (x >= 2 and y >= 2),
    }
    return _stamp(_coords(rules[kind]), color)


def corner(
    position: str,
    thickness: int = 1,
    color: tuple[int, int, int, int] = INK,
) -> Image.Image:
    _require_choice("position", position, {"top_left", "top_right", "bottom_left", "bottom_right"})
    _require_choice("thickness", thickness, {1, 2})
    span = range(thickness)
    high = range(CELL_SIZE - thickness, CELL_SIZE)
    coords: set[tuple[int, int]]
    if position == "top_left":
        coords = {(x, y) for x in span for y in range(CELL_SIZE)} | {(x, y) for y in span for x in range(CELL_SIZE)}
    elif position == "top_right":
        coords = {(x, y) for x in high for y in range(CELL_SIZE)} | {(x, y) for y in span for x in range(CELL_SIZE)}
    elif position == "bottom_left":
        coords = {(x, y) for x in span for y in range(CELL_SIZE)} | {(x, y) for y in high for x in range(CELL_SIZE)}
    else:
        coords = {(x, y) for x in high for y in range(CELL_SIZE)} | {(x, y) for y in high for x in range(CELL_SIZE)}
    return _stamp(sorted(coords), color)


def crack(kind: str, color: tuple[int, int, int, int] = INK) -> Image.Image:
    _require_choice("kind", kind, {"short", "long_diagonal", "vertical_jagged", "forked"})
    patterns = {
        "short": [(0, 1), (1, 1), (2, 2), (3, 2)],
        "long_diagonal": [(0, 3), (1, 2), (2, 1), (3, 0)],
        "vertical_jagged": [(1, 0), (1, 1), (2, 2), (2, 3)],
        "forked": [(1, 0), (1, 1), (0, 2), (1, 2), (2, 2), (2, 3)],
    }
    return _stamp(patterns[kind], color)


def fill(
    kind: str,
    seed: int = 0,
    color: tuple[int, int, int, int] = INK,
) -> Image.Image:
    _require_choice("kind", kind, {"sparse", "checker", "dense", "noise"})
    if kind == "sparse":
        coords = [(0, 0), (2, 1), (1, 3)]
    elif kind == "checker":
        coords = _coords(lambda x, y: (x + y) % 2 == 0)
    elif kind == "dense":
        coords = _coords(lambda x, y: (x, y) not in {(0, 0), (3, 0), (0, 3), (3, 3)})
    else:
        rng = random.Random(seed)
        coords = [(x, y) for y in range(CELL_SIZE) for x in range(CELL_SIZE) if rng.random() < 0.45]
    return _stamp(coords, color)


def bevel(kind: str, color: tuple[int, int, int, int] = INK) -> Image.Image:
    _require_choice("kind", kind, {"highlight_top_left", "shadow_bottom_right", "diagonal"})
    patterns = {
        "highlight_top_left": _coords(lambda x, y: y == 0 or x == 0),
        "shadow_bottom_right": _coords(lambda x, y: y == 3 or x == 3),
        "diagonal": [(0, 0), (1, 1), (2, 2), (3, 3)],
    }
    return _stamp(patterns[kind], color)


def primitive_stamp(primitive_family: str, **params) -> Image.Image:
    _require_choice("primitive_family", primitive_family, {"point", "line", "block", "corner", "crack", "fill", "bevel"})
    if primitive_family == "point":
        _validate_params("point", params, {"x", "y"}, set())
        return point(**params)
    if primitive_family == "line":
        _validate_params("line", params, {"orientation"}, {"thickness", "broken"})
        return line(**params)
    if primitive_family == "block":
        _validate_params("block", params, {"kind"}, set())
        return block(**params)
    if primitive_family == "corner":
        _validate_params("corner", params, {"position"}, {"thickness"})
        return corner(**params)
    if primitive_family == "crack":
        _validate_params("crack", params, {"kind"}, set())
        return crack(**params)
    if primitive_family == "fill":
        _validate_params("fill", params, {"kind"}, {"seed"})
        return fill(**params)
    _validate_params("bevel", params, {"kind"}, set())
    return bevel(**params)


def _stamp(coords: list[tuple[int, int]], color: tuple[int, int, int, int]) -> Image.Image:
    image = Image.new("RGBA", (CELL_SIZE, CELL_SIZE), (0, 0, 0, 0))
    pixels = image.load()
    for x, y in coords:
        _require_range("x", x, 0, CELL_SIZE - 1)
        _require_range("y", y, 0, CELL_SIZE - 1)
        pixels[x, y] = color
    return image


def _coords(rule: Callable[[int, int], bool]) -> list[tuple[int, int]]:
    return [(x, y) for y in range(CELL_SIZE) for x in range(CELL_SIZE) if rule(x, y)]


def _break_line(coords: set[tuple[int, int]], orientation: str) -> set[tuple[int, int]]:
    if orientation == "horizontal":
        return {coord for coord in coords if coord[0] != 2}
    if orientation == "vertical":
        return {coord for coord in coords if coord[1] != 2}
    return {coord for coord in coords if coord not in {(1, 2), (2, 1)}}


def _require_range(name: str, value: int, low: int, high: int) -> None:
    if value < low or value > high:
        raise ValueError(f"{name} must be between {low} and {high}, got {value}")


def _require_choice(name: str, value, choices: set) -> None:
    if value not in choices:
        options = ", ".join(str(choice) for choice in sorted(choices))
        raise ValueError(f"{name} must be one of {options}, got {value!r}")


def _validate_params(
    primitive_family: str,
    params: dict,
    required: set[str],
    optional: set[str],
) -> None:
    allowed = required | optional | {"color"}
    missing = required - set(params)
    unknown = set(params) - allowed
    if missing:
        names = ", ".join(sorted(missing))
        raise ValueError(f"{primitive_family} primitive missing required params: {names}")
    if unknown:
        names = ", ".join(sorted(unknown))
        raise ValueError(f"{primitive_family} primitive got unknown params: {names}")
