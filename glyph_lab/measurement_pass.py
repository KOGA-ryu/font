from __future__ import annotations

from pathlib import Path
from typing import Any
import json

from .art_passes import LayerEvidence, art_pass_summary
from .provenance import measurement_record


ART_LAYER_NAMES = [
    "linework",
    "value_gradient",
    "shadow",
    "highlight",
    "colour_material",
    "texture_detail",
    "measuring_glyphs",
]


def build_layer_evidence_from_probe_outputs(
    probe: dict[str, Any] | None = None,
    profile: dict[str, Any] | None = None,
    rhythm: dict[str, Any] | None = None,
    layered: dict[str, Any] | None = None,
) -> LayerEvidence:
    probe = probe or {}
    profile = profile or {}
    rhythm = rhythm or {}
    layered = layered or {}
    grid_width = int(layered.get("grid_width") or probe.get("grid_width") or _grid_size(profile, rhythm)[0])
    grid_height = int(layered.get("grid_height") or probe.get("grid_height") or _grid_size(profile, rhythm)[1])
    blank = " " * grid_width
    source_layers = {
        layer["name"]: layer["grid"]
        for layer in layered.get("layers", [])
        if "name" in layer and "grid" in layer
    }
    layers = {
        "linework": source_layers.get("edge", [blank for _ in range(grid_height)]),
        "value_gradient": _merge_grids(
            grid_width,
            grid_height,
            source_layers.get("base_fill"),
            source_layers.get("mass"),
        ),
        "shadow": source_layers.get("shadow", [blank for _ in range(grid_height)]),
        "highlight": source_layers.get("highlight", [blank for _ in range(grid_height)]),
        "colour_material": source_layers.get("colour_material", [blank for _ in range(grid_height)]),
        "texture_detail": source_layers.get("detail", [blank for _ in range(grid_height)]),
        "measuring_glyphs": source_layers.get("measurement", [blank for _ in range(grid_height)]),
    }
    provenance = [
        {
            "stage": "layer_evidence",
            "notes": "Existing layered glyph grids are mapped into art-pass layer names.",
        }
    ]
    return LayerEvidence(
        grid_width=grid_width,
        grid_height=grid_height,
        layers=layers,
        measurements={"probe": probe, "profile": profile, "rhythm": rhythm},
        provenance=provenance,
    )


def final_measurements_from_layer_evidence(evidence: LayerEvidence) -> list[dict[str, Any]]:
    profile = evidence.measurements.get("profile", {})
    probe = evidence.measurements.get("probe", {})
    rhythm = evidence.measurements.get("rhythm", {})
    records = [
        _object_width(evidence, profile, probe),
        _object_height(evidence, profile, probe),
        _centerline(evidence, profile, probe),
        _profile_taper(profile),
        _groove_count(rhythm),
        _groove_spacing(rhythm),
        _band_count(rhythm),
        _band_spacing(rhythm),
        _shadow_depth_hint(evidence),
        _curve_presence_hint(profile, evidence),
    ]
    return records


def write_art_pass_measurements(
    out_dir: str | Path,
    probe: dict[str, Any] | None = None,
    profile: dict[str, Any] | None = None,
    rhythm: dict[str, Any] | None = None,
    layered: dict[str, Any] | None = None,
) -> dict[str, Any]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    evidence = build_layer_evidence_from_probe_outputs(probe, profile, rhythm, layered)
    measurements = final_measurements_from_layer_evidence(evidence)
    summary = art_pass_summary()
    summary["layer_evidence"] = {
        "grid_width": evidence.grid_width,
        "grid_height": evidence.grid_height,
        "layers": sorted(evidence.layers),
        "measurement_sources": [name for name, value in evidence.measurements.items() if value],
        "provenance": evidence.provenance,
    }
    _write_json(out / "final_measurements.json", {"measurements": measurements})
    _write_json(out / "art_pass_summary.json", summary)
    return {"measurements": measurements, "art_pass_summary": summary}


