from __future__ import annotations

from pathlib import Path
from typing import Any
import json


FUSED_KEYS = [
    "grid_size",
    "occupied_bbox_cells",
    "total_height_cells",
    "max_width_cells",
    "taper_ratio",
    "symmetry_error",
    "likely_shape",
    "groove_count",
    "average_groove_spacing",
    "groove_spacing_variance",
    "rhythm_confidence",
    "likely_repeated_grooves",
    "band_count",
    "average_band_spacing",
    "band_spacing_variance",
    "likely_moulding_stack",
    "feature_flags",
]


def fuse_measurements(
    profile: dict[str, Any] | None = None,
    rhythm: dict[str, Any] | None = None,
    probe: dict[str, Any] | None = None,
) -> dict[str, Any]:
    profile = profile or {}
    rhythm = rhythm or {}
    probe = probe or {}
    fused = {
        "grid_size": profile.get("grid_size") or rhythm.get("grid_size") or _probe_grid_size(probe),
        "occupied_bbox_cells": profile.get("occupied_bbox_cells") or probe.get("occupied_bbox_cells"),
        "total_height_cells": profile.get("total_height_cells"),
        "max_width_cells": profile.get("max_width_cells"),
        "taper_ratio": profile.get("taper_ratio"),
        "symmetry_error": profile.get("symmetry_error"),
        "likely_shape": profile.get("likely_shape", "unknown"),
        "groove_count": rhythm.get("groove_count", 0),
        "average_groove_spacing": rhythm.get("average_groove_spacing"),
        "groove_spacing_variance": rhythm.get("groove_spacing_variance"),
        "rhythm_confidence": rhythm.get("rhythm_confidence", 0.0),
        "likely_repeated_grooves": bool(rhythm.get("likely_repeated_grooves", False)),
        "band_count": rhythm.get("band_count", 0),
        "average_band_spacing": rhythm.get("average_band_spacing"),
        "band_spacing_variance": rhythm.get("band_spacing_variance"),
        "likely_moulding_stack": bool(rhythm.get("likely_moulding_stack", False)),
        "measurement_sources": _sources(profile, rhythm, probe),
    }
    fused["feature_flags"] = feature_flags(fused, profile, rhythm, probe)
    return fused


def feature_flags(
    fused: dict[str, Any],
    profile: dict[str, Any] | None = None,
    rhythm: dict[str, Any] | None = None,
    probe: dict[str, Any] | None = None,
) -> list[str]:
    profile = profile or {}
    rhythm = rhythm or {}
    probe = probe or {}
    flags: list[str] = []
    aspect = _aspect_ratio(profile, fused)
    taper = fused.get("taper_ratio")
    symmetry = fused.get("symmetry_error")
    likely_shape = fused.get("likely_shape")

    if aspect is not None and aspect >= 1.35:
        flags.append("tall")
    if aspect is not None and aspect <= 0.75:
        flags.append("wide")
    if symmetry is not None and symmetry <= 1.0:
        flags.append("centered")
        flags.append("symmetric")
    if taper is not None and taper < 0.85:
        flags.append("tapered")
    if fused.get("likely_repeated_grooves"):
        flags.append("repeated_vertical_grooves")
    if fused.get("band_count", 0) >= 3:
        flags.append("repeated_horizontal_bands")
    if fused.get("likely_moulding_stack"):
        flags.append("moulding_stack")
    if likely_shape == "rectangle":
        flags.append("rectangle_like")
    if likely_shape == "circle_or_ellipse":
        flags.append("ellipse_like")
    if likely_shape == "taper_column":
        flags.append("tapered")
    return sorted(set(flags))


def write_fused_features(
    profile_path: str | Path | None,
    rhythm_path: str | Path | None,
    output_path: str | Path,
    probe_path: str | Path | None = None,
) -> dict[str, Any]:
    fused = fuse_measurements(
        _load_json(profile_path) if profile_path else None,
        _load_json(rhythm_path) if rhythm_path else None,
        _load_json(probe_path) if probe_path else None,
    )
    _write_json(output_path, fused)
    return fused


def _aspect_ratio(profile: dict[str, Any], fused: dict[str, Any]) -> float | None:
    crop = profile.get("crop_box")
    if crop and len(crop) == 4:
        width = crop[2] - crop[0]
        height = crop[3] - crop[1]
        return height / width if width else None
    height = fused.get("total_height_cells")
    width = fused.get("max_width_cells")
    return height / width if height and width else None


def _probe_grid_size(probe: dict[str, Any]) -> list[int] | None:
    if "grid_size" in probe:
        return probe["grid_size"]
    if "grid_width" in probe and "grid_height" in probe:
        return [probe["grid_width"], probe["grid_height"]]
    return None


def _sources(profile: dict[str, Any], rhythm: dict[str, Any], probe: dict[str, Any]) -> list[str]:
    sources = []
    if profile:
        sources.append("profile")
    if rhythm:
        sources.append("rhythm")
    if probe:
        sources.append("probe")
    return sources


def _load_json(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _write_json(path: str | Path, payload: dict[str, Any]) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with Path(path).open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
        handle.write("\n")
