from __future__ import annotations

from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

from .candidate_filter import candidate_stamp
from .transforms import scale_nearest


def generate_review_contact_sheet(
    accepted: list[dict[str, Any]],
    rejected: list[dict[str, Any]],
    output_path: str | Path,
    columns: int = 4,
    cell_size: tuple[int, int] = (160, 112),
) -> None:
    records = [("accepted", record) for record in accepted] + [
        ("rejected", record) for record in rejected
    ]
    if not records:
        records = [("empty", {"id": "no-candidates", "features": {"bitmask": 0}, "usefulness_score": 0})]
    rows = (len(records) + columns - 1) // columns
    cell_w, cell_h = cell_size
    sheet = Image.new("RGBA", (columns * cell_w, rows * cell_h), (244, 241, 232, 255))
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()

    for index, (state, record) in enumerate(records):
        col = index % columns
        row = index // columns
        left = col * cell_w
        top = row * cell_h
        fill = (229, 240, 225, 255) if state == "accepted" else (244, 224, 220, 255)
        if state == "empty":
            fill = (238, 235, 226, 255)
        draw.rectangle((left, top, left + cell_w - 1, top + cell_h - 1), fill=fill, outline=(120, 112, 100, 255))
        stamp = scale_nearest(candidate_stamp(record), 12)
        sheet.alpha_composite(stamp, (left + 8, top + 8))
        text_x = left + 62
        draw.text((text_x, top + 8), _label(record), fill=(30, 28, 24, 255), font=font)
        draw.text((text_x, top + 24), f"score {record.get('usefulness_score', 0):.2f}", fill=(30, 28, 24, 255), font=font)
        draw.text(
            (text_x, top + 40),
            _short(f"{record.get('role', '?')}/{record.get('family', '?')}", 18),
            fill=(30, 28, 24, 255),
            font=font,
        )
        reason = record.get("rejection_reason")
        if reason:
            draw.text((left + 8, top + 78), _short(reason, 28), fill=(96, 35, 28, 255), font=font)

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output_path)


def _label(record: dict[str, Any]) -> str:
    token = record.get("token")
    if token:
        return _short(f"token {token}", 18)
    return _short(str(record.get("id", "candidate")).split(".")[-1], 18)


def _short(value: str, length: int) -> str:
    return value if len(value) <= length else value[: length - 3] + "..."
