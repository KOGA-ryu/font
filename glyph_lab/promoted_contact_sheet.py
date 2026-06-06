from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any
import json

from PIL import Image, ImageDraw, ImageFont

from .atlas import load_atlas_stamps
from .schema import load_glyphs
from .transforms import scale_nearest


def generate_promoted_contact_sheet(
    glyphs_path: str | Path,
    atlas_path: str | Path,
    output_path: str | Path,
    cell_pixels: int = 88,
) -> dict[str, Any]:
    records = _load_records(glyphs_path)
    promoted_records = [record for record in records if _is_promoted(record)]
    glyphs = load_glyphs(glyphs_path)
    stamps = load_atlas_stamps(atlas_path, glyphs)
    groups = _group_records(promoted_records)

    width = cell_pixels * 4
    header_height = 18
    row_count = sum(1 + ((len(group_records) + 3) // 4) for group_records in groups.values())
    height = max(cell_pixels, row_count * cell_pixels)
    sheet = Image.new("RGBA", (width, height), (244, 241, 232, 255))
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()

    y = 0
    for group, group_records in groups.items():
        draw.rectangle((0, y, width - 1, y + header_height - 1), fill=(212, 204, 188, 255))
        draw.text((6, y + 4), group, fill=(30, 28, 24, 255), font=font)
        y += header_height
        for offset, record in enumerate(group_records):
            col = offset % 4
            row = offset // 4
            left = col * cell_pixels
            top = y + row * cell_pixels
            draw.rectangle((left, top, left + cell_pixels - 1, top + cell_pixels - 1), outline=(120, 112, 100, 255))
            stamp = scale_nearest(stamps[record["token"]], 10)
            sheet.alpha_composite(stamp, (left + 24, top + 5))
            draw.text((left + 5, top + 47), f"{record['token']} {record.get('role', '')}", fill=(30, 28, 24, 255), font=font)
            draw.text((left + 5, top + 59), _short_family(record), fill=(30, 28, 24, 255), font=font)
            draw.text((left + 5, top + 71), _source_suffix(record), fill=(30, 28, 24, 255), font=font)
        y += max(1, ((len(group_records) + 3) // 4)) * cell_pixels

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    sheet.crop((0, 0, width, max(y, cell_pixels))).save(output_path)
    return {
        "output_path": str(output_path),
        "glyphs_path": str(glyphs_path),
        "atlas_path": str(atlas_path),
        "promoted_count": len(promoted_records),
        "groups": {group: len(group_records) for group, group_records in groups.items()},
    }


def _is_promoted(record: dict[str, Any]) -> bool:
    return bool(record.get("promoted_from") or record.get("source_candidate_id"))


def _group_records(records: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in sorted(records, key=lambda item: int(item.get("index", 0))):
        grouped[_group_name(record)].append(record)
    return {group: grouped[group] for group in sorted(grouped, key=_group_sort_key)}


def _group_name(record: dict[str, Any]) -> str:
    if record.get("linework_kind"):
        return "linework"
    brush_family = record.get("brush_family")
    if brush_family:
        return f"brush:{brush_family}"
    primitive_family = record.get("primitive_family")
    if primitive_family:
        return f"primitive:{primitive_family}"
    return "other"


def _group_sort_key(group: str) -> tuple[int, str]:
    order = {
        "linework": 0,
        "brush:hatch": 1,
        "brush:crosshatch": 2,
        "brush:charcoal": 3,
        "brush:dry_brush": 4,
        "brush:grain": 5,
        "brush:stipple": 6,
        "brush:spray": 7,
        "brush:scratch": 8,
        "brush:chip": 9,
        "brush:tone_hatch": 10,
        "brush:dot_field": 11,
    }
    return (order.get(group, 100), group)


def _short_family(record: dict[str, Any]) -> str:
    brush = record.get("brush_family")
    density = record.get("density_class")
    if brush and density:
        return f"{brush}/{density}"[:14]
    if brush:
        return brush[:14]
    linework = record.get("linework_kind")
    if linework:
        return f"{linework}/{record.get('variant', '')}"[:14]
    return str(record.get("family", ""))[:14]


def _source_suffix(record: dict[str, Any]) -> str:
    source = record.get("source_candidate_id") or record.get("id", "")
    return source.split(".")[-1][-14:]


def _load_records(path: str | Path) -> list[dict[str, Any]]:
    with Path(path).open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return payload.get("glyphs", payload)
