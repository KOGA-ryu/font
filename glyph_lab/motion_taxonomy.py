from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path
from typing import Any
import json


MOTION_METADATA_FIELDS = (
    "motion_profile",
    "speed_class",
    "pressure_curve",
    "stress_points",
    "release_style",
    "dwell",
    "stroke_confidence",
    "rhythm_role",
    "acceleration",
    "motion_family",
)

EXPECTED_MOTION_PROFILES = {
    "linework.stroke": {"steady_pull", "pressed_pull", "angled_pull"},
    "linework.break": {"interrupted_pull"},
    "linework.terminal": {"press_and_stop"},
    "linework.join": {"direction_change"},
    "linework.curve": {"rounded_turn"},
    "linework.pattern": {"repeated_motion"},
}

RESEARCH_SOURCES = [
    {
        "name": "Wacom WILL ink pipeline",
        "url": "https://developer-docs.wacom.com/docs/sdk-for-ink/tech/pipeline/",
        "use": "Position, timestamp, pressure/force, tilt, phase, and velocity map to stroke motion state.",
    },
    {
        "name": "Wacom WILL overview",
        "url": "https://developer-docs.wacom.com/docs/sdk-for-ink/overview/",
        "use": "Digital ink stores sensor data and rendered ink together.",
    },
    {
        "name": "Krita brush sensors",
        "url": "https://docs.krita.org/en/reference_manual/brushes/brush_settings/tablet_sensors.html",
        "use": "Pressure, speed, drawing angle, distance, time, fade, tilt, and rotation inform brush behavior.",
    },
    {
        "name": "MyPaint concepts",
        "url": "https://www.mypaint.app/en/docs/manuals/v0.9.0/concepts/",
        "use": "A stroke is a sequence of brush dabs that can respond to pressure, speed, direction, and canvas state.",
    },
    {
        "name": "MyPaint Brushlib",
        "url": "https://github-wiki-see.page/m/mypaint/libmypaint/wiki/Using-Brushlib",
        "use": "Brush input includes x/y position, pressure, tilt, and time delta.",
    },
]


def motion_metadata(spec: dict[str, Any], base_metadata: dict[str, Any]) -> dict[str, Any]:
    kind = spec["kind"]
    params = spec.get("params", {})
    if kind == "line":
        return _line_motion(params, base_metadata)
    if kind == "corner":
        return _corner_motion(params)
    if kind == "cap":
        return _cap_motion()
    if kind == "hatch":
        return _hatch_motion(params)
    raise ValueError(f"unknown linework primitive kind: {kind}")


def linework_motion_coverage(records: list[dict[str, Any]]) -> dict[str, Any]:
    linework = [record for record in records if record.get("linework_package")]
    package_counts = Counter(record["linework_package"] for record in linework)
    motion_counts = Counter(record.get("motion_profile", "unknown") for record in linework)
    matrix: dict[str, Counter[str]] = defaultdict(Counter)
    missing_fields: dict[str, list[str]] = {}
    for record in linework:
        package = record["linework_package"]
        profile = record.get("motion_profile", "unknown")
        matrix[package][profile] += 1
        missing = [field for field in MOTION_METADATA_FIELDS if field not in record]
        if missing:
            missing_fields[record["id"]] = missing

    missing_profiles = {
        package: sorted(EXPECTED_MOTION_PROFILES[package] - set(matrix.get(package, {})))
        for package in sorted(EXPECTED_MOTION_PROFILES)
        if EXPECTED_MOTION_PROFILES[package] - set(matrix.get(package, {}))
    }
    return {
        "linework_record_count": len(linework),
        "package_counts": dict(sorted(package_counts.items())),
        "motion_profile_counts": dict(sorted(motion_counts.items())),
        "package_motion_matrix": {
            package: dict(sorted(counts.items()))
            for package, counts in sorted(matrix.items())
        },
        "missing_expected_motion_profiles": missing_profiles,
        "records_missing_motion_fields": missing_fields,
        "research_sources": RESEARCH_SOURCES,
    }


