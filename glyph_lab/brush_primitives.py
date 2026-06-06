from __future__ import annotations

import random
from typing import Any

from PIL import Image

from .primitives import INK
from .schema import CELL_SIZE


BRUSH_FAMILIES = {
    "hatch",
    "crosshatch",
    "stipple",
    "spray",
    "charcoal",
    "dry_brush",
    "charcoal_drag",
    "grain",
    "scratch",
    "chip",
    "tone_hatch",
    "dot_field",
    "edge_wear",
}


def brush_stamp(
    brush_family: str,
    color: tuple[int, int, int, int] = INK,
    **params: Any,
) -> Image.Image:
    _require_choice("brush_family", brush_family, BRUSH_FAMILIES)
    if brush_family == "hatch":
        return hatch(**params, color=color)
    if brush_family == "crosshatch":
        return crosshatch(**params, color=color)
    if brush_family == "stipple":
        return stipple(**params, color=color)
    if brush_family == "spray":
        return spray(**params, color=color)
    if brush_family == "charcoal":
        return charcoal(**params, color=color)
    if brush_family == "dry_brush":
        return dry_brush(**params, color=color)
    if brush_family == "charcoal_drag":
        return charcoal_drag(**params, color=color)
    if brush_family == "scratch":
        return scratch(**params, color=color)
    if brush_family == "chip":
        return chip(**params, color=color)
    if brush_family == "tone_hatch":
        return tone_hatch(**params, color=color)
    if brush_family == "dot_field":
        return dot_field(**params, color=color)
    if brush_family == "edge_wear":
        return edge_wear(**params, color=color)
    return grain(**params, color=color)


def hatch(
    angle: str,
    density: str = "light",
    broken: bool = False,
    color: tuple[int, int, int, int] = INK,
) -> Image.Image:
    _require_choice("angle", angle, {"horizontal", "vertical", "diagonal_rise", "diagonal_fall"})
    _require_choice("density", density, {"light", "medium", "dense"})
    if angle == "horizontal":
        rows = {"light": {1}, "medium": {0, 2}, "dense": {0, 1, 3}}[density]
        coords = {(x, y) for y in rows for x in range(CELL_SIZE)}
    elif angle == "vertical":
        cols = {"light": {1}, "medium": {0, 2}, "dense": {0, 1, 3}}[density]
        coords = {(x, y) for x in cols for y in range(CELL_SIZE)}
    elif angle == "diagonal_rise":
        bands = {"light": {3}, "medium": {1, 3}, "dense": {1, 2, 3}}[density]
        coords = {(x, y) for y in range(CELL_SIZE) for x in range(CELL_SIZE) if x + y in bands}
    else:
        bands = {"light": {0}, "medium": {-2, 0}, "dense": {-1, 0, 1}}[density]
        coords = {(x, y) for y in range(CELL_SIZE) for x in range(CELL_SIZE) if x - y in bands}
    if broken:
        coords = {coord for coord in coords if (coord[0] + coord[1]) % 3 != 1}
    return _stamp(sorted(coords), color)


def crosshatch(
    style: str = "x",
    density: str = "medium",
    color: tuple[int, int, int, int] = INK,
) -> Image.Image:
    _require_choice("style", style, {"x", "grid", "uneven"})
    _require_choice("density", density, {"light", "medium", "dense"})
    if style == "x":
        coords = _coords(hatch("diagonal_rise", density)) | _coords(hatch("diagonal_fall", density))
    elif style == "grid":
        coords = _coords(hatch("horizontal", density)) | _coords(hatch("vertical", density))
    else:
        coords = _coords(hatch("diagonal_rise", "medium")) | {(0, 0), (3, 1), (1, 3)}
        if density == "dense":
            coords |= _coords(hatch("horizontal", "light"))
        elif density == "light":
            coords = {coord for coord in coords if coord not in {(3, 1), (1, 3)}}
    return _stamp(sorted(coords), color)


def stipple(
    density: str = "sparse",
    seed: int = 0,
    color: tuple[int, int, int, int] = INK,
) -> Image.Image:
    _require_choice("density", density, {"sparse", "cluster", "dense"})
    patterns = {
        "sparse": [(0, 0), (2, 1), (1, 3)],
        "cluster": [(1, 1), (2, 1), (1, 2), (2, 2)],
    }
    if density in patterns:
        coords = patterns[density]
    else:
        rng = random.Random(seed)
        coords = [(x, y) for y in range(CELL_SIZE) for x in range(CELL_SIZE) if rng.random() < 0.55]
    return _stamp(coords, color)


