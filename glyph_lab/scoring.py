from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import Any


SOLID_ROLES = {"solid", "mass", "shadow"}
TEXTURE_FAMILIES = {"texture", "damage"}
MEASUREMENT_ROLES = {"guide", "measurement"}


def score_glyph(glyph: Any) -> dict[str, Any]:
    record = _as_record(glyph)
    features = record.get("features", {})
    role = record.get("role", "")
    family = record.get("family", "")
    density = float(features.get("density", 0.0))
    components = int(features.get("connected_component_count", 0))
    contacts = features.get("edge_contacts", {})
    quadrants = features.get("quadrant_densities", {})
    symmetry = features.get("symmetry", {})
    bbox = features.get("bounding_box")

    tags: list[str] = []
    rejection_reason = _rejection_reason(role, family, density, components, contacts, bbox)
    score = _base_score(role, family, density, components, contacts, quadrants, symmetry, bbox)

    if density == 0:
        tags.append("empty")
    elif density == 1:
        tags.append("solid")
    elif family in TEXTURE_FAMILIES:
        tags.append(family)
    elif _is_edge_like(role, family):
        tags.append("connector")
    else:
        tags.append("shape")

    if symmetry.get("horizontal") or symmetry.get("vertical"):
        tags.append("symmetric")
    if contacts:
        tags.append(f"contacts:{_contact_count(contacts)}")
    if rejection_reason:
        tags.append("rejected")
        score = min(score, 0.25)
    else:
        tags.append("candidate")

    scored = dict(record)
    scored["usefulness_score"] = round(max(0.0, min(1.0, score)), 4)
    scored["rejection_reason"] = rejection_reason
    scored["review_tags"] = tags
    return scored


def _rejection_reason(
    role: str,
    family: str,
    density: float,
    components: int,
    contacts: dict[str, bool],
    bbox: dict[str, int] | None,
) -> str | None:
    if role in MEASUREMENT_ROLES:
        return None
    if density == 0 and role != "empty":
        return "empty-density-for-non-empty-role"
    if density == 1 and role not in SOLID_ROLES and family != "solid":
        return "solid-density-for-non-solid-role"
    if family not in TEXTURE_FAMILIES and components > 2:
        return "too-many-components-for-non-texture"
    if _is_edge_like(role, family) and _contact_count(contacts) == 0:
        return "no-edge-contacts-for-edge-like-glyph"
    if role == "edge" and family not in {"corner", "junction", "diagonal"} and _ambiguous_edge_contacts(contacts):
        return "ambiguous-edge-orientation"
    if family == "corner" and not _has_adjacent_contacts(contacts):
        return "corner-without-adjacent-contacts"
    if bbox is None and role != "empty":
        return "missing-bounding-box"
    return None


def _base_score(
    role: str,
    family: str,
    density: float,
    components: int,
    contacts: dict[str, bool],
    quadrants: dict[str, float],
    symmetry: dict[str, bool],
    bbox: dict[str, int] | None,
) -> float:
    if role == "empty":
        return 0.2 if density == 0 else 0.05
    score = 0.35
    score += min(density, 1.0 - abs(density - 0.5)) * 0.3
    score += min(_contact_count(contacts), 4) * 0.08
    if bbox:
        score += 0.08
    if components == 1:
        score += 0.12
    elif family in TEXTURE_FAMILIES and components > 1:
        score += 0.12
    if _quadrants_are_varied(quadrants):
        score += 0.07
    if symmetry.get("horizontal") or symmetry.get("vertical"):
        score += 0.05
    if family == "corner" and _has_adjacent_contacts(contacts):
        score += 0.08
    if role == "edge" and _has_opposed_contacts(contacts):
        score += 0.08
    return score


def _as_record(glyph: Any) -> dict[str, Any]:
    if isinstance(glyph, dict):
        return glyph
    if is_dataclass(glyph):
        return asdict(glyph)
    raise TypeError(f"expected glyph dict or dataclass, got {type(glyph).__name__}")


def _is_edge_like(role: str, family: str) -> bool:
    return role == "edge" or family in {"corner", "junction"}


def _contact_count(contacts: dict[str, bool]) -> int:
    return sum(1 for value in contacts.values() if value)


def _has_opposed_contacts(contacts: dict[str, bool]) -> bool:
    return (contacts.get("top") and contacts.get("bottom")) or (
        contacts.get("left") and contacts.get("right")
    )


def _has_adjacent_contacts(contacts: dict[str, bool]) -> bool:
    pairs = (("top", "left"), ("top", "right"), ("bottom", "left"), ("bottom", "right"))
    return any(contacts.get(a) and contacts.get(b) for a, b in pairs)


def _ambiguous_edge_contacts(contacts: dict[str, bool]) -> bool:
    vertical = contacts.get("top") and contacts.get("bottom")
    horizontal = contacts.get("left") and contacts.get("right")
    adjacent = _has_adjacent_contacts(contacts)
    return bool((vertical and horizontal) or (adjacent and not vertical and not horizontal))


def _quadrants_are_varied(quadrants: dict[str, float]) -> bool:
    if not quadrants:
        return False
    values = list(quadrants.values())
    return max(values) - min(values) >= 0.25
