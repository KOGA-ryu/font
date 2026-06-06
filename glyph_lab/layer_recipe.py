from __future__ import annotations

from pathlib import Path
from typing import Any
import json

from PIL import Image

from .ascii_glyph_renderer import render_ascii_glyphs


def render_layer_recipe(recipe_path: str | Path, output_dir: str | Path) -> dict[str, Any]:
    recipe_file = Path(recipe_path)
    recipe = _load_json(recipe_file)
    root = recipe_file.parent
    output = Path(output_dir)
    layers_dir = output / "layers"
    masks_dir = output / "masks"
    composites_dir = output / "composites"
    layers_dir.mkdir(parents=True, exist_ok=True)
    masks_dir.mkdir(parents=True, exist_ok=True)
    composites_dir.mkdir(parents=True, exist_ok=True)

    defaults = recipe.get("defaults", {})
    layer_results: dict[str, dict[str, Any]] = {}
    manifest_layers = []
    for layer in recipe.get("layers", []):
        name = _required_name(layer)
        layer_output = layers_dir / f"{name}.png"
        mask_output = masks_dir / f"{name}_mask.png"
        render_args = _render_args(defaults, layer, root)
        result = render_ascii_glyphs(
            render_args["ascii"],
            render_args["glyphs"],
            render_args["atlas"],
            layer_output,
            mapping_path=render_args.get("mapping"),
            gate_image_path=render_args.get("gate_image"),
            gate_mode=render_args.get("gate_mode", "border-difference"),
            gate_threshold=render_args.get("gate_threshold", 32),
            gate_dilate=render_args.get("gate_dilate", 1),
            gate_mask_output_path=mask_output if render_args.get("gate_image") else None,
            gate_samples_path=render_args.get("gate_samples"),
            gate_samples_key=render_args.get("gate_sample_key", "eyedropper_samples"),
            gate_include_boxes=render_args.get("gate_include_boxes"),
            gate_fill_token=render_args.get("gate_fill_token"),
            ink_mode=render_args.get("ink_mode", "atlas"),
            ink_color=render_args.get("ink_color"),
            ink_sample_radius=render_args.get("ink_sample_radius", 6),
            ink_ignore_luminance=render_args.get("ink_ignore_luminance", 40),
            ink_palette_threshold=render_args.get("ink_palette_threshold"),
            scale=render_args.get("scale", 4),
        )
        layer_results[name] = {
            "path": str(layer_output),
            "mask": str(mask_output) if render_args.get("gate_image") else None,
            "result": result,
        }
        manifest_layers.append(
            {
                "name": name,
                "path": str(layer_output),
                "mask": str(mask_output) if render_args.get("gate_image") else None,
                "gate": result.get("gate"),
                "ink": result.get("ink"),
            }
        )

    manifest_composites = []
    for composite in recipe.get("composites", []):
        name = _required_name(composite)
        base_name = composite.get("base")
        if base_name not in layer_results:
            raise ValueError(f"composite {name!r} references unknown base layer {base_name!r}")
        overlay_names = composite.get("overlays", [])
        if not isinstance(overlay_names, list):
            raise ValueError(f"composite {name!r} overlays must be a list")
        composite_output = composites_dir / f"{name}.png"
        _write_composite(layer_results[base_name], [layer_results[_require_layer(layer_results, layer)] for layer in overlay_names], composite_output)
        manifest_composites.append(
            {
                "name": name,
                "base": base_name,
                "overlays": overlay_names,
                "path": str(composite_output),
            }
        )

    manifest = {
        "recipe": str(recipe_file),
        "output_dir": str(output),
        "layers": manifest_layers,
        "composites": manifest_composites,
    }
    _write_json(output / "manifest.json", manifest)
    return manifest


def _render_args(defaults: dict[str, Any], layer: dict[str, Any], root: Path) -> dict[str, Any]:
    args = dict(defaults)
    args.update(layer)
    for key in ("ascii", "glyphs", "atlas", "mapping", "gate_image", "gate_samples"):
        if args.get(key):
            args[key] = _resolve(root, args[key])
    if "gate_include_box" in args and "gate_include_boxes" not in args:
        args["gate_include_boxes"] = [args["gate_include_box"]]
    if args.get("gate_include_boxes") is not None:
        args["gate_include_boxes"] = [_parse_box(box) for box in args["gate_include_boxes"]]
    return args


def _write_composite(base: dict[str, Any], overlays: list[dict[str, Any]], output_path: Path) -> None:
    image = Image.open(base["path"]).convert("RGBA")
    for overlay in overlays:
        overlay_image = Image.open(overlay["path"]).convert("RGBA")
        if overlay_image.size != image.size:
            overlay_image = overlay_image.resize(image.size, Image.Resampling.NEAREST)
        mask_path = overlay.get("mask")
        if mask_path is None:
            mask = overlay_image.split()[3]
        else:
            mask = Image.open(mask_path).convert("L")
            if mask.size != image.size:
                mask = mask.resize(image.size, Image.Resampling.NEAREST)
        image = Image.composite(overlay_image, image, mask)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_path)


def _parse_box(value: Any) -> tuple[int, int, int, int]:
    if isinstance(value, str):
        parts = value.split(",")
    elif isinstance(value, list | tuple):
        parts = value
    else:
        raise ValueError(f"gate include box must be x0,y0,x1,y1, got {value!r}")
    if len(parts) != 4:
        raise ValueError(f"gate include box must be x0,y0,x1,y1, got {value!r}")
    try:
        x0, y0, x1, y1 = (int(part) for part in parts)
    except ValueError as exc:
        raise ValueError(f"gate include box values must be integers, got {value!r}") from exc
    if x0 < 0 or y0 < 0 or x1 <= x0 or y1 <= y0:
        raise ValueError(f"gate include box must have positive size, got {value!r}")
    return x0, y0, x1, y1


def _resolve(root: Path, value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def _required_name(payload: dict[str, Any]) -> str:
    name = payload.get("name")
    if not isinstance(name, str) or not name:
        raise ValueError("layer/composite requires a non-empty name")
    return name


def _require_layer(layer_results: dict[str, dict[str, Any]], name: str) -> str:
    if name not in layer_results:
        raise ValueError(f"composite references unknown overlay layer {name!r}")
    return name


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
        handle.write("\n")
