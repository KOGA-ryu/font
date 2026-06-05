from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any
import json

from .compositor import compile_layered_grid
from .layers import output_layer_order
from .schema import load_glyphs


def ascii_grid_to_layered(
    ascii_text: str,
    mapping: dict[str, Any],
    active_tokens: set[str],
) -> dict[str, Any]:
    rows = ascii_text.splitlines()
    if not rows:
        raise ValueError("ASCII grid is empty")
    width = max(len(row) for row in rows)
    height = len(rows)
    if width <= 0:
        raise ValueError("ASCII grid has no columns")

    normalized_rows = [row.ljust(width) for row in rows]
    layer_rows = {layer: [list(" " * width) for _ in range(height)] for layer in output_layer_order()}
    warnings: list[dict[str, Any]] = []
    resolved_counts: Counter[str] = Counter()

    for y, row in enumerate(normalized_rows, start=1):
        for x, char in enumerate(row, start=1):
            if char == " ":
                continue
            resolved = resolve_ascii_char(char, mapping, active_tokens)
            if resolved is None:
                warnings.append(
                    {
                        "type": "unmapped-ascii-char",
                        "char": char,
                        "row": y,
                        "column": x,
                        "message": f"ASCII char {char!r} has no active glyph mapping",
                    }
                )
                continue
            if resolved.get("used_fallback"):
                warnings.append(
                    {
                        "type": "bridge-fallback",
                        "char": char,
                        "row": y,
                        "column": x,
                        "token": resolved["token"],
                        "message": f"Bridge-only char {char!r} resolved through fallback token {resolved['token']!r}",
                    }
                )
            layer = resolved["layer"]
            if layer not in layer_rows:
                layer = "detail"
            layer_rows[layer][y - 1][x - 1] = resolved["token"]
            resolved_counts[resolved["token"]] += 1

    return {
        "grid_width": width,
        "grid_height": height,
        "layers": [
            {"name": layer, "grid": ["".join(row) for row in rows]}
            for layer, rows in layer_rows.items()
            if any(any(char != " " for char in row) for row in rows)
        ],
        "metadata": {
            "source": "ascii_bridge",
            "resolved_token_counts": dict(sorted(resolved_counts.items())),
            "warnings": warnings,
        },
    }


def resolve_ascii_char(
    char: str,
    mapping: dict[str, Any],
    active_tokens: set[str],
) -> dict[str, Any] | None:
    entries = mapping.get("mapping", mapping)
    entry = entries.get(char)
    if entry is None:
        aliases = mapping.get("edge_aliases", {})
        alias = aliases.get(char)
        entry = entries.get(alias) if alias else None
    if entry is None:
        return None
    token = entry.get("token")
    if token and token in active_tokens:
        return {"token": token, "layer": entry.get("layer", "detail"), "used_fallback": False}
    if char in active_tokens:
        return {"token": char, "layer": entry.get("layer", "detail"), "used_fallback": False}
    fallback = entry.get("ascii_fallback")
    if fallback and fallback in entries:
        fallback_entry = entries[fallback]
        fallback_token = fallback_entry.get("token")
        if fallback_token and fallback_token in active_tokens:
            return {
                "token": fallback_token,
                "layer": fallback_entry.get("layer", entry.get("layer", "detail")),
                "used_fallback": True,
            }
    if fallback and fallback in active_tokens:
        return {"token": fallback, "layer": entry.get("layer", "detail"), "used_fallback": True}
    return None


def import_ascii_grid(
    pack_dir: str | Path,
    ascii_path: str | Path,
    mapping_path: str | Path,
    output_dir: str | Path,
    glyphs_path: str | Path | None = None,
    atlas_path: str | Path | None = None,
) -> dict[str, Any]:
    pack = Path(pack_dir)
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    glyphs_file = Path(glyphs_path) if glyphs_path is not None else pack / "glyphs.json"
    atlas_file = Path(atlas_path) if atlas_path is not None else pack / "atlas.png"
    ascii_text = Path(ascii_path).read_text(encoding="utf-8").rstrip("\n")
    mapping = _load_json(mapping_path)
    active_tokens = {glyph.token for glyph in load_glyphs(glyphs_file)}
    layered = ascii_grid_to_layered(ascii_text, mapping, active_tokens)
    layered["metadata"]["input_paths"] = {
        "pack": str(pack),
        "atlas": str(atlas_file),
        "glyphs": str(glyphs_file),
        "ascii": str(ascii_path),
        "mapping": str(mapping_path),
    }
    layered_path = out / "generated_layered_grid.json"
    _write_json(layered_path, layered)
    manifest = compile_layered_grid(atlas_file, glyphs_file, layered_path, out)
    manifest["ascii_bridge"] = layered["metadata"]
    _write_json(out / "manifest.json", manifest)
    return {"layered": layered, "manifest": manifest}


def _load_json(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _write_json(path: str | Path, payload: dict[str, Any]) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with Path(path).open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
        handle.write("\n")
