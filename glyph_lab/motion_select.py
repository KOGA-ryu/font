from __future__ import annotations

from pathlib import Path
from typing import Any
import json
import math


def load_glyph_records(path: str | Path) -> list[dict[str, Any]]:
    with Path(path).open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return payload.get("glyphs", payload.get("accepted_candidates", payload))


def select_motion_glyph(
    evidence: dict[str, Any],
    glyph_records: list[dict[str, Any]],
) -> dict[str, Any]:
    candidates = [record for record in glyph_records if record.get("token") and _is_linework_record(record)]
    if not candidates:
        fallback = _fallback_token(evidence)
        return {
            "token": fallback,
            "glyph_id": None,
            "score": 0.0,
            "selection_reason": "fallback-no-linework-motion-records",
        }
    scored = sorted(
        ((_score_record(evidence, record), record) for record in candidates),
        key=lambda item: (-item[0], int(item[1].get("index", 999999)), item[1].get("id", "")),
    )
    score, record = scored[0]
    if score <= 0:
        fallback = _fallback_token(evidence)
        return {
            "token": fallback,
            "glyph_id": None,
            "score": score,
            "selection_reason": "fallback-no-positive-motion-match",
        }
    return {
        "token": record["token"],
        "glyph_id": record.get("id"),
        "score": round(score, 4),
        "selection_reason": "motion-match",
    }


def _is_linework_record(record: dict[str, Any]) -> bool:
    return bool(
        record.get("linework_package")
        or record.get("linework_kind")
        or record.get("role") == "edge"
        or record.get("layer") == "edge"
    )


def _score_record(evidence: dict[str, Any], record: dict[str, Any]) -> float:
    score = 0.0
    if record.get("motion_profile") == evidence.get("motion_profile"):
        score += 4.0
    if record.get("stroke_topology") == evidence.get("stroke_topology"):
        score += 2.0
    if record.get("linework_package") == evidence.get("linework_package"):
        score += 1.5
    record_angle = record.get("angle_degrees")
    evidence_angle = evidence.get("angle_degrees")
    if record_angle is not None and evidence_angle is not None:
        score += max(0.0, 1.5 - (_angle_delta(float(record_angle), float(evidence_angle)) / 45.0))
    if _pressure_family(record.get("pressure_curve") or record.get("weight_profile")) == evidence.get("pressure_curve"):
        score += 0.75
    if record.get("release_style") == evidence.get("release_style"):
        score += 0.5
    return score


def _angle_delta(a: float, b: float) -> float:
    delta = abs((a - b) % 180.0)
    return min(delta, 180.0 - delta)


def _pressure_family(value: str | None) -> str | None:
    if value is None:
        return None
    if "heavy" in value or value == "medium":
        return "heavy" if "heavy" in value else "medium"
    if "light" in value or value == "thin":
        return "thin"
    return value


def _fallback_token(evidence: dict[str, Any]) -> str:
    angle = evidence.get("angle_degrees")
    if angle is None:
        return "+"
    angle = float(angle) % 180.0
    if _angle_delta(angle, 0.0) <= 22.5:
        return "-"
    if _angle_delta(angle, 90.0) <= 22.5:
        return "|"
    if _angle_delta(angle, 45.0) <= 45.0:
        return "/"
    return "\\"