def write_linework_motion_coverage(
    glyphs_path: str | Path,
    output_path: str | Path,
) -> dict[str, Any]:
    records = _load_records(glyphs_path)
    report = linework_motion_coverage(records)
    report["glyphs_path"] = str(glyphs_path)
    _write_json(output_path, report)
    return report


def _line_motion(params: dict[str, Any], base_metadata: dict[str, Any]) -> dict[str, Any]:
    broken = bool(params.get("broken", False))
    thickness = int(params.get("thickness", 1))
    direction = params["direction"]
    if broken:
        return _motion(
            profile="interrupted_pull",
            speed="fast",
            pressure="constant_light" if thickness == 1 else "constant_medium",
            stress=[],
            release="dry_break",
            dwell="none",
            confidence="decisive",
            rhythm="single_with_gap",
            acceleration="steady",
            family="interrupted_stroke",
        )
    if thickness > 1:
        return _motion(
            profile="pressed_pull",
            speed="slow",
            pressure="constant_heavy",
            stress=["middle"],
            release="clean_exit",
            dwell="slight",
            confidence="decisive",
            rhythm="single",
            acceleration="steady",
            family="pressure_weight",
        )
    profile = "angled_pull" if direction.startswith("diagonal") else "steady_pull"
    return _motion(
        profile=profile,
        speed="medium",
        pressure=base_metadata.get("weight_profile", "thin"),
        stress=[],
        release="clean_exit",
        dwell="none",
        confidence="decisive",
        rhythm="single",
        acceleration="steady",
        family="continuous_stroke",
    )


def _corner_motion(params: dict[str, Any]) -> dict[str, Any]:
    if params.get("radius", "sharp") == "soft":
        return _motion(
            profile="rounded_turn",
            speed="medium",
            pressure="constant_light",
            stress=["curve_apex"],
            release="clean_exit",
            dwell="none",
            confidence="decisive",
            rhythm="single",
            acceleration="smooth_turn",
            family="turning_motion",
        )
    return _motion(
        profile="direction_change",
        speed="slow",
        pressure="constant_light",
        stress=["corner"],
        release="clean_exit",
        dwell="slight",
        confidence="decisive",
        rhythm="single",
        acceleration="corner_reset",
        family="join_motion",
    )


def _cap_motion() -> dict[str, Any]:
    return _motion(
        profile="press_and_stop",
        speed="decelerating",
        pressure="constant_medium",
        stress=["terminal"],
        release="blunt_stop",
        dwell="slight",
        confidence="decisive",
        rhythm="single",
        acceleration="stop",
        family="terminal_motion",
    )


def _hatch_motion(params: dict[str, Any]) -> dict[str, Any]:
    density = params["density"]
    return _motion(
        profile="repeated_motion",
        speed="fast",
        pressure="constant_light",
        stress=["repeat_accent"] if density == "dense" else [],
        release="flick" if density == "light" else "clean_exit",
        dwell="none",
        confidence="decisive",
        rhythm=f"repeat_{density}",
        acceleration="repeated",
        family="rhythmic_mark",
    )


def _motion(
    profile: str,
    speed: str,
    pressure: str,
    stress: list[str],
    release: str,
    dwell: str,
    confidence: str,
    rhythm: str,
    acceleration: str,
    family: str,
) -> dict[str, Any]:
    return {
        "motion_profile": profile,
        "speed_class": speed,
        "pressure_curve": pressure,
        "stress_points": stress,
        "release_style": release,
        "dwell": dwell,
        "stroke_confidence": confidence,
        "rhythm_role": rhythm,
        "acceleration": acceleration,
        "motion_family": family,
    }


def _load_records(path: str | Path) -> list[dict[str, Any]]:
    with Path(path).open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return payload.get("glyphs", payload.get("accepted_candidates", payload))


def _write_json(path: str | Path, payload: dict[str, Any]) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with Path(path).open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
        handle.write("\n")
