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
        broken = bool(params.get("broken", False))
        direction = params["direction"]
        thickness = params.get("thickness", 1)
        variant = params.get("offset", "middle")
        return {
            "linework_package": "linework.break" if broken else "linework.stroke",
            "stroke_topology": "broken_segment" if broken else "pass_through_segment",
            "stroke_ports": _line_ports(direction, variant),
            "angle_degrees": _angle(direction),
            "connector_sides": _line_connector_sides(direction, variant),
            "thickness": thickness,
            "variant": variant,
            "weight_profile": _weight_profile(thickness),
            "cap_style": "none",
            "join_style": "none",
            "break_rhythm": "middle_dropout" if broken else "solid",
            "roughness": "clean",
            "continuity": "implied_through_gap" if broken else "continuous",
            "intended_continuity": "pass_through",
            "visible_fragments": 2 if broken else 1,
            "dropout_ratio": 0.25 if broken else 0.0,
            "coverage": _coverage_class(thickness),
        }
    if kind == "corner":
        radius = params.get("radius", "sharp")
        thickness = params.get("thickness", 1)
        return {
            "linework_package": "linework.curve" if radius == "soft" else "linework.join",
            "stroke_topology": "soft_corner" if radius == "soft" else "corner_join",
            "stroke_ports": _corner_ports(params["position"]),
            "angle_degrees": None,
            "connector_sides": _corner_sides(params["position"]),
            "thickness": thickness,
            "variant": radius,
            "weight_profile": _weight_profile(thickness),
            "cap_style": "none",
            "join_style": "soft_corner" if radius == "soft" else "sharp_corner",
            "break_rhythm": "solid",
            "roughness": "clean",
            "continuity": "joined",
            "branch_count": 2,
            "dominant_angle_degrees": None,
            "entry_tangent_degrees": None if radius == "sharp" else _corner_tangents(params["position"])[0],
            "exit_tangent_degrees": None if radius == "sharp" else _corner_tangents(params["position"])[1],
            "curvature": "quarter_turn" if radius == "soft" else "hard_turn",
            "coverage": _coverage_class(thickness),
        }
    if kind == "cap":
        thickness = params.get("thickness", 1)
        return {
            "linework_package": "linework.terminal",
            "stroke_topology": "terminal_segment",
            "stroke_ports": _cap_ports(params["direction"], params["side"]),
            "angle_degrees": _angle(params["direction"]),
            "connector_sides": [params["side"]],
            "thickness": thickness,
            "variant": f"{params['direction']}_{params['side']}",
            "weight_profile": _weight_profile(thickness),
            "cap_style": "blunt",
            "join_style": "none",
            "break_rhythm": "solid",
            "roughness": "clean",
            "continuity": "terminates",
            "terminal_ports": [port for port in _cap_ports(params["direction"], params["side"]) if port["role"] == "terminal"],
            "branch_count": 1,
            "coverage": _coverage_class(thickness),
        }
    angle = _angle(params["kind"]) if params["kind"] != "cross" else None
    return {
        "linework_package": "linework.pattern",
        "stroke_topology": "repeated_strokes",
        "stroke_ports": [],
        "angle_degrees": angle,
        "connector_sides": [],
        "thickness": 1,
        "variant": params["density"],
        "weight_profile": "thin",
        "cap_style": "none",
        "join_style": "overlap" if params["kind"] == "cross" else "none",
        "break_rhythm": "patterned",
        "roughness": "clean",
        "continuity": "repeated",
        "repeat_angle_degrees": angle,
        "spacing_class": params["density"],
        "density_class": params["density"],
        "stroke_style": "clean",
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


def _line_ports(direction: str, offset: str) -> list[dict[str, str]]:
    if direction == "horizontal":
        lane = {"top": "top", "middle": "center", "bottom": "bottom"}[offset]
        return [_port("left", lane, "entry"), _port("right", lane, "exit")]
    if direction == "vertical":
        lane = {"left": "left", "center": "center", "right": "right"}[offset]
        return [_port("top", lane, "entry"), _port("bottom", lane, "exit")]
    if direction == "diagonal_rise":
        lane = {"left": "low", "middle": "center", "right": "high"}[offset]
        return [_port("left", lane, "entry"), _port("right", lane, "exit")]
    lane = {"left": "high", "middle": "center", "right": "low"}[offset]
    return [_port("left", lane, "entry"), _port("right", lane, "exit")]


def _corner_ports(position: str) -> list[dict[str, str]]:
    return {
        "top_left": [_port("top", "left", "entry"), _port("left", "top", "exit")],
        "top_right": [_port("top", "right", "entry"), _port("right", "top", "exit")],
        "bottom_left": [_port("bottom", "left", "entry"), _port("left", "bottom", "exit")],
        "bottom_right": [_port("bottom", "right", "entry"), _port("right", "bottom", "exit")],
    }[position]


def _cap_ports(direction: str, side: str) -> list[dict[str, str]]:
    if direction == "horizontal":
        role = "terminal" if side == "left" else "entry"
        other_role = "entry" if side == "left" else "terminal"
        return [_port("left", "center", role), _port("right", "center", other_role)]
    role = "terminal" if side == "top" else "entry"
    other_role = "entry" if side == "top" else "terminal"
    return [_port("top", "center", role), _port("bottom", "center", other_role)]


def _port(side: str, lane: str, role: str) -> dict[str, str]:
    return {"side": side, "lane": lane, "role": role}


def _weight_profile(thickness: int) -> str:
    return "thin" if thickness == 1 else "medium"


def _coverage_class(thickness: int) -> str:
    return "single_pixel" if thickness == 1 else "double_pixel"


def _corner_tangents(position: str) -> tuple[float, float]:
    return {
        "top_left": (0.0, 90.0),
        "top_right": (180.0, 90.0),
        "bottom_left": (0.0, 270.0),
        "bottom_right": (180.0, 270.0),
    }[position]


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