def spray(
    density: str = "medium",
    seed: int = 0,
    direction: str = "even",
    color: tuple[int, int, int, int] = INK,
) -> Image.Image:
    _require_choice("density", density, {"light", "medium", "dense"})
    _require_choice("direction", direction, {"even", "left", "right", "top", "bottom"})
    threshold = {"light": 0.25, "medium": 0.45, "dense": 0.68}[density]
    rng = random.Random(seed)
    coords = []
    for y in range(CELL_SIZE):
        for x in range(CELL_SIZE):
            bias = _direction_bias(x, y, direction)
            if rng.random() < threshold * bias:
                coords.append((x, y))
    return _stamp(coords, color)


def charcoal(
    edge: str = "left",
    roughness: str = "medium",
    color: tuple[int, int, int, int] = INK,
) -> Image.Image:
    _require_choice("edge", edge, {"left", "right", "top", "bottom", "chunk"})
    _require_choice("roughness", roughness, {"light", "medium", "heavy"})
    if edge == "chunk":
        coords = {(0, 1), (1, 1), (1, 2), (2, 2), (3, 3)}
    elif edge in {"left", "right"}:
        col = 0 if edge == "left" else 3
        coords = {(col, y) for y in range(CELL_SIZE)}
        if roughness in {"medium", "heavy"}:
            near = 1 if edge == "left" else 2
            coords |= {(near, 0), (near, 2)}
        if roughness == "heavy":
            coords |= {(near, 3), (col, 1)}
    else:
        row = 0 if edge == "top" else 3
        coords = {(x, row) for x in range(CELL_SIZE)}
        if roughness in {"medium", "heavy"}:
            near = 1 if edge == "top" else 2
            coords |= {(0, near), (2, near)}
        if roughness == "heavy":
            coords |= {(3, near), (1, row)}
    return _stamp(sorted(coords), color)


def dry_brush(
    direction: str = "horizontal",
    coverage: str = "medium",
    color: tuple[int, int, int, int] = INK,
) -> Image.Image:
    _require_choice("direction", direction, {"horizontal", "vertical", "diagonal_rise", "diagonal_fall"})
    _require_choice("coverage", coverage, {"light", "medium", "heavy"})
    base = _coords(hatch(direction, {"light": "light", "medium": "medium", "heavy": "dense"}[coverage], broken=True))
    gaps = {
        "light": {(1, 1), (2, 2), (3, 0)},
        "medium": {(1, 0), (2, 3)},
        "heavy": {(3, 3)},
    }[coverage]
    return _stamp(sorted(base - gaps), color)


def charcoal_drag(
    direction: str = "horizontal",
    pressure: str = "medium",
    color: tuple[int, int, int, int] = INK,
) -> Image.Image:
    _require_choice("direction", direction, {"horizontal", "vertical", "diagonal_rise", "diagonal_fall", "smudge"})
    _require_choice("pressure", pressure, {"light", "medium", "heavy"})
    if direction == "horizontal":
        coords = {(0, 1), (1, 1), (2, 1)}
        if pressure in {"medium", "heavy"}:
            coords |= {(0, 2), (1, 2)}
        if pressure == "heavy":
            coords |= {(2, 2), (3, 1)}
    elif direction == "vertical":
        coords = {(1, 0), (1, 1), (1, 2)}
        if pressure in {"medium", "heavy"}:
            coords |= {(2, 0), (2, 1)}
        if pressure == "heavy":
            coords |= {(2, 2), (1, 3)}
    elif direction == "diagonal_rise":
        coords = {(0, 3), (1, 2), (2, 1)}
        if pressure in {"medium", "heavy"}:
            coords |= {(1, 3), (2, 2)}
        if pressure == "heavy":
            coords |= {(3, 0), (3, 1)}
    elif direction == "diagonal_fall":
        coords = {(0, 0), (1, 1), (2, 2)}
        if pressure in {"medium", "heavy"}:
            coords |= {(1, 0), (2, 1)}
        if pressure == "heavy":
            coords |= {(3, 2), (3, 3)}
    else:
        coords = {(1, 1), (2, 1), (1, 2), (2, 2)}
        if pressure == "light":
            coords = {(1, 1), (2, 2)}
        elif pressure == "heavy":
            coords |= {(0, 1), (1, 0), (2, 3), (3, 2)}
    return _stamp(sorted(coords), color)


