from __future__ import annotations

from typing import Any

from PIL import Image

from .primitives import INK
from .schema import CELL_SIZE


LINEWORK_DIRECTIONS = {"horizontal", "vertical", "diagonal_rise", "diagonal_fall"}
LINEWORK_OFFSETS = {"top", "middle", "bottom", "left", "center", "right"}
CORNER_POSITIONS = {"top_left", "top_right", "bottom_left", "bottom_right"}


def linework_line(
    direction: str,
    offset: str = "middle",
    thickness: int = 1,
    broken: bool = False,
    color: tuple[int, int, int, int] = INK,
) -> Image.Image:
    _require_choice("direction", direction, LINEWORK_DIRECTIONS)
    _require_choice("thickness", thickness, {1, 2})
    coords: set[tuple[int, int]]
    if direction == "horizontal":
        row = _horizontal_row(offset)
        rows = {row} if thickness == 1 else {max(0, row - 1), row}
        coords = {(x, y) for x in range(CELL_SIZE) for y in rows}
    elif direction == "vertical":
        col = _vertical_col(offset)
        cols = {col} if thickness == 1 else {max(0, col - 1), col}
        coords = {(x, y) for x in cols for y in range(CELL_SIZE)}
    elif direction == "diagonal_rise":
        coords = _diagonal_rise(offset, thickness)
    else:
        coords = _diagonal_fall(offset, thickness)
    if broken:
        coords = _break_coords(coords, direction)
    return _stamp(sorted(coords), color)


def linework_corner(
    position: str,
    thickness: int = 1,
    radius: str = "sharp",
    color: tuple[int, int, int, int] = INK,
) -> Image.Image:
    _require_choice("position", position, CORNER_POSITIONS)
    _require_choice("thickness", thickness, {1, 2})
    _require_choice("radius", radius, {"sharp", "soft"})
    coords = _corner_coords(position, thickness)
    if radius == "soft":
        coords -= _corner_cutout(position)
    return _stamp(sorted(coords), color)


def linework_cap(
    direction: str,
    side: str,
    thickness: int = 1,
    color: tuple[int, int, int, int] = INK,
) -> Image.Image:
    _require_choice("direction", direction, {"horizontal", "vertical"})
    _require_choice("thickness", thickness, {1, 2})
    if direction == "horizontal":
        _require_choice("side", side, {"left", "right"})
        rows = {1} if thickness == 1 else {1, 2}
        xs = range(0, 3) if side == "left" else range(1, 4)
        coords = {(x, y) for x in xs for y in rows}
    else:
        _require_choice("side", side, {"top", "bottom"})
        cols = {1} if thickness == 1 else {1, 2}
        ys = range(0, 3) if side == "top" else range(1, 4)
        coords = {(x, y) for x in cols for y in ys}
    return _stamp(sorted(coords), color)


def hatch_pattern(
    kind: str,
    density: str = "light",
    color: tuple[int, int, int, int] = INK,
) -> Image.Image:
    _require_choice("kind", kind, {"horizontal", "vertical", "diagonal_rise", "diagonal_fall", "cross"})
    _require_choice("density", density, {"light", "medium", "dense"})
    if kind == "horizontal":
        rows = {"light": {1}, "medium": {0, 2}, "dense": {0, 1, 2}}[density]
        coords = {(x, y) for y in rows for x in range(CELL_SIZE)}
    elif kind == "vertical":
        cols = {"light": {1}, "medium": {0, 2}, "dense": {0, 1, 2}}[density]
        coords = {(x, y) for x in cols for y in range(CELL_SIZE)}
    elif kind == "diagonal_rise":
        bands = {"light": {3}, "medium": {1, 3}, "dense": {1, 2, 3}}[density]
        coords = {(x, y) for y in range(CELL_SIZE) for x in range(CELL_SIZE) if x + y in bands}
    elif kind == "diagonal_fall":
        bands = {"light": {0}, "medium": {-2, 0}, "dense": {-1, 0, 1}}[density]
        coords = {(x, y) for y in range(CELL_SIZE) for x in range(CELL_SIZE) if x - y in bands}
    else:
        coords = _hatch_coords("diagonal_rise", density) | _hatch_coords("diagonal_fall", density)
    return _stamp(sorted(coords), color)


