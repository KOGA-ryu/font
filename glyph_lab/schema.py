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
    source_glyph_id: str | None = None
    transform_chain: list[str] = field(default_factory=list)
    generated: bool = False
    source: str | None = None
    primitive_family: str | None = None
    primitive_params: dict[str, Any] = field(default_factory=dict)
    source_candidate_id: str | None = None
    promoted_from: str | None = None
    promoted_at_version: str | None = None
    notes: str | None = None

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
            source_glyph_id=data.get("source_glyph_id"),
            transform_chain=data.get("transform_chain", []),
            generated=bool(data.get("generated", False)),
            source=data.get("source"),
            primitive_family=data.get("primitive_family"),
            primitive_params=data.get("primitive_params", {}),
            source_candidate_id=data.get("source_candidate_id"),
            promoted_from=data.get("promoted_from"),
            promoted_at_version=data.get("promoted_at_version"),
            notes=data.get("notes"),
        )

    def to_dict(self) -> dict[str, Any]:
        data = {
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
        if self.generated:
            data["source_glyph_id"] = self.source_glyph_id
            data["transform_chain"] = self.transform_chain
            data["generated"] = True
        if self.source is not None:
            data["source"] = self.source
        if self.primitive_family is not None:
            data["primitive_family"] = self.primitive_family
        if self.primitive_params:
            data["primitive_params"] = self.primitive_params
        if self.source_candidate_id is not None:
            data["source_candidate_id"] = self.source_candidate_id
        if self.promoted_from is not None:
            data["promoted_from"] = self.promoted_from
        if self.promoted_at_version is not None:
            data["promoted_at_version"] = self.promoted_at_version
        if self.notes is not None:
            data["notes"] = self.notes
        return data


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