def grain(
    kind: str = "paper",
    seed: int = 0,
    color: tuple[int, int, int, int] = INK,
) -> Image.Image:
    _require_choice("kind", kind, {"paper", "noise", "fibers", "checker"})
    if kind == "paper":
        coords = [(0, 0), (3, 0), (1, 1), (2, 2), (0, 3)]
    elif kind == "fibers":
        coords = [(0, 1), (1, 1), (3, 1), (1, 3), (2, 3)]
    elif kind == "checker":
        coords = [(x, y) for y in range(CELL_SIZE) for x in range(CELL_SIZE) if (x + y) % 2 == 0]
    else:
        rng = random.Random(seed)
        coords = [(x, y) for y in range(CELL_SIZE) for x in range(CELL_SIZE) if rng.random() < 0.38]
    return _stamp(coords, color)


def scratch(
    direction: str = "horizontal",
    length: str = "short",
    broken: bool = False,
    color: tuple[int, int, int, int] = INK,
) -> Image.Image:
    _require_choice("direction", direction, {"horizontal", "vertical", "diagonal_rise", "diagonal_fall"})
    _require_choice("length", length, {"short", "long"})
    if direction == "horizontal":
        coords = {(1, 1), (2, 1)} if length == "short" else {(0, 1), (1, 1), (2, 1), (3, 1)}
    elif direction == "vertical":
        coords = {(1, 1), (1, 2)} if length == "short" else {(1, 0), (1, 1), (1, 2), (1, 3)}
    elif direction == "diagonal_rise":
        coords = {(1, 2), (2, 1)} if length == "short" else {(0, 3), (1, 2), (2, 1), (3, 0)}
    else:
        coords = {(1, 1), (2, 2)} if length == "short" else {(0, 0), (1, 1), (2, 2), (3, 3)}
    if broken:
        coords = _broken_scratch_coords(direction, coords)
    return _stamp(sorted(coords), color)


def chip(
    edge: str = "left",
    size: str = "small",
    color: tuple[int, int, int, int] = INK,
) -> Image.Image:
    _require_choice("edge", edge, {"left", "right", "top", "bottom", "corner_top_left", "corner_bottom_right"})
    _require_choice("size", size, {"small", "medium", "large"})
    coords = {
        "left": {(0, 1), (0, 2), (1, 1)},
        "right": {(3, 1), (3, 2), (2, 2)},
        "top": {(1, 0), (2, 0), (1, 1)},
        "bottom": {(1, 3), (2, 3), (2, 2)},
        "corner_top_left": {(0, 0), (1, 0), (0, 1)},
        "corner_bottom_right": {(3, 3), (2, 3), (3, 2)},
    }[edge]
    if size in {"medium", "large"}:
        coords |= {
            "left": {(1, 2)},
            "right": {(2, 1)},
            "top": {(2, 1)},
            "bottom": {(1, 2)},
            "corner_top_left": {(1, 1)},
            "corner_bottom_right": {(2, 2)},
        }[edge]
    if size == "large":
        coords |= {
            "left": {(0, 3), (2, 1)},
            "right": {(3, 0), (1, 2)},
            "top": {(3, 0), (1, 2)},
            "bottom": {(0, 3), (2, 1)},
            "corner_top_left": {(2, 0), (0, 2)},
            "corner_bottom_right": {(1, 3), (3, 1)},
        }[edge]
    return _stamp(sorted(coords), color)


