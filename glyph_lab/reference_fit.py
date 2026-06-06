from __future__ import annotations

from pathlib import Path
from typing import Any
import json

from PIL import Image, ImageDraw, ImageFont

from .foreground_mask import FOREGROUND_MODES, foreground_mask


def fit_reference_to_mannequin(
    reference_image_path: str | Path,
    mannequin_path: str | Path,
    output_path: str | Path,
    *,
    foreground_mode: str = "auto",
    foreground_alpha_threshold: int = 1,
    foreground_background_threshold: int = 28,
    target_padding: int = 0,
    contact_scale: int = 1,
) -> dict[str, Any]:
    if foreground_mode not in FOREGROUND_MODES:
        raise ValueError(f"unknown foreground mode {foreground_mode!r}; expected one of {sorted(FOREGROUND_MODES)}")
    if target_padding < 0:
        raise ValueError("target padding must be non-negative")
    if contact_scale < 1:
        raise ValueError("contact scale must be at least 1")

    output = Path(output_path)
    output.mkdir(parents=True, exist_ok=True)
    recipe_path = Path(mannequin_path)
    recipe = _load_json(recipe_path)
    width = int(recipe.get("grid", {}).get("width", 0))
    height = int(recipe.get("grid", {}).get("height", 0))
    if width <= 0 or height <= 0:
        raise ValueError("mannequin recipe must include positive grid width and height")

    mannequin_base = _render_mannequin_base(recipe, recipe_path.parent, width, height)
    target_bbox = _padded_bbox(_alpha_bbox(mannequin_base), width, height, target_padding)
    if target_bbox is None:
        raise ValueError("mannequin recipe did not produce a visible target body")

    with Image.open(reference_image_path) as source:
        reference = source.convert("RGBA")
    reference_cutout, reference_bbox, foreground_summary = _reference_cutout(
        reference,
        foreground_mode=foreground_mode,
        alpha_threshold=foreground_alpha_threshold,
        background_threshold=foreground_background_threshold,
    )
    if reference_bbox is None:
        raise ValueError("reference image has no detected foreground")

    fitted_reference, fit = _fit_cutout_to_bbox(reference_cutout, (width, height), target_bbox)
    overlay = _overlay_fit(mannequin_base, fitted_reference)

    paths = {
        "mannequin_base": output / "mannequin_base.png",
        "reference_cutout": output / "reference_cutout.png",
        "fitted_reference": output / "fitted_reference.png",
        "fit_overlay": output / "fit_overlay.png",
        "contact_sheet": output / "reference_fit_contact_sheet.png",
    }
    mannequin_base.save(paths["mannequin_base"])
    reference_cutout.save(paths["reference_cutout"])
    fitted_reference.save(paths["fitted_reference"])
    overlay.save(paths["fit_overlay"])
    _write_contact_sheet(
        [
            ("mannequin target", mannequin_base),
            ("reference cutout", reference_cutout),
            ("fit overlay", overlay),
            ("fitted reference", fitted_reference),
        ],
        paths["contact_sheet"],
        contact_scale,
    )

    manifest = {
        "schema": "glyph_lab.reference_fit.v0",
        "reference_image": str(reference_image_path),
        "source_mannequin": str(recipe_path),
        "grid": {"width": width, "height": height},
        "foreground": foreground_summary,
        "reference_bbox": list(reference_bbox),
        "target_bbox": list(target_bbox),
        "fit": fit,
        "outputs": {name: str(path) for name, path in paths.items()},
        "rule": "foreground reference is cropped, scaled uniformly, and anchored bottom-center to the mannequin target bbox",
    }
    manifest_path = output / "reference_fit_manifest.json"
    _write_json(manifest_path, manifest)
    manifest["outputs"]["manifest"] = str(manifest_path)
    return manifest


def _render_mannequin_base(recipe: dict[str, Any], root: Path, width: int, height: int) -> Image.Image:
    image = Image.new("RGBA", (width, height), (255, 255, 255, 0))
    for part in sorted(recipe.get("parts", []), key=lambda item: int(item.get("draw_order", 0))):
        cutout_path = _resolve_path(root, part.get("cutout"))
        if cutout_path is None or not cutout_path.exists():
            continue
        with Image.open(cutout_path) as source:
            cutout = source.convert("RGBA")
        if cutout.size != (width, height):
            cutout = cutout.resize((width, height), Image.Resampling.NEAREST)
        image.alpha_composite(cutout)
    return image


