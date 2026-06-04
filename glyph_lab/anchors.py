from __future__ import annotations

from typing import Any


def detect_anchor_points(
    profile: dict[str, Any],
    rhythm: dict[str, Any] | None = None,
    boundary_cells: list[list[int]] | None = None,
) -> list[dict[str, Any]]:
    rhythm = rhythm or {}
    anchors: list[dict[str, Any]] = []
    seen: set[tuple[int, int, str]] = set()
    center_x = _center_x(profile)
    bbox = profile.get("occupied_bbox_cells")
    if bbox:
        _add_anchor(anchors, seen, "anchor.silhouette_top", center_x, int(bbox[1]), "silhouette_top", 0.78)
        _add_anchor(anchors, seen, "anchor.silhouette_bottom", center_x, int(bbox[3]), "silhouette_bottom", 0.78)

    for index, y in enumerate(rhythm.get("major_band_rows", [])):
        _add_anchor(anchors, seen, f"anchor.band_{index:02d}", center_x, int(y), "band_row", 0.82)
    for index, band in enumerate(rhythm.get("bands", [])):
        y = int(band["y_cell"])
        _add_anchor(anchors, seen, f"anchor.band_{index:02d}", center_x, y, "band_row", band.get("confidence", 0.72))

    groove_index = 0
    for groove in rhythm.get("grooves", []):
        x = int(groove["x_cell"])
        _add_anchor(
            anchors,
            seen,
            f"anchor.groove_{groove_index:02d}_start",
            x,
            int(groove["y_start"]),
            "groove_start",
            groove.get("confidence", 0.68),
        )
        _add_anchor(
            anchors,
            seen,
            f"anchor.groove_{groove_index:02d}_end",
            x,
            int(groove["y_end"]),
            "groove_end",
            groove.get("confidence", 0.68),
        )
        groove_index += 1

    for source, rows in (("bulge_row", profile.get("bulge_rows", [])), ("neck_row", profile.get("neck_rows", []))):
        for index, y in enumerate(rows):
            _add_anchor(anchors, seen, f"anchor.{source}_{index:02d}", center_x, int(y), source, 0.7)

    for index, y in enumerate(_profile_change_rows(profile.get("width_profile_by_row", []))):
        _add_anchor(anchors, seen, f"anchor.profile_change_{index:02d}", center_x, y, "profile_change", 0.58)

    for index, point in enumerate(_contour_corners(boundary_cells or [])):
        _add_anchor(anchors, seen, f"anchor.contour_corner_{index:02d}", point[0], point[1], "contour_corner", 0.52)

    return sorted(anchors, key=lambda item: (item["y"], item["x"], item["id"]))


def _add_anchor(
    anchors: list[dict[str, Any]],
    seen: set[tuple[int, int, str]],
    anchor_id: str,
    x: int,
    y: int,
    source: str,
    confidence: float,
) -> None:
    key = (int(x), int(y), source)
    if key in seen:
        return
    seen.add(key)
    anchors.append(
        {
            "id": anchor_id,
            "x": int(x),
            "y": int(y),
            "source": source,
            "confidence": round(max(0.0, min(1.0, float(confidence))), 4),
        }
    )


def _center_x(profile: dict[str, Any]) -> int:
    value = profile.get("centerline_x_estimate")
    if value is not None:
        return round(float(value))
    bbox = profile.get("occupied_bbox_cells")
    if bbox:
        return round((bbox[0] + bbox[2]) / 2)
    grid_size = profile.get("grid_size") or [32, 32]
    return int(grid_size[0]) // 2


def _profile_change_rows(widths: list[int]) -> list[int]:
    rows = []
    for index in range(1, len(widths)):
        if widths[index] and widths[index - 1] and abs(widths[index] - widths[index - 1]) >= 3:
            rows.append(index)
    return rows


def _contour_corners(boundary_cells: list[list[int]]) -> list[tuple[int, int]]:
    if not boundary_cells:
        return []
    xs = [point[0] for point in boundary_cells]
    ys = [point[1] for point in boundary_cells]
    corners = {
        (min(xs), min(ys)),
        (max(xs), min(ys)),
        (min(xs), max(ys)),
        (max(xs), max(ys)),
    }
    boundary = {(point[0], point[1]) for point in boundary_cells}
    return sorted(corner for corner in corners if corner in boundary)