def tone_hatch(
    pattern: str = "gradient_left",
    color: tuple[int, int, int, int] = INK,
) -> Image.Image:
    _require_choice(
        "pattern",
        pattern,
        {
            "gradient_left",
            "gradient_right",
            "gradient_top",
            "gradient_bottom",
            "corner_top_left",
            "corner_bottom_right",
            "contour_rise",
            "contour_fall",
            "parallel_staggered",
            "woven",
        },
    )
    coords = {
        "gradient_left": {(0, y) for y in range(CELL_SIZE)} | {(1, 0), (1, 2)},
        "gradient_right": {(3, y) for y in range(CELL_SIZE)} | {(2, 1), (2, 3)},
        "gradient_top": {(x, 0) for x in range(CELL_SIZE)} | {(0, 1), (2, 1)},
        "gradient_bottom": {(x, 3) for x in range(CELL_SIZE)} | {(1, 2), (3, 2)},
        "corner_top_left": {(0, 0), (1, 0), (2, 0), (0, 1), (1, 1), (0, 2)},
        "corner_bottom_right": {(3, 3), (2, 3), (1, 3), (3, 2), (2, 2), (3, 1)},
        "contour_rise": {(0, 3), (1, 3), (1, 2), (2, 2), (2, 1), (3, 1)},
        "contour_fall": {(0, 0), (1, 0), (1, 1), (2, 1), (2, 2), (3, 2)},
        "parallel_staggered": {(0, 0), (1, 0), (2, 1), (3, 1), (0, 3), (1, 3)},
        "woven": {(0, 0), (2, 0), (1, 1), (3, 1), (0, 2), (2, 2), (1, 3), (3, 3)},
    }[pattern]
    return _stamp(sorted(coords), color)


def dot_field(
    pattern: str = "dust_light",
    color: tuple[int, int, int, int] = INK,
) -> Image.Image:
    _require_choice(
        "pattern",
        pattern,
        {
            "dust_light",
            "dust_medium",
            "dust_dense",
            "speckle_even",
            "speckle_cluster_left",
            "speckle_cluster_right",
            "spray_corner_top_left",
            "spray_corner_bottom_right",
            "pitted_surface",
            "scattered_large",
        },
    )
    coords = {
        "dust_light": {(0, 1), (3, 2)},
        "dust_medium": {(0, 0), (2, 1), (1, 2), (3, 3)},
        "dust_dense": {(0, 0), (2, 0), (1, 1), (3, 1), (0, 3), (2, 3)},
        "speckle_even": {(0, 0), (3, 0), (1, 1), (2, 2), (0, 3), (3, 3)},
        "speckle_cluster_left": {(0, 0), (1, 0), (0, 1), (1, 2), (0, 3)},
        "speckle_cluster_right": {(3, 0), (2, 1), (3, 1), (2, 3), (3, 3)},
        "spray_corner_top_left": {(0, 0), (1, 0), (0, 1), (2, 1), (1, 2)},
        "spray_corner_bottom_right": {(3, 3), (2, 3), (3, 2), (1, 2), (2, 1)},
        "pitted_surface": {(0, 0), (2, 0), (1, 1), (3, 2), (0, 3), (2, 3), (3, 3)},
        "scattered_large": {(0, 0), (3, 0), (2, 1), (0, 2), (1, 3), (3, 3)},
    }[pattern]
    return _stamp(sorted(coords), color)


def edge_wear(
    side: str = "left",
    wear: str = "nick",
    color: tuple[int, int, int, int] = INK,
) -> Image.Image:
    _require_choice("side", side, {"left", "right", "top", "bottom", "corner_top_left", "corner_bottom_right"})
    _require_choice("wear", wear, {"nick", "rubbed", "broken"})
    if side == "left":
        coords = {
            "nick": {(0, 1), (1, 1)},
            "rubbed": {(0, 0), (0, 1), (1, 1), (0, 3)},
            "broken": {(0, 0), (1, 0), (0, 2), (1, 3)},
        }[wear]
    elif side == "right":
        coords = {
            "nick": {(3, 2), (2, 2)},
            "rubbed": {(3, 0), (3, 2), (2, 2), (3, 3)},
            "broken": {(3, 0), (2, 1), (3, 2), (2, 3)},
        }[wear]
    elif side == "top":
        coords = {
            "nick": {(1, 0), (1, 1)},
            "rubbed": {(0, 0), (1, 0), (1, 1), (3, 0)},
            "broken": {(0, 0), (1, 1), (2, 0), (3, 1)},
        }[wear]
    elif side == "bottom":
        coords = {
            "nick": {(2, 3), (2, 2)},
            "rubbed": {(0, 3), (2, 3), (2, 2), (3, 3)},
            "broken": {(0, 2), (1, 3), (2, 2), (3, 3)},
        }[wear]
    elif side == "corner_top_left":
        coords = {
            "nick": {(0, 0), (1, 0), (0, 1)},
            "rubbed": {(0, 0), (1, 0), (0, 1), (2, 0)},
            "broken": {(0, 0), (1, 0), (0, 1), (2, 1), (1, 2)},
        }[wear]
    else:
        coords = {
            "nick": {(3, 3), (2, 3), (3, 2)},
            "rubbed": {(3, 3), (2, 3), (3, 2), (1, 3)},
            "broken": {(3, 3), (2, 3), (3, 2), (1, 2), (2, 1)},
        }[wear]
    return _stamp(sorted(coords), color)