def _object_width(evidence: LayerEvidence, profile: dict[str, Any], probe: dict[str, Any]) -> dict[str, Any]:
    value = profile.get("max_width_cells")
    confidence = 0.85
    sources = ["profile.max_width_cells"]
    notes = "Measured after art-pass organization from profile evidence."
    if value is None:
        bbox = probe.get("occupied_bbox_cells")
        value = bbox[2] - bbox[0] + 1 if bbox else None
        confidence = 0.45 if value is not None else 0.1
        sources = ["probe.occupied_bbox_cells"] if value is not None else []
        notes = "Profile width missing; used rough probe bounds." if value is not None else "Missing profile/probe width evidence."
    return measurement_record(
        "object_width_cells",
        value,
        "cells",
        ["linework", "value_gradient"],
        sources,
        "read object width from cleaned profile or rough silhouette bounds",
        confidence,
        notes,
    )


def _object_height(evidence: LayerEvidence, profile: dict[str, Any], probe: dict[str, Any]) -> dict[str, Any]:
    value = profile.get("total_height_cells")
    confidence = 0.85
    sources = ["profile.total_height_cells"]
    notes = "Measured after art-pass organization from profile evidence."
    if value is None:
        bbox = probe.get("occupied_bbox_cells")
        value = bbox[3] - bbox[1] + 1 if bbox else None
        confidence = 0.45 if value is not None else 0.1
        sources = ["probe.occupied_bbox_cells"] if value is not None else []
        notes = "Profile height missing; used rough probe bounds." if value is not None else "Missing profile/probe height evidence."
    return measurement_record(
        "object_height_cells",
        value,
        "cells",
        ["linework", "value_gradient"],
        sources,
        "read object height from cleaned profile or rough silhouette bounds",
        confidence,
        notes,
    )


def _centerline(evidence: LayerEvidence, profile: dict[str, Any], probe: dict[str, Any]) -> dict[str, Any]:
    value = profile.get("centerline_x_estimate", probe.get("centerline_x_estimate"))
    confidence = 0.75 if profile.get("centerline_x_estimate") is not None else 0.4 if value is not None else 0.1
    source = "profile.centerline_x_estimate" if profile.get("centerline_x_estimate") is not None else "probe.centerline_x_estimate"
    return measurement_record(
        "centerline_x",
        value,
        "cells",
        ["linework", "value_gradient"],
        [source] if value is not None else [],
        "estimate centerline from organized silhouette/profile evidence",
        confidence,
        "Centerline remains a cell-space estimate unless calibrated.",
    )


def _profile_taper(profile: dict[str, Any]) -> dict[str, Any]:
    present = profile.get("taper_ratio") is not None
    return measurement_record(
        "profile_taper_ratio",
        profile.get("taper_ratio"),
        "ratio",
        ["linework", "value_gradient"],
        ["profile.taper_ratio"] if present else [],
        "compare top and bottom profile widths after silhouette cleanup",
        0.8 if present else 0.1,
        "Missing profile taper evidence." if not present else "Top width divided by bottom width.",
    )


def _groove_count(rhythm: dict[str, Any]) -> dict[str, Any]:
    present = "groove_count" in rhythm
    return measurement_record(
        "groove_count",
        rhythm.get("groove_count"),
        "count",
        ["linework", "shadow"],
        ["rhythm.groove_count"] if present else [],
        "count edge-aligned groove centers from linework with shadow confirmation",
        0.8 if present else 0.1,
        "Missing rhythm input; groove count is unconfirmed." if not present else "Repeated vertical groove evidence measured from rhythm pass.",
    )


def _groove_spacing(rhythm: dict[str, Any]) -> dict[str, Any]:
    present = rhythm.get("average_groove_spacing") is not None
    return measurement_record(
        "groove_spacing_cells",
        rhythm.get("average_groove_spacing"),
        "cells",
        ["linework", "shadow"],
        ["rhythm.average_groove_spacing"] if present else [],
        "measure average spacing between detected groove centers",
        0.78 if present else 0.1,
        "Missing rhythm input; groove spacing is unavailable." if not present else "Spacing is in sampled grid cells.",
    )


def _band_count(rhythm: dict[str, Any]) -> dict[str, Any]:
    present = "band_count" in rhythm
    return measurement_record(
        "band_count",
        rhythm.get("band_count"),
        "count",
        ["linework", "shadow", "highlight"],
        ["rhythm.band_count"] if present else [],
        "count horizontal construction bands from organized line/value evidence",
        0.75 if present else 0.1,
        "Missing rhythm input; band count is unconfirmed." if not present else "Horizontal band evidence measured from rhythm pass.",
    )


