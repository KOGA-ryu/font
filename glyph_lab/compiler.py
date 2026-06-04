from __future__ import annotations

from collections import Counter
from pathlib import Path
import json

from PIL import Image

from .atlas import load_atlas_stamps
from .schema import EXPECTED_LAYERS, Glyph, load_glyphs
from .validate import glyph_map, read_control_grid, validate_tokens


def compile_grid(
    atlas_path: str | Path,
    glyphs_path: str | Path,
    control_grid_path: str | Path,
    output_dir: str | Path,
) -> dict:
    glyphs = load_glyphs(glyphs_path)
    by_token = glyph_map(glyphs)
    rows = read_control_grid(str(control_grid_path))
    validate_tokens(rows, set(by_token))

    cell_size = glyphs[0].cell_size if glyphs else 4
    width = len(rows[0])
    height = len(rows)
    output_size = (width * cell_size, height * cell_size)
    output = Image.new("RGBA", output_size, (0, 0, 0, 0))
    layer_images = {
        layer: Image.new("RGBA", output_size, (0, 0, 0, 0)) for layer in EXPECTED_LAYERS
    }
    stamps = load_atlas_stamps(atlas_path, glyphs)
    counts: Counter[str] = Counter()
    used_layers: set[str] = set()

    for row_index, row in enumerate(rows):
        for column_index, char in enumerate(row):
            if char == " ":
                continue
            glyph = by_token[char]
            stamp = stamps[char]
            point = (column_index * cell_size, row_index * cell_size)
            output.alpha_composite(stamp, point)
            if glyph.layer not in layer_images:
                layer_images[glyph.layer] = Image.new("RGBA", output_size, (0, 0, 0, 0))
            layer_images[glyph.layer].alpha_composite(stamp, point)
            counts[char] += 1
            used_layers.add(glyph.layer)

    out = Path(output_dir)
    layers_dir = out / "layers"
    layers_dir.mkdir(parents=True, exist_ok=True)
    output.save(out / "proof_128.png")
    for layer, image in layer_images.items():
        image.save(layers_dir / f"{layer}.png")

    manifest = {
        "input_paths": {
            "atlas": str(atlas_path),
            "glyphs": str(glyphs_path),
            "control_grid": str(control_grid_path),
        },
        "grid_width": width,
        "grid_height": height,
        "cell_size": cell_size,
        "output_size": {"width": output_size[0], "height": output_size[1]},
        "glyph_counts": dict(sorted(counts.items())),
        "used_layers": sorted(used_layers),
        "warnings": [],
        "errors": [],
    }
    with (out / "manifest.json").open("w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2)
        handle.write("\n")
    return manifest