def default_brush_specs() -> list[dict[str, Any]]:
    specs = []
    for angle in ("horizontal", "vertical", "diagonal_rise", "diagonal_fall"):
        for density in ("light", "medium", "dense"):
            specs.append(_spec("hatch", f"hatch_{angle}_{density}", {"angle": angle, "density": density}))
            specs.append(_spec("hatch", f"hatch_{angle}_{density}_broken", {"angle": angle, "density": density, "broken": True}))
    for style in ("x", "grid", "uneven"):
        for density in ("light", "medium", "dense"):
            specs.append(_spec("crosshatch", f"crosshatch_{style}_{density}", {"style": style, "density": density}))
    for density in ("sparse", "cluster", "dense"):
        specs.append(_spec("stipple", f"stipple_{density}", {"density": density, "seed": 11}, family="spray"))
    for direction in ("even", "left", "right", "top", "bottom"):
        for density in ("light", "medium", "dense"):
            specs.append(_spec("spray", f"spray_{direction}_{density}", {"direction": direction, "density": density, "seed": 17}, family="spray"))
    for edge in ("left", "right", "top", "bottom", "chunk"):
        for roughness in ("light", "medium", "heavy"):
            specs.append(_spec("charcoal", f"charcoal_{edge}_{roughness}", {"edge": edge, "roughness": roughness}, family="charcoal"))
    for direction in ("horizontal", "vertical", "diagonal_rise", "diagonal_fall"):
        for coverage in ("light", "medium", "heavy"):
            specs.append(_spec("dry_brush", f"dry_brush_{direction}_{coverage}", {"direction": direction, "coverage": coverage}, family="dry_brush"))
    for kind in ("paper", "noise", "fibers", "checker"):
        specs.append(_spec("grain", f"grain_{kind}", {"kind": kind, "seed": 23}, family="grain"))
    for direction in ("horizontal", "vertical", "diagonal_rise", "diagonal_fall"):
        for length in ("short", "long"):
            specs.append(
                _spec(
                    "scratch",
                    f"scratch_{direction}_{length}",
                    {"direction": direction, "length": length},
                    family="damage",
                )
            )
            specs.append(
                _spec(
                    "scratch",
                    f"scratch_{direction}_{length}_broken",
                    {"direction": direction, "length": length, "broken": True},
                    family="damage",
                )
            )
    for edge in ("left", "right", "top", "bottom", "corner_top_left", "corner_bottom_right"):
        for size in ("small", "medium", "large"):
            specs.append(_spec("chip", f"chip_{edge}_{size}", {"edge": edge, "size": size}, family="damage"))
    for pattern in (
        "gradient_left",
        "gradient_right",
        "gradient_top",
        "gradient_bottom",
        "corner_top_left",
        "corner_bottom_right",
        "contour_rise",
        "contour_fall",
        "parallel_staggered",
        "woven",
    ):
        specs.append(_spec("tone_hatch", f"tone_hatch_{pattern}", {"pattern": pattern}, family="texture"))
    for pattern in (
        "dust_light",
        "dust_medium",
        "dust_dense",
        "speckle_even",
        "speckle_cluster_left",
        "speckle_cluster_right",
        "spray_corner_top_left",
        "spray_corner_bottom_right",
        "pitted_surface",
        "scattered_large",
    ):
        specs.append(_spec("dot_field", f"dot_field_{pattern}", {"pattern": pattern}, family="texture"))
    for direction in ("horizontal", "vertical", "diagonal_rise", "diagonal_fall", "smudge"):
        for pressure in ("light", "medium", "heavy"):
            specs.append(
                _spec(
                    "charcoal_drag",
                    f"charcoal_drag_{direction}_{pressure}",
                    {"direction": direction, "pressure": pressure},
                    family="charcoal",
                )
            )
    for side in ("left", "right", "top", "bottom", "corner_top_left", "corner_bottom_right"):
        for wear in ("nick", "rubbed", "broken"):
            specs.append(_spec("edge_wear", f"edge_wear_{side}_{wear}", {"side": side, "wear": wear}, family="damage"))
    return specs


