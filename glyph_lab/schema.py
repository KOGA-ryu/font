from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
import json


CELL_SIZE = 4
ATLAS_COLUMNS = 8
ATLAS_ROWS = 4
EXPECTED_LAYERS = ["base_fill", "edge", "shadow", "detail"]


@dataclass(frozen=True)
class Glyph:
    id: str
    token: str
    index: int
    role: str
    family: str
    layer: str
    palette_role: str
    cell_size: int = CELL_SIZE
    features: dict[str, Any] = field(default_factory=dict)
    constraints: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Glyph":
        return cls(
            id=data["id"],
            token=data["token"],
            index=int(data["index"]),
            role=data["role"],
            family=data["family"],
            layer=data["layer"],
            palette_role=data["palette_role"],
            cell_size=int(data.get("cell_size", CELL_SIZE)),
            features=data.get("features", {}),
            constraints=data.get("constraints", {}),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "token": self.token,
            "index": self.index,
            "role": self.role,
            "family": self.family,
            "layer": self.layer,
            "palette_role": self.palette_role,
            "cell_size": self.cell_size,
            "features": self.features,
            "constraints": self.constraints,
        }


def load_glyphs(path: str | Path) -> list[Glyph]:
    with Path(path).open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    records = data["glyphs"] if isinstance(data, dict) else data
    return [Glyph.from_dict(record) for record in records]


def save_glyphs(path: str | Path, glyphs: list[Glyph]) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with Path(path).open("w", encoding="utf-8") as handle:
        json.dump({"glyphs": [glyph.to_dict() for glyph in glyphs]}, handle, indent=2)
        handle.write("\n")
