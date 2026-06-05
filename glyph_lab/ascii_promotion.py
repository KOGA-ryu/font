from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any
import json


def promotion_request_from_ascii_manifest(
    manifest: dict[str, Any],
    mapping: dict[str, Any],
    accepted_candidates: list[dict[str, Any]],
    limit: int | None = None,
) -> dict[str, Any]:
    accepted_ids = {candidate["id"] for candidate in accepted_candidates}
    bridge_mapping = mapping.get("mapping", mapping)
    fallback_counts = Counter(
        warning["char"]
        for warning in manifest.get("ascii_bridge", {}).get("warnings", [])
        if warning.get("type") == "bridge-fallback"
    )
    promote = []
    skipped = []
    for char, count in fallback_counts.most_common():
        if limit is not None and len(promote) >= limit:
            break
        entry = bridge_mapping.get(char)
        if entry is None:
            skipped.append({"char": char, "count": count, "reason": "missing-mapping-entry"})
            continue
        candidate_id = entry.get("glyph_id")
        if candidate_id not in accepted_ids:
            skipped.append({"char": char, "count": count, "candidate_id": candidate_id, "reason": "candidate-not-accepted"})
            continue
        if len(char) != 1 or char == " ":
            skipped.append({"char": char, "count": count, "candidate_id": candidate_id, "reason": "invalid-token"})
            continue
        promote.append(
            {
                "candidate_id": candidate_id,
                "token": char,
                "notes": f"Promote linework bridge key {char!r}; used {count} times as ASCII bridge fallback.",
            }
        )
    return {
        "promote": promote,
        "metadata": {
            "source": "ascii_bridge_fallback_warnings",
            "fallback_counts": dict(fallback_counts.most_common()),
            "skipped": skipped,
        },
    }


def write_ascii_promotion_request(
    manifest_path: str | Path,
    mapping_path: str | Path,
    accepted_path: str | Path,
    output_path: str | Path,
    limit: int | None = None,
) -> dict[str, Any]:
    manifest = _load_json(manifest_path)
    mapping = _load_json(mapping_path)
    accepted_payload = _load_json(accepted_path)
    accepted = accepted_payload.get("accepted_candidates", accepted_payload)
    request = promotion_request_from_ascii_manifest(manifest, mapping, accepted, limit=limit)
    _write_json(output_path, request)
    return request


def _load_json(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _write_json(path: str | Path, payload: dict[str, Any]) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with Path(path).open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
        handle.write("\n")
