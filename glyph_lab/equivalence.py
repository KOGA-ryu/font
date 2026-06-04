from __future__ import annotations

from collections.abc import Iterable
from typing import Callable

from PIL import Image

from .transforms import (
    flip_horizontal,
    flip_vertical,
    normalize_to_top_left,
    rotate_90,
    rotate_180,
    rotate_270,
    stamp_to_bitmask,
)


Transform = Callable[[Image.Image], Image.Image]
NamedTransform = tuple[str, Transform]


def canonical_bitmask(
    stamp: Image.Image,
    transforms: str | Iterable[NamedTransform] = "exact",
) -> tuple[int, str]:
    candidates = []
    for name, transform in _resolve_transforms(transforms):
        transformed = transform(stamp)
        candidates.append((stamp_to_bitmask(transformed), name))
    if not candidates:
        raise ValueError("canonical_bitmask requires at least one transform")
    return min(candidates, key=lambda candidate: (candidate[0], candidate[1]))


def transform_group(name: str) -> list[NamedTransform]:
    groups: dict[str, list[NamedTransform]] = {
        "exact": [("identity", lambda stamp: stamp.copy())],
        "rotations": [
            ("identity", lambda stamp: stamp.copy()),
            ("rotate_90", rotate_90),
            ("rotate_180", rotate_180),
            ("rotate_270", rotate_270),
        ],
        "mirrors": [
            ("identity", lambda stamp: stamp.copy()),
            ("flip_horizontal", flip_horizontal),
            ("flip_vertical", flip_vertical),
        ],
        "dihedral8": [
            ("identity", lambda stamp: stamp.copy()),
            ("rotate_90", rotate_90),
            ("rotate_180", rotate_180),
            ("rotate_270", rotate_270),
            ("flip_horizontal", flip_horizontal),
            ("flip_horizontal.rotate_90", lambda stamp: rotate_90(flip_horizontal(stamp))),
            ("flip_horizontal.rotate_180", lambda stamp: rotate_180(flip_horizontal(stamp))),
            ("flip_horizontal.rotate_270", lambda stamp: rotate_270(flip_horizontal(stamp))),
        ],
        "translations_normalized": [
            ("normalize_to_top_left", normalize_to_top_left),
        ],
    }
    if name not in groups:
        raise ValueError(f"unknown transform group {name!r}")
    return groups[name]


def _resolve_transforms(transforms: str | Iterable[NamedTransform]) -> list[NamedTransform]:
    if isinstance(transforms, str):
        return transform_group(transforms)
    return list(transforms)
