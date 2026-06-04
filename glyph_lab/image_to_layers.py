from __future__ import annotations

from pathlib import Path
from typing import Any
import json

from .compositor import compile_layered_grid
from .image_probe import measurement_summary, probe_image
from .schema import Glyph, load_glyphs


STANDARD_PROBE_LAYERS = ["mass", "base_fill", "shadow", "highlight", "edge"]


class ProbeGlyphLookupError(ValueError):
    pass


def probe_image_to_layers(
    image_path: str | Path,
    pack_dir: str | Path,
    output_dir: str | Path,
    grid_size: int = 32,
) -> dict[str, Any]:
    pack = Path(pack_dir)
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    glyphs = load_glyphs(pack / "glyphs.json")
    tokens = required_probe_tokens(glyphs)
    probe = probe_image(image_path, grid_size, grid_size)
    layered = maps_to_layered_grid(probe, tokens)

    layered_path = out / "generated_layered_grid.json"
    measurements_path = out / "probe_measurements.json"
    _write_json(layered_path, layered)
    _write_json(measurements_path, measurement_summary(probe))
    manifest = compile_layered_grid(pack / "atlas.png", pack / "glyphs.json", layered_path, out)
    return {
        "layered_grid_path": str(layered_path),
        "measurements_path": str(measurements_path),
        "manifest": manifest,
        "measurements": measurement_summary(probe),
    }


def maps_to_layered_grid(probe: dict[str, Any], tokens: dict[str, str]) -> dict[str, Any]:
    width = probe["grid_width"]
    height = probe["grid_height"]
    mask = probe["mass_mask"]
    bands = probe["value_band_map"]
    edges = probe["edge_map"]
    layers = {name: [[" " for _ in range(width)] for _ in range(height)] for name in STANDARD_PROBE_LAYERS}

    for y in range(height):
        for x in range(width):
            if mask[y][x]:
                layers["mass"][y][x] = tokens["mass"]
                if bands[y][x] == "dark":
                    layers["shadow"][y][x] = tokens["shadow"]
                elif bands[y][x] == "light":
                    layers["highlight"][y][x] = tokens["highlight"]
                else:
                    layers["base_fill"][y][x] = tokens["base_fill"]
            if edges[y][x]["edge"]:
                layers["edge"][y][x] = tokens[f"edge_{edges[y][x]['direction']}"]

    return {
        "grid_width": width,
        "grid_height": height,
        "layers": [
            {"name": name, "grid": ["".join(row) for row in layers[name]]}
            for name in STANDARD_PROBE_LAYERS
        ],
    }


def required_probe_tokens(glyphs: list[Glyph]) -> dict[str, str]:
    return {
        "mass": _find_token(glyphs, layer="base_fill", role="fill", family="solid"),
        "base_fill": _find_token(glyphs, layer="base_fill", role="fill", family="texture"),
        "shadow": _find_token(glyphs, layer="shadow", role="shadow"),
        "highlight": _find_token(glyphs, role="highlight"),
        "edge_horizontal": _find_token(glyphs, layer="edge", role="edge", family="horizontal"),
        "edge_vertical": _find_token(glyphs, layer="edge", role="edge", family="vertical"),
        "edge_diagonal_rise": _find_token(glyphs, layer="edge", role="edge", family="diagonal", token="/"),
        "edge_diagonal_fall": _find_token(glyphs, layer="edge", role="edge", family="diagonal", token="\\"),
    }


def _find_token(
    glyphs: list[Glyph],
    layer: str | None = None,
    role: str | None = None,
    family: str | None = None,
    token: str | None = None,
) -> str:
    for glyph in glyphs:
        if layer is not None and glyph.layer != layer:
            continue
        if role is not None and glyph.role != role:
            continue
        if family is not None and glyph.family != family:
            continue
        if token is not None and glyph.token != token:
            continue
        return glyph.token
    parts = []
    if layer is not None:
        parts.append(f"layer={layer}")
    if role is not None:
        parts.append(f"role={role}")
    if family is not None:
        parts.append(f"family={family}")
    if token is not None:
        parts.append(f"token={token!r}")
    raise ProbeGlyphLookupError(f"missing required glyph for probe mapping: {', '.join(parts)}")


def _write_json(path: str | Path, payload: dict[str, Any]) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with Path(path).open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
        handle.write("\n")