def _reference_cutout(
    reference: Image.Image,
    *,
    foreground_mode: str,
    alpha_threshold: int,
    background_threshold: int,
) -> tuple[Image.Image, tuple[int, int, int, int] | None, dict[str, Any]]:
    mask, summary = foreground_mask(
        reference,
        reference.width,
        reference.height,
        mode=foreground_mode,
        alpha_threshold=alpha_threshold,
        background_threshold=background_threshold,
    )
    bbox = _mask_bbox(mask)
    if bbox is None:
        return Image.new("RGBA", (1, 1), (255, 255, 255, 0)), None, summary
    x0, y0, x1, y1 = bbox
    cutout = Image.new("RGBA", reference.size, (255, 255, 255, 0))
    source = reference.load()
    target = cutout.load()
    for y, row in enumerate(mask):
        for x, keep in enumerate(row):
            if keep:
                target[x, y] = source[x, y]
    return cutout.crop((x0, y0, x1 + 1, y1 + 1)), bbox, summary


def _fit_cutout_to_bbox(
    cutout: Image.Image,
    canvas_size: tuple[int, int],
    target_bbox: tuple[int, int, int, int],
) -> tuple[Image.Image, dict[str, Any]]:
    target_x0, target_y0, target_x1, target_y1 = target_bbox
    target_width = target_x1 - target_x0 + 1
    target_height = target_y1 - target_y0 + 1
    scale = min(target_width / cutout.width, target_height / cutout.height)
    scaled_width = max(1, int(round(cutout.width * scale)))
    scaled_height = max(1, int(round(cutout.height * scale)))
    resample = Image.Resampling.NEAREST if scale >= 1 else Image.Resampling.BOX
    scaled = cutout.resize((scaled_width, scaled_height), resample)
    paste_x = int(round((target_x0 + target_x1) / 2 - scaled_width / 2))
    paste_y = target_y1 - scaled_height + 1
    canvas = Image.new("RGBA", canvas_size, (255, 255, 255, 0))
    canvas.alpha_composite(scaled, (paste_x, paste_y))
    return canvas, {
        "scale": round(scale, 6),
        "scaled_size": [scaled_width, scaled_height],
        "paste_position": [paste_x, paste_y],
        "anchor": "bottom_center",
    }


def _overlay_fit(mannequin_base: Image.Image, fitted_reference: Image.Image) -> Image.Image:
    background = Image.new("RGBA", mannequin_base.size, (255, 255, 255, 255))
    pale = _with_alpha(mannequin_base, 86)
    background.alpha_composite(pale)
    background.alpha_composite(fitted_reference)
    return background


def _with_alpha(image: Image.Image, alpha: int) -> Image.Image:
    output = image.copy()
    output.putalpha(output.getchannel("A").point(lambda value: min(value, alpha)))
    return output


def _write_contact_sheet(items: list[tuple[str, Image.Image]], output_path: Path, scale: int) -> None:
    scaled = [(name, image.resize((image.width * scale, image.height * scale), Image.Resampling.NEAREST)) for name, image in items]
    label_height = 18
    padding = 12
    cell_width = max(image.width for _, image in scaled)
    cell_height = max(image.height for _, image in scaled) + label_height
    sheet = Image.new(
        "RGBA",
        (padding + len(scaled) * (cell_width + padding), padding + cell_height + padding),
        (245, 245, 245, 255),
    )
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    x = padding
    for name, image in scaled:
        draw.text((x, padding), name, fill=(0, 0, 0), font=font)
        sheet.alpha_composite(image, (x, padding + label_height))
        x += cell_width + padding
    sheet.save(output_path)


def _alpha_bbox(image: Image.Image) -> tuple[int, int, int, int] | None:
    alpha = image.getchannel("A")
    bbox = alpha.getbbox()
    if bbox is None:
        return None
    x0, y0, x1, y1 = bbox
    return x0, y0, x1 - 1, y1 - 1


def _mask_bbox(mask: list[list[bool]]) -> tuple[int, int, int, int] | None:
    points = [(x, y) for y, row in enumerate(mask) for x, value in enumerate(row) if value]
    if not points:
        return None
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    return min(xs), min(ys), max(xs), max(ys)


def _padded_bbox(
    bbox: tuple[int, int, int, int] | None,
    width: int,
    height: int,
    padding: int,
) -> tuple[int, int, int, int] | None:
    if bbox is None:
        return None
    x0, y0, x1, y1 = bbox
    return (
        max(0, x0 + padding),
        max(0, y0 + padding),
        min(width - 1, x1 - padding),
        min(height - 1, y1 - padding),
    )


def _resolve_path(root: Path, value: str | None) -> Path | None:
    if not value:
        return None
    path = Path(value)
    return path if path.is_absolute() else root / path


def _load_json(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
        handle.write("\n")
