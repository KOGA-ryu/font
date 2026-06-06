from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any
import json

from PIL import Image

from .atlas import load_atlas_stamps
from .layers import default_layer_order, layer_schema, layer_sort_key, output_layer_order
from .schema import Glyph, load_glyphs
from .validate import GridValidationError, glyph_map


def compile_layered_grid(
    atlas_path: str | Path,
    glyphs_path: str | Path,
    layered_input_path: str | Path,
    output_dir: str | Path,
) -> dict[str, Any]:
    glyphs = load_glyphs(glyphs_path)
    by_token = glyph_map(glyphs)
    stamps = load_atlas_stamps(atlas_path, glyphs)
    layer_input = _load_layered_input(layered_input_path)
    layers = _validate_layered_input(layer_input, set(by_token))

    cell_size = glyphs[0].cell_size if glyphs else 4
    width = int(layer_input["grid_width"])
    height = int(layer_input["grid_height"])
    output_size = (width * cell_size, height * cell_size)
    layer_images = {
        name: Image.new("RGBA", output_size, (0, 0, 0, 0)) for name in output_layer_order()
    }
    extra_layer_images: dict[str, Image.Image] = {}
    per_layer_counts: dict[str, Counter[str]] = {}
    total_counts: Counter[str] = Counter()
    warnings: list[dict[str, Any]] = []

    for layer in sorted(layers, key=lambda item: layer_sort_key(item["name"])):
        layer_name = layer["name"]
        target = layer_images.get(layer_name)
        if target is None:
            target = extra_layer_images.setdefault(layer_name, Image.new("RGBA", output_size, (0, 0, 0, 0)))
        counts = per_layer_counts.setdefault(layer_name, Counter())
        for row_index, row in enumerate(layer["grid"], start=1):
            for column_index, token in enumerate(row, start=1):
                if token == " ":
                    continue
                glyph = by_token[token]
                point = ((column_index - 1) * cell_size, (row_index - 1) * cell_size)
                target.alpha_composite(stamps[token], point)
                counts[token] += 1
                total_counts[token] += 1
                warning = _constraint_warning(glyph, layer_name, row_index, column_index, token)
                if warning:
                    warnings.append(warning)

    proof = Image.new("RGBA", output_size, (0, 0, 0, 0))
    all_layer_images = {**layer_images, **extra_layer_images}
    for name in sorted(all_layer_images, key=layer_sort_key):
        if name == "background":
            continue
        proof.alpha_composite(all_layer_images[name], (0, 0))

    out = Path(output_dir)
    layers_dir = out / "layers"
    layers_dir.mkdir(parents=True, exist_ok=True)
    proof.save(out / "proof_128.png")
    for name in output_layer_order():
        layer_images[name].save(layers_dir / f"{name}.png")
    for name, image in extra_layer_images.items():
        image.save(layers_dir / f"{name}.png")

    manifest = {
        "input_mode": "layered",
        "input_paths": {
            "atlas": str(atlas_path),
            "glyphs": str(glyphs_path),
            "layered_control": str(layered_input_path),
        },
        "grid_width": width,
        "grid_height": height,
        "cell_size": cell_size,
        "output_size": {"width": output_size[0], "height": output_size[1]},
        "layer_order": default_layer_order(),
        "layers": layer_schema(),
        "per_layer_glyph_counts": {
            layer: dict(sorted(counts.items())) for layer, counts in sorted(per_layer_counts.items())
        },
        "glyph_counts": dict(sorted(total_counts.items())),
        "used_layers": sorted(per_layer_counts, key=layer_sort_key),
        "constraint_warnings": warnings,
        "warnings": warnings,
        "errors": [],
    }
    with (out / "manifest.json").open("w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2)
        handle.write("\n")
    return manifest


def _load_layered_input(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _validate_layered_input(data: dict[str, Any], tokens: set[str]) -> list[dict[str, Any]]:
    required = {"grid_width", "grid_height", "layers"}
    missing = required - set(data)
    if missing:
        raise GridValidationError(f"layered control missing required keys: {', '.join(sorted(missing))}")
    width = int(data["grid_width"])
    height = int(data["grid_height"])
    if width <= 0 or height <= 0:
        raise GridValidationError("layered control grid_width and grid_height must be positive")
    if not isinstance(data["layers"], list) or not data["layers"]:
        raise GridValidationError("layered control must contain at least one layer")

    layers = []
    for layer in data["layers"]:
        name = layer.get("name")
        grid = layer.get("grid")
        if not name:
            raise GridValidationError("layered control layer missing name")
        if not isinstance(grid, list):
            raise GridValidationError(f"layer {name!r} grid must be a list of rows")
        if len(grid) != height:
            raise GridValidationError(f"layer {name!r} has height {len(grid)}, expected {height}")
        for row_index, row in enumerate(grid, start=1):
            if len(row) != width:
                raise GridValidationError(
                    f"layer {name!r} row {row_index} has width {len(row)}, expected {width}"
                )
            for column_index, token in enumerate(row, start=1):
                if token != " " and token not in tokens:
                    raise GridValidationError(
                        f"unknown token in layer {name!r} at row {row_index}, column {column_index}: {token!r}"
                    )
        layers.append({"name": name, "grid": grid})
    return layers


def _constraint_warning(
    glyph: Glyph,
    layer_name: str,
    row_index: int,
    column_index: int,
    token: str,
) -> dict[str, Any] | None:
    allowed = glyph.constraints.get("allowed_layers", [])
    if layer_name in {"linework", "linework_pressure"} and any(layer in allowed for layer in ("edge", "detail")):
        return None
    if allowed and layer_name not in allowed:
        return {
            "type": "layer-constraint",
            "message": f"glyph token {token!r} used on layer {layer_name!r}, allowed layers: {allowed}",
            "layer": layer_name,
            "row": row_index,
            "column": column_index,
            "token": token,
            "glyph_id": glyph.id,
            "allowed_layers": allowed,
        }
    return None