def brush_metadata(spec: dict[str, Any]) -> dict[str, Any]:
    params = spec["params"]
    return {
        "brush_family": spec["brush_family"],
        "brush_params": params,
        "brush_engine": _engine_for(spec["brush_family"]),
        "density_class": (
            params.get("density")
            or params.get("coverage")
            or params.get("roughness")
            or params.get("pressure")
            or params.get("kind")
            or params.get("length")
            or params.get("size")
            or params.get("pattern")
            or params.get("wear")
        ),
        "ascii_fallback": _fallback_for(spec),
    }


def _spec(
    brush_family: str,
    name: str,
    params: dict[str, Any],
    role: str = "detail",
    family: str = "texture",
    layer: str = "detail",
    palette_role: str = "crack",
) -> dict[str, Any]:
    return {
        "brush_family": brush_family,
        "name": name,
        "params": params,
        "role": role,
        "family": family,
        "layer": layer,
        "palette_role": palette_role,
    }


def _engine_for(brush_family: str) -> str:
    if brush_family in {"stipple", "spray"}:
        return "scatter"
    if brush_family == "charcoal_drag":
        return "charcoal-drag"
    if brush_family in {"charcoal", "dry_brush"}:
        return "broken-stroke"
    if brush_family == "scratch":
        return "incised-mark"
    if brush_family == "chip":
        return "edge-damage"
    if brush_family == "tone_hatch":
        return "tone-hatch"
    if brush_family == "dot_field":
        return "dot-field"
    if brush_family == "edge_wear":
        return "edge-wear"
    if brush_family in {"hatch", "crosshatch"}:
        return "directional-stroke"
    return "grain"


def _fallback_for(spec: dict[str, Any]) -> str:
    family = spec["brush_family"]
    params = spec["params"]
    if family in {"hatch", "dry_brush", "scratch", "charcoal_drag"}:
        angle = params.get("angle") or params.get("direction")
        return {"horizontal": "-", "vertical": "|", "diagonal_rise": "/", "diagonal_fall": "\\"}.get(angle, "x")
    if family == "crosshatch":
        return "+"
    if family in {"stipple", "spray", "grain", "dot_field"}:
        return "*"
    if family in {"chip", "edge_wear"}:
        return "x"
    if family == "tone_hatch":
        return "+"
    return "x"


def _direction_bias(x: int, y: int, direction: str) -> float:
    if direction == "left":
        return 1.15 if x < 2 else 0.65
    if direction == "right":
        return 1.15 if x >= 2 else 0.65
    if direction == "top":
        return 1.15 if y < 2 else 0.65
    if direction == "bottom":
        return 1.15 if y >= 2 else 0.65
    return 1.0


def _coords(stamp: Image.Image) -> set[tuple[int, int]]:
    pixels = stamp.load()
    return {(x, y) for y in range(CELL_SIZE) for x in range(CELL_SIZE) if pixels[x, y][3] > 0}


def _broken_scratch_coords(direction: str, coords: set[tuple[int, int]]) -> set[tuple[int, int]]:
    if len(coords) <= 2:
        return {coord for index, coord in enumerate(sorted(coords)) if index == 0}
    if direction == "horizontal":
        return {coord for coord in coords if coord[0] != 2}
    if direction == "vertical":
        return {coord for coord in coords if coord[1] != 2}
    return {coord for index, coord in enumerate(sorted(coords)) if index != 2}


def _stamp(coords: list[tuple[int, int]] | set[tuple[int, int]], color: tuple[int, int, int, int]) -> Image.Image:
    image = Image.new("RGBA", (CELL_SIZE, CELL_SIZE), (0, 0, 0, 0))
    pixels = image.load()
    for x, y in coords:
        if 0 <= x < CELL_SIZE and 0 <= y < CELL_SIZE:
            pixels[x, y] = color
    return image


def _require_choice(name: str, value: Any, choices: set[Any]) -> None:
    if value not in choices:
        options = ", ".join(str(choice) for choice in sorted(choices))
        raise ValueError(f"{name} must be one of {options}, got {value!r}")
