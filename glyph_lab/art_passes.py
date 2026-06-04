from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


ART_PASS_ORDER = [
    "rough_measure",
    "linework",
    "value_gradient",
    "shadow",
    "highlight",
    "colour_material",
    "texture_detail",
    "measuring_glyphs",
]


@dataclass(frozen=True)
class ArtPass:
    name: str
    order: int
    input_sources: list[str]
    output_layer: str
    enabled: bool = True
    parameters: dict[str, Any] = field(default_factory=dict)
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "order": self.order,
            "input_sources": self.input_sources,
            "output_layer": self.output_layer,
            "enabled": self.enabled,
            "parameters": self.parameters,
            "description": self.description,
        }


@dataclass
class LayerEvidence:
    grid_width: int
    grid_height: int
    layers: dict[str, list[str]]
    measurements: dict[str, Any] = field(default_factory=dict)
    provenance: list[dict[str, Any]] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.grid_width <= 0 or self.grid_height <= 0:
            raise ValueError("LayerEvidence grid_width and grid_height must be positive")
        for name, rows in self.layers.items():
            if len(rows) != self.grid_height:
                raise ValueError(f"layer {name!r} has height {len(rows)}, expected {self.grid_height}")
            for index, row in enumerate(rows, start=1):
                if len(row) != self.grid_width:
                    raise ValueError(
                        f"layer {name!r} row {index} has width {len(row)}, expected {self.grid_width}"
                    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "grid_width": self.grid_width,
            "grid_height": self.grid_height,
            "layers": self.layers,
            "measurements": self.measurements,
            "provenance": self.provenance,
        }


def default_art_passes() -> list[ArtPass]:
    return [
        ArtPass(
            name="rough_measure",
            order=0,
            input_sources=["raw_image"],
            output_layer="rough_measure",
            description="Coarse crop, silhouette, centerline, and bounds from raw pixels.",
        ),
        ArtPass(
            name="linework",
            order=1,
            input_sources=["rough_measure", "edge_map"],
            output_layer="linework",
            description="Hard edges, contours, panel boundaries, groove lips, and curve strokes.",
        ),
        ArtPass(
            name="value_gradient",
            order=2,
            input_sources=["rough_measure", "value_band_map"],
            output_layer="value_gradient",
            description="Light/mid/dark fill, broad value bands, and smooth form evidence.",
        ),
        ArtPass(
            name="shadow",
            order=3,
            input_sources=["rough_measure", "value_gradient"],
            output_layer="shadow",
            description="Cast, contact, recess, and undercut shadow evidence.",
        ),
        ArtPass(
            name="highlight",
            order=4,
            input_sources=["value_gradient", "linework"],
            output_layer="highlight",
            description="Bevel, ridge, specular, and bright lip marks.",
        ),
        ArtPass(
            name="colour_material",
            order=5,
            input_sources=["value_gradient", "raw_image"],
            output_layer="colour_material",
            description="Material or tint evidence separating true shadow from material color.",
        ),
        ArtPass(
            name="texture_detail",
            order=6,
            input_sources=["linework", "value_gradient"],
            output_layer="texture_detail",
            description="Grain, cracks, chips, pores, pitting, fabric weave, and stone marks.",
        ),
        ArtPass(
            name="measuring_glyphs",
            order=7,
            input_sources=["linework", "value_gradient", "shadow", "highlight", "texture_detail"],
            output_layer="measuring_glyphs",
            description="Dimension ticks, curve probes, angle probes, depth probes, and confidence markers.",
        ),
    ]


def validate_art_passes(passes: list[ArtPass]) -> None:
    names = [art_pass.name for art_pass in passes]
    orders = [art_pass.order for art_pass in passes]
    if len(names) != len(set(names)):
        raise ValueError("art pass names must be unique")
    if len(orders) != len(set(orders)):
        raise ValueError("art pass orders must be unique")
    by_name = {art_pass.name: art_pass for art_pass in passes}
    required = {"rough_measure", "linework", "value_gradient", "shadow", "measuring_glyphs"}
    missing = required - set(by_name)
    if missing:
        raise ValueError(f"missing required art passes: {', '.join(sorted(missing))}")
    rough_order = by_name["rough_measure"].order
    for name, art_pass in by_name.items():
        if name != "rough_measure" and rough_order >= art_pass.order:
            raise ValueError("rough_measure must occur before art passes")
    measuring_order = by_name["measuring_glyphs"].order
    for name in ("linework", "value_gradient", "shadow"):
        if measuring_order <= by_name[name].order:
            raise ValueError("measuring_glyphs must occur after linework/value/shadow")


def art_pass_summary(passes: list[ArtPass] | None = None) -> dict[str, Any]:
    passes = passes or default_art_passes()
    validate_art_passes(passes)
    return {
        "passes": [art_pass.to_dict() for art_pass in sorted(passes, key=lambda item: item.order)],
        "valid": True,
        "doctrine": [
            "pixels are rough evidence",
            "art glyph passes organize evidence",
            "measuring glyphs operate after art passes",
            "final measurements carry provenance and confidence",
        ],
    }