def linework_metadata(spec: dict[str, Any]) -> dict[str, Any]:
    kind = spec["kind"]
    params = spec.get("params", {})
    if kind == "line":
        return {
            "angle_degrees": _angle(params["direction"]),
            "connector_sides": _line_connector_sides(params["direction"], params.get("offset", "middle")),
            "thickness": params.get("thickness", 1),
            "variant": params.get("offset", "middle"),
        }
    if kind == "corner":
        return {
            "angle_degrees": None,
            "connector_sides": _corner_sides(params["position"]),
            "thickness": params.get("thickness", 1),
            "variant": params.get("radius", "sharp"),
        }
    if kind == "cap":
        return {
            "angle_degrees": _angle(params["direction"]),
            "connector_sides": [params["side"]],
            "thickness": params.get("thickness", 1),
            "variant": f"{params['direction']}_{params['side']}",
        }
    return {
        "angle_degrees": _angle(params["kind"]) if params["kind"] != "cross" else None,
        "connector_sides": [],
        "thickness": 1,
        "variant": params["density"],
    }


def linework_stamp(spec: dict[str, Any], color: tuple[int, int, int, int] = INK) -> Image.Image:
    kind = spec["kind"]
    params = dict(spec.get("params", {}))
    params["color"] = color
    if kind == "line":
        return linework_line(**params)
    if kind == "corner":
        return linework_corner(**params)
    if kind == "cap":
        return linework_cap(**params)
    if kind == "hatch":
        return hatch_pattern(**params)
    raise ValueError(f"unknown linework primitive kind: {kind}")


def default_linework_specs() -> list[dict[str, Any]]:
    specs: list[dict[str, Any]] = []
    for direction in ("horizontal", "vertical"):
        offsets = ("top", "middle", "bottom") if direction == "horizontal" else ("left", "center", "right")
        for offset in offsets:
            specs.append(_spec("line", f"{direction}_{offset}_thin", {"direction": direction, "offset": offset}))
        specs.append(_spec("line", f"{direction}_middle_thick", {"direction": direction, "offset": "middle" if direction == "horizontal" else "center", "thickness": 2}))
        specs.append(_spec("line", f"{direction}_broken", {"direction": direction, "offset": "middle" if direction == "horizontal" else "center", "broken": True}))
    for direction in ("diagonal_rise", "diagonal_fall"):
        for offset in ("left", "middle", "right"):
            specs.append(_spec("line", f"{direction}_{offset}", {"direction": direction, "offset": offset}))
        specs.append(_spec("line", f"{direction}_thick", {"direction": direction, "offset": "middle", "thickness": 2}))
        specs.append(_spec("line", f"{direction}_broken", {"direction": direction, "offset": "middle", "broken": True}))
    for position in sorted(CORNER_POSITIONS):
        specs.append(_spec("corner", f"corner_{position}_sharp", {"position": position, "radius": "sharp"}))
        specs.append(_spec("corner", f"corner_{position}_soft", {"position": position, "radius": "soft"}))
    for direction, sides in (("horizontal", ("left", "right")), ("vertical", ("top", "bottom"))):
        for side in sides:
            specs.append(_spec("cap", f"cap_{direction}_{side}", {"direction": direction, "side": side}))
    for kind in ("horizontal", "vertical", "diagonal_rise", "diagonal_fall", "cross"):
        for density in ("light", "medium", "dense"):
            specs.append(_spec("hatch", f"hatch_{kind}_{density}", {"kind": kind, "density": density}, role="detail", family="texture", layer="detail", palette_role="crack"))
    return specs


def _spec(
    kind: str,
    name: str,
    params: dict[str, Any],
    role: str = "edge",
    family: str = "linework",
    layer: str = "edge",
    palette_role: str = "ink",
) -> dict[str, Any]:
    return {
        "kind": kind,
        "name": name,
        "params": params,
        "role": role,
        "family": family,
        "layer": layer,
        "palette_role": palette_role,
    }


def _stamp(coords: list[tuple[int, int]], color: tuple[int, int, int, int]) -> Image.Image:
    image = Image.new("RGBA", (CELL_SIZE, CELL_SIZE), (0, 0, 0, 0))
    pixels = image.load()
    for x, y in coords:
        if 0 <= x < CELL_SIZE and 0 <= y < CELL_SIZE:
            pixels[x, y] = color
    return image


