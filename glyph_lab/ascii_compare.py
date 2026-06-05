from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any
import json

from .ascii_promotion import write_ascii_promotion_request


def compare_ascii_fallbacks(
    before_manifest_path: str | Path,
    after_manifest_path: str | Path,
    output_dir: str | Path,
    mapping_path: str | Path | None = None,
    accepted_path: str | Path | None = None,
    limit: int | None = None,
    base_glyphs_path: str | Path | None = None,
) -> dict[str, Any]:
    before_path = Path(before_manifest_path)
    after_path = Path(after_manifest_path)
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    before = _load_json(before_path)
    after = _load_json(after_path)
    report = fallback_comparison(before, after)
    report["input_paths"] = {
        "before_manifest": str(before_path),
        "after_manifest": str(after_path),
        "mapping": str(mapping_path) if mapping_path is not None else None,
        "accepted": str(accepted_path) if accepted_path is not None else None,
        "base_glyphs": str(base_glyphs_path) if base_glyphs_path is not None else None,
    }

    next_request_path = None
    if mapping_path is not None and accepted_path is not None:
        next_request_path = out / "next_promote_candidates.json"
        next_request = write_ascii_promotion_request(
            after_path,
            mapping_path,
            accepted_path,
            next_request_path,
            limit=limit,
            base_glyphs_path=base_glyphs_path,
        )
        report["next_promotion_request"] = {
            "path": str(next_request_path),
            "promote_count": len(next_request.get("promote", [])),
            "limit": limit,
        }
    else:
        report["next_promotion_request"] = None

    _write_json(out / "fallback_compare.json", report)
    return report


def fallback_comparison(before_manifest: dict[str, Any], after_manifest: dict[str, Any]) -> dict[str, Any]:
    before_counts = _fallback_counts(before_manifest)
    after_counts = _fallback_counts(after_manifest)
    before_total = sum(before_counts.values())
    after_total = sum(after_counts.values())
    all_chars = sorted(set(before_counts) | set(after_counts))
    char_deltas = [
        {
            "char": char,
            "before": before_counts.get(char, 0),
            "after": after_counts.get(char, 0),
            "reduction": before_counts.get(char, 0) - after_counts.get(char, 0),
        }
        for char in all_chars
    ]
    fixed = [item for item in char_deltas if item["before"] > 0 and item["after"] == 0]
    improved = [item for item in char_deltas if item["reduction"] > 0]
    worsened = [item for item in char_deltas if item["reduction"] < 0]
    reduction = before_total - after_total
    ratio = (reduction / before_total) if before_total else 0.0

    return {
        "before_fallback_total": before_total,
        "after_fallback_total": after_total,
        "fallback_reduction": reduction,
        "fallback_reduction_ratio": round(ratio, 4),
        "before_unmapped_total": _warning_count(before_manifest, "unmapped-ascii-char"),
        "after_unmapped_total": _warning_count(after_manifest, "unmapped-ascii-char"),
        "fixed_chars": sorted(fixed, key=lambda item: (-item["before"], item["char"])),
        "improved_chars": sorted(improved, key=lambda item: (-item["reduction"], item["char"])),
        "worsened_chars": sorted(worsened, key=lambda item: (item["reduction"], item["char"])),
        "top_remaining_fallbacks": [
            {"char": char, "count": count}
            for char, count in after_counts.most_common()
        ],
        "before_fallback_counts": dict(before_counts.most_common()),
        "after_fallback_counts": dict(after_counts.most_common()),
    }


def _fallback_counts(manifest: dict[str, Any]) -> Counter[str]:
    return Counter(
        warning.get("char", "")
        for warning in manifest.get("ascii_bridge", {}).get("warnings", [])
        if warning.get("type") == "bridge-fallback"
    )


def _warning_count(manifest: dict[str, Any], warning_type: str) -> int:
    return sum(
        1
        for warning in manifest.get("ascii_bridge", {}).get("warnings", [])
        if warning.get("type") == warning_type
    )


def _load_json(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _write_json(path: str | Path, payload: dict[str, Any]) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with Path(path).open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
        handle.write("\n")