def _band_spacing(rhythm: dict[str, Any]) -> dict[str, Any]:
    present = rhythm.get("average_band_spacing") is not None
    return measurement_record(
        "band_spacing_cells",
        rhythm.get("average_band_spacing"),
        "cells",
        ["linework", "shadow", "highlight"],
        ["rhythm.average_band_spacing"] if present else [],
        "measure average spacing between horizontal band rows",
        0.72 if present else 0.1,
        "Missing rhythm input; band spacing is unavailable." if not present else "Spacing is in sampled grid cells.",
    )


def _shadow_depth_hint(evidence: LayerEvidence) -> dict[str, Any]:
    shadow_cells = _occupied_cells(evidence.layers.get("shadow", []))
    linework_cells = _occupied_cells(evidence.layers.get("linework", []))
    value_cells = _occupied_cells(evidence.layers.get("value_gradient", []))
    object_cells = len(value_cells | shadow_cells | linework_cells)
    if object_cells == 0:
        value = 0.0
        confidence = 0.1
        notes = "No organized layer evidence for relative shadow depth."
    else:
        adjacency = _adjacency_count(shadow_cells, linework_cells)
        shadow_ratio = len(shadow_cells) / object_cells
        adjacency_ratio = adjacency / max(1, len(shadow_cells))
        value = round(min(1.0, shadow_ratio * 1.4 + adjacency_ratio * 0.35), 4)
        confidence = round(min(0.85, 0.35 + shadow_ratio + adjacency_ratio * 0.2), 4)
        notes = "Relative hint only; no real-world depth without scale/light/camera data."
    return measurement_record(
        "shadow_depth_hint",
        value,
        "relative",
        ["shadow", "linework", "value_gradient"],
        ["layer.shadow", "layer.linework"],
        "estimate relative shadow/recess strength from shadow coverage and adjacency to linework",
        confidence,
        notes,
    )


def _curve_presence_hint(profile: dict[str, Any], evidence: LayerEvidence) -> dict[str, Any]:
    bulges = profile.get("bulge_rows", []) or []
    necks = profile.get("neck_rows", []) or []
    likely_curve = profile.get("likely_shape") == "circle_or_ellipse" or bool(bulges or necks)
    confidence = 0.78 if bulges or necks else 0.62 if likely_curve else 0.25
    rows = sorted(set(bulges + necks))
    return measurement_record(
        "curve_presence_hint",
        likely_curve,
        "boolean",
        ["linework", "value_gradient", "measuring_glyphs"],
        ["profile.bulge_rows", "profile.neck_rows", "profile.likely_shape"],
        "infer curve presence from profile bulge/neck rows and classified silhouette shape",
        confidence,
        "Curve evidence rows are recorded when available.",
        metadata={"source_rows": rows},
    )


def _grid_size(profile: dict[str, Any], rhythm: dict[str, Any]) -> tuple[int, int]:
    size = profile.get("grid_size") or rhythm.get("grid_size") or [32, 32]
    return int(size[0]), int(size[1])


def _merge_grids(grid_width: int, grid_height: int, *grids: list[str] | None) -> list[str]:
    merged = [list(" " * grid_width) for _ in range(grid_height)]
    for grid in grids:
        if not grid:
            continue
        for y, row in enumerate(grid):
            for x, token in enumerate(row):
                if token != " ":
                    merged[y][x] = token
    return ["".join(row) for row in merged]


def _occupied_cells(rows: list[str]) -> set[tuple[int, int]]:
    return {(x, y) for y, row in enumerate(rows) for x, token in enumerate(row) if token != " "}


def _adjacency_count(cells: set[tuple[int, int]], targets: set[tuple[int, int]]) -> int:
    count = 0
    for x, y in cells:
        if any((x + dx, y + dy) in targets for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1))):
            count += 1
    return count


def _write_json(path: str | Path, payload: dict[str, Any]) -> None:
    with Path(path).open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
        handle.write("\n")
