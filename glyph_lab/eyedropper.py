from __future__ import annotations

from pathlib import Path
from typing import Any
import json

from PIL import Image


def sample_color(image_path: str | Path, x: int, y: int, label: str | None = None) -> dict[str, Any]:
    with Image.open(image_path) as source:
        image = source.convert("RGBA")
        if x < 0 or y < 0 or x >= image.width or y >= image.height:
            raise ValueError(f"sample point ({x}, {y}) is outside image bounds {image.width}x{image.height}")
        red, green, blue, alpha = image.getpixel((x, y))
    sample = {
        "x": x,
        "y": y,
        "rgba": [red, green, blue, alpha],
        "hex": _hex(red, green, blue),
        "alpha": alpha,
        "luminance": _luminance(red, green, blue),
    }
    if label:
        sample["label"] = label
    return sample


def grid_samples(image_path: str | Path, grid_width: int, grid_height: int) -> list[dict[str, Any]]:
    if grid_width <= 0 or grid_height <= 0:
        raise ValueError("grid size must be positive")
    with Image.open(image_path) as source:
        width, height = source.size
    samples = []
    for row in range(grid_height):
        for column in range(grid_width):
            x = min(width - 1, int((column + 0.5) * width / grid_width))
            y = min(height - 1, int((row + 0.5) * height / grid_height))
            samples.append(sample_color(image_path, x, y, label=f"cell_{column}_{row}") | {"grid_x": column, "grid_y": row})
    return samples


def write_eyedropper_json(
    image_path: str | Path,
    output_path: str | Path,
    *,
    points: list[tuple[int, int, str | None]] | None = None,
    grid_size: tuple[int, int] | None = None,
    base_json_path: str | Path | None = None,
    json_key: str = "eyedropper_samples",
) -> dict[str, Any]:
    if not points and grid_size is None:
        raise ValueError("provide at least one sample point or a grid size")

    samples: list[dict[str, Any]] = []
    for x, y, label in points or []:
        samples.append(sample_color(image_path, x, y, label=label))
    if grid_size is not None:
        samples.extend(grid_samples(image_path, grid_size[0], grid_size[1]))

    with Image.open(image_path) as source:
        image_size = [source.width, source.height]

    payload = _load_json(base_json_path) if base_json_path is not None else {}
    payload[json_key] = {
        "source_image": str(image_path),
        "image_size": image_size,
        "samples": samples,
    }
    _write_json(output_path, payload)
    return payload


def parse_point(value: str) -> tuple[int, int, str | None]:
    label = None
    coords = value
    if ":" in value:
        label, coords = value.split(":", 1)
        if not label:
            raise ValueError(f"invalid sample point {value!r}: label is empty")
    parts = coords.split(",")
    if len(parts) != 2:
        raise ValueError(f"sample point must be 'x,y' or 'label:x,y', got {value!r}")
    try:
        x = int(parts[0])
        y = int(parts[1])
    except ValueError as exc:
        raise ValueError(f"sample point coordinates must be integers, got {value!r}") from exc
    return x, y, label


def parse_grid_size(value: str) -> tuple[int, int]:
    lowered = value.lower()
    separator = "x" if "x" in lowered else ","
    parts = lowered.split(separator)
    if len(parts) != 2:
        raise ValueError(f"grid size must be 'WIDTHxHEIGHT' or 'WIDTH,HEIGHT', got {value!r}")
    try:
        width = int(parts[0])
        height = int(parts[1])
    except ValueError as exc:
        raise ValueError(f"grid size values must be integers, got {value!r}") from exc
    if width <= 0 or height <= 0:
        raise ValueError("grid size must be positive")
    return width, height


def _hex(red: int, green: int, blue: int) -> str:
    return f"#{red:02x}{green:02x}{blue:02x}"


def _luminance(red: int, green: int, blue: int) -> int:
    return int(round(0.299 * red + 0.587 * green + 0.114 * blue))


def _load_json(path: str | Path | None) -> dict[str, Any]:
    if path is None:
        return {}
    with Path(path).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _write_json(path: str | Path, payload: dict[str, Any]) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
        handle.write("\n")
