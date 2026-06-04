from __future__ import annotations

from pathlib import Path
from typing import Any
import json

from .fusion import fuse_measurements


FAMILIES = ["fluted_column", "simple_column", "banded_block", "rail_segment", "panel"]


def object_family_hints(fused: dict[str, Any]) -> dict[str, Any]:
    hints = [_score_family(family, fused) for family in FAMILIES]
    hints.append(_unknown_hint(fused, hints))
    hints = sorted(hints, key=lambda item: item["confidence"], reverse=True)
    return {"top_hint": hints[0], "hints": hints}


def write_object_hints(
    profile: dict[str, Any] | None,
    rhythm: dict[str, Any] | None,
    out_dir: str | Path,
    probe: dict[str, Any] | None = None,
) -> dict[str, Any]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    fused = fuse_measurements(profile, rhythm, probe)
    hints = object_family_hints(fused)
    _write_json(out / "fused_features.json", fused)
    _write_json(out / "object_family_hints.json", hints)
    return {"fused_features": fused, "object_family_hints": hints}


def _score_family(family: str, fused: dict[str, Any]) -> dict[str, Any]:
    flags = set(fused.get("feature_flags", []))
    sources = fused.get("measurement_sources", [])
    required = _requirements(family)
    reasons = []
    missing = []
    score = 0.0
    for flag, weight, reason in required:
        if flag in flags or _special_match(flag, fused, flags):
            score += weight
            reasons.append(reason)
        else:
            missing.append(reason)
    confidence = round(min(1.0, score), 4)
    return {
        "family": family,
        "confidence": confidence,
        "reasons": reasons,
        "missing_evidence": missing,
        "measurement_sources": sources,
    }


def _requirements(family: str) -> list[tuple[str, float, str]]:
    if family == "fluted_column":
        return [
            ("tall", 0.2, "tall silhouette"),
            ("column_shape", 0.2, "tapered or rectangle-like vertical body"),
            ("repeated_vertical_grooves", 0.35, "repeated vertical grooves"),
            ("some_horizontal_bands", 0.15, "cap/base or horizontal bands present"),
            ("symmetric", 0.1, "symmetric or centered profile"),
        ]
    if family == "simple_column":
        return [
            ("tall", 0.25, "tall silhouette"),
            ("centered", 0.2, "centered profile"),
            ("symmetric", 0.2, "symmetric profile"),
            ("column_shape", 0.25, "rectangle-like or tapered body"),
            ("not_moulding_stack", 0.1, "not dominated by moulding stack"),
        ]
    if family == "banded_block":
        return [
            ("rectangle_like", 0.35, "rectangle-like silhouette"),
            ("repeated_horizontal_bands", 0.25, "repeated horizontal bands"),
            ("moulding_stack", 0.25, "moulding stack rhythm"),
            ("not_tall", 0.15, "not strongly tall"),
        ]
    if family == "rail_segment":
        return [
            ("wide", 0.25, "wide silhouette"),
            ("rhythmic_verticals", 0.3, "vertical rhythm or baluster-like repetition"),
            ("some_horizontal_bands", 0.25, "horizontal rail or band evidence"),
            ("not_tall", 0.2, "not strongly tall"),
        ]
    return [
        ("rectangle_like", 0.3, "rectangle-like silhouette"),
        ("centered", 0.2, "centered profile"),
        ("low_taper", 0.2, "low taper"),
        ("no_strong_groove_rhythm", 0.2, "no strong groove rhythm"),
        ("not_moulding_stack", 0.1, "not a moulding stack"),
    ]


def _special_match(flag: str, fused: dict[str, Any], flags: set[str]) -> bool:
    if flag == "column_shape":
        return "rectangle_like" in flags or "tapered" in flags
    if flag == "some_horizontal_bands":
        return fused.get("band_count", 0) > 0
    if flag == "not_moulding_stack":
        return "rhythm" in fused.get("measurement_sources", []) and "moulding_stack" not in flags
    if flag == "not_tall":
        return "tall" not in flags
    if flag == "rhythmic_verticals":
        return "repeated_vertical_grooves" in flags or fused.get("groove_count", 0) >= 3
    if flag == "low_taper":
        taper = fused.get("taper_ratio")
        return taper is not None and 0.85 <= taper <= 1.15
    if flag == "no_strong_groove_rhythm":
        return "rhythm" in fused.get("measurement_sources", []) and not fused.get("likely_repeated_grooves", False)
    return False


def _unknown_hint(fused: dict[str, Any], hints: list[dict[str, Any]]) -> dict[str, Any]:
    best = max((hint["confidence"] for hint in hints), default=0.0)
    confidence = 0.75 if best < 0.35 else max(0.0, 0.35 - best)
    return {
        "family": "unknown",
        "confidence": round(confidence, 4),
        "reasons": ["weak or conflicting evidence"] if confidence else [],
        "missing_evidence": ["strong profile and rhythm evidence"] if confidence else [],
        "measurement_sources": fused.get("measurement_sources", []),
    }


def _write_json(path: str | Path, payload: dict[str, Any]) -> None:
    with Path(path).open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
        handle.write("\n")