def _horizontal_row(offset: str) -> int:
    _require_choice("offset", offset, {"top", "middle", "bottom"})
    return {"top": 0, "middle": 1, "bottom": 3}[offset]


def _vertical_col(offset: str) -> int:
    _require_choice("offset", offset, {"left", "center", "right"})
    return {"left": 0, "center": 1, "right": 3}[offset]


def _diagonal_rise(offset: str, thickness: int) -> set[tuple[int, int]]:
    _require_choice("offset", offset, {"left", "middle", "right"})
    base = {"left": 2, "middle": 3, "right": 4}[offset]
    bands = {base} if thickness == 1 else {base - 1, base}
    return {(x, y) for y in range(CELL_SIZE) for x in range(CELL_SIZE) if x + y in bands}


def _diagonal_fall(offset: str, thickness: int) -> set[tuple[int, int]]:
    _require_choice("offset", offset, {"left", "middle", "right"})
    base = {"left": -1, "middle": 0, "right": 1}[offset]
    bands = {base} if thickness == 1 else {base, base + 1}
    return {(x, y) for y in range(CELL_SIZE) for x in range(CELL_SIZE) if x - y in bands}


def _corner_coords(position: str, thickness: int) -> set[tuple[int, int]]:
    top = range(thickness)
    bottom = range(CELL_SIZE - thickness, CELL_SIZE)
    left = range(thickness)
    right = range(CELL_SIZE - thickness, CELL_SIZE)
    if position == "top_left":
        return {(x, y) for x in left for y in range(CELL_SIZE)} | {(x, y) for y in top for x in range(CELL_SIZE)}
    if position == "top_right":
        return {(x, y) for x in right for y in range(CELL_SIZE)} | {(x, y) for y in top for x in range(CELL_SIZE)}
    if position == "bottom_left":
        return {(x, y) for x in left for y in range(CELL_SIZE)} | {(x, y) for y in bottom for x in range(CELL_SIZE)}
    return {(x, y) for x in right for y in range(CELL_SIZE)} | {(x, y) for y in bottom for x in range(CELL_SIZE)}


def _corner_cutout(position: str) -> set[tuple[int, int]]:
    return {
        "top_left": {(0, 0)},
        "top_right": {(3, 0)},
        "bottom_left": {(0, 3)},
        "bottom_right": {(3, 3)},
    }[position]


def _hatch_coords(kind: str, density: str) -> set[tuple[int, int]]:
    stamp = hatch_pattern(kind, density)
    pixels = stamp.load()
    return {(x, y) for y in range(CELL_SIZE) for x in range(CELL_SIZE) if pixels[x, y][3] > 0}


def _break_coords(coords: set[tuple[int, int]], direction: str) -> set[tuple[int, int]]:
    if direction == "horizontal":
        return {coord for coord in coords if coord[0] != 2}
    if direction == "vertical":
        return {coord for coord in coords if coord[1] != 2}
    return {coord for coord in coords if coord not in {(1, 2), (2, 1)}}


def _angle(direction: str) -> float:
    return {
        "horizontal": 0.0,
        "vertical": 90.0,
        "diagonal_rise": 45.0,
        "diagonal_fall": 135.0,
    }[direction]


def _line_connector_sides(direction: str, offset: str) -> list[str]:
    if direction == "horizontal":
        sides = ["left", "right"]
        if offset == "top":
            sides.append("top")
        elif offset == "bottom":
            sides.append("bottom")
        return sides
    if direction == "vertical":
        sides = ["top", "bottom"]
        if offset == "left":
            sides.append("left")
        elif offset == "right":
            sides.append("right")
        return sides
    return ["left", "right", "top", "bottom"]


def _corner_sides(position: str) -> list[str]:
    return {
        "top_left": ["top", "left"],
        "top_right": ["top", "right"],
        "bottom_left": ["bottom", "left"],
        "bottom_right": ["bottom", "right"],
    }[position]


def _require_choice(name: str, value: Any, choices: set[Any]) -> None:
    if value not in choices:
        options = ", ".join(str(choice) for choice in sorted(choices))
        raise ValueError(f"{name} must be one of {options}, got {value!r}")
