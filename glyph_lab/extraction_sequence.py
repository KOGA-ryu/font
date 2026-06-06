from __future__ import annotations

from pathlib import Path
from typing import Any
import json

from PIL import Image, ImageDraw

from .color_family_layers import render_color_family_layers
from .threshold_layers import DEFAULT_THRESHOLDS, parse_thresholds, render_threshold_color_layers


def render_extraction_sequence(
    image_path: str | Path,
    pack_path: str | Path,
    output_dir: str | Path,
    *,
    thresholds: str | list[int] | tuple[int, ...] = DEFAULT_THRESHOLDS,
    families: str | list[str] | tuple[str, ...] = "auto",
    grid_width: int = 128,
    grid_height: int = 128,
    fill_token: str = "#",
    glyphs_path: str | Path | None = None,
    atlas_path: str | Path | None = None,
    mapping_path: str | Path | None = None,
    background_threshold: int = 28,
    min_cell_coverage: float = 0.18,
    foreground_mode: str = "auto",
    foreground_alpha_threshold: int = 1,
    foreground_background_threshold: int | None = None,
    scale: int = 2,
) -> dict[str, Any]:
    pack = Path(pack_path)
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)

    glyphs = Path(glyphs_path) if glyphs_path is not None else _preferred_pack_file(pack, "glyphs.promoted.json", "glyphs.json")
    atlas = Path(atlas_path) if atlas_path is not None else _preferred_pack_file(pack, "atlas.promoted.png", "atlas.png")
    mapping = Path(mapping_path) if mapping_path is not None else _optional_pack_file(pack, "ascii_brush_mapping.json")
    resolved_thresholds = parse_thresholds(thresholds)
    foreground_background = foreground_background_threshold if foreground_background_threshold is not None else background_threshold

    threshold_manifest = render_threshold_color_layers(
        image_path,
        glyphs,
        atlas,
        output / "threshold_layers",
        thresholds=resolved_thresholds,
        grid_width=grid_width,
        grid_height=grid_height,
        fill_token=fill_token,
        mapping_path=mapping,
        foreground_mode=foreground_mode,
        foreground_alpha_threshold=foreground_alpha_threshold,
        foreground_background_threshold=foreground_background,
        scale=scale,
    )
    color_manifest = render_color_family_layers(
        image_path,
        glyphs,
        atlas,
        output / "color_families",
        families=families,
        grid_width=grid_width,
        grid_height=grid_height,
        fill_token=fill_token,
        mapping_path=mapping,
        background_threshold=background_threshold,
        min_cell_coverage=min_cell_coverage,
        foreground_mode=foreground_mode,
        foreground_alpha_threshold=foreground_alpha_threshold,
        foreground_background_threshold=foreground_background,
        scale=scale,
    )

    report = {
        "source_image": str(image_path),
        "pack": str(pack),
        "glyphs": str(glyphs),
        "atlas": str(atlas),
        "mapping": str(mapping) if mapping is not None else None,
        "grid_width": grid_width,
        "grid_height": grid_height,
        "fill_token": fill_token,
        "foreground_mode": foreground_mode,
        "foreground_alpha_threshold": foreground_alpha_threshold,
        "foreground_background_threshold": foreground_background,
        "threshold_layers": {
            "directory": str(output / "threshold_layers"),
            "manifest": str(output / "threshold_layers" / "manifest.json"),
            "contact_sheet": threshold_manifest["contact_sheet"],
            "stacked": threshold_manifest["stacked"],
            "foreground": threshold_manifest["foreground"],
            "layers": [
                {
                    "threshold": layer["threshold"],
                    "luminance_range": layer["luminance_range"],
                    "delta_cells": layer["delta_cells"],
                    "colorized_layer": layer["colorized_layer"],
                }
                for layer in threshold_manifest["layers"]
            ],
        },
        "color_families": {
            "directory": str(output / "color_families"),
            "manifest": str(output / "color_families" / "manifest.json"),
            "contact_sheet": color_manifest["contact_sheet"],
            "stacked": color_manifest["stacked"],
            "foreground": color_manifest["foreground"],
            "stack_order": color_manifest["stack_order"],
            "layers": [
                {
                    "family": layer["family"],
                    "cells": layer["cells"],
                    "average_hex": layer["average_hex"],
                    "colorized_layer": layer["colorized_layer"],
                }
                for layer in color_manifest["layers"]
            ],
        },
        "rule": (
            "run foreground evidence first, split dark value bands with threshold deltas, "
            "split hue/saturation/luminance families, then color every kept glyph cell from the source image"
        ),
    }
    contact_sheet = output / "sequence_contact_sheet.png"
    _write_sequence_contact_sheet(image_path, report, contact_sheet)
    report["contact_sheet"] = str(contact_sheet)
    report_path = output / "sequence_report.json"
    _write_json(report_path, report)
    return report


def _write_sequence_contact_sheet(image_path: str | Path, report: dict[str, Any], output_path: str | Path) -> None:
    thumb = 260
    pad = 14
    label_h = 42
    cells = [
        ("original", str(image_path), ""),
        ("threshold stack", report["threshold_layers"]["stacked"], _threshold_summary(report)),
        ("color stack", report["color_families"]["stacked"], _family_summary(report)),
        ("foreground mask", report["threshold_layers"]["foreground"]["mask"], _foreground_summary(report)),
        ("threshold sheet", report["threshold_layers"]["contact_sheet"], ""),
        ("color family sheet", report["color_families"]["contact_sheet"], ""),
    ]
    columns = 3
    rows = 2
    sheet = Image.new("RGB", (pad + columns * (thumb + pad), pad + rows * (thumb + label_h + pad)), "white")
    draw = ImageDraw.Draw(sheet)
    for index, (label, path, subtitle) in enumerate(cells):
        column = index % columns
        row = index // columns
        x = pad + column * (thumb + pad)
        y = pad + row * (thumb + label_h + pad)
        draw.text((x, y), label, fill="black")
        if subtitle:
            draw.text((x, y + 16), subtitle[:52], fill="black")
        with Image.open(path) as image:
            view = image.convert("RGB")
            view.thumbnail((thumb, thumb), Image.Resampling.NEAREST)
            canvas = Image.new("RGB", (thumb, thumb), "white")
            canvas.paste(view, ((thumb - view.width) // 2, (thumb - view.height) // 2))
            sheet.paste(canvas, (x, y + label_h))
        draw.rectangle([x, y + label_h, x + thumb - 1, y + label_h + thumb - 1], outline=(210, 210, 210))
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output)


def _threshold_summary(report: dict[str, Any]) -> str:
    counts = [f"t{layer['threshold']}:{layer['delta_cells']}" for layer in report["threshold_layers"]["layers"]]
    return " ".join(counts[:4])


def _family_summary(report: dict[str, Any]) -> str:
    layers = [layer for layer in report["color_families"]["layers"] if layer["cells"] > 0]
    return " ".join(f"{layer['family']}:{layer['cells']}" for layer in layers[:3])


def _foreground_summary(report: dict[str, Any]) -> str:
    foreground = report["threshold_layers"]["foreground"]
    return f"{foreground['mode']} kept {foreground['kept_cells']}"


def _preferred_pack_file(pack: Path, preferred_name: str, fallback_name: str) -> Path:
    preferred = pack / preferred_name
    return preferred if preferred.exists() else pack / fallback_name


def _optional_pack_file(pack: Path, name: str) -> Path | None:
    path = pack / name
    return path if path.exists() else None


def _write_json(path: str | Path, payload: dict[str, Any]) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
