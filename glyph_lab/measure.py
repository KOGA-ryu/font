from __future__ import annotations

from collections import deque
from typing import Iterable

from PIL import Image


def occupied_matrix(image: Image.Image) -> list[list[bool]]:
    rgba = image.convert("RGBA")
    width, height = rgba.size
    pixels = rgba.load()
    return [[pixels[x, y][3] > 0 for x in range(width)] for y in range(height)]


def measure_stamp(image: Image.Image) -> dict:
    matrix = occupied_matrix(image)
    return measure_matrix(matrix)


def measure_matrix(matrix: list[list[bool]]) -> dict:
    height = len(matrix)
    width = len(matrix[0]) if height else 0
    points = [(x, y) for y, row in enumerate(matrix) for x, occupied in enumerate(row) if occupied]
    occupied = len(points)
    total = width * height if width and height else 1

    if points:
        xs = [x for x, _ in points]
        ys = [y for _, y in points]
        bbox = {"left": min(xs), "top": min(ys), "right": max(xs), "bottom": max(ys)}
        centroid_x = sum(xs) / occupied
        centroid_y = sum(ys) / occupied
    else:
        bbox = None
        centroid_x = None
        centroid_y = None

    return {
        "density": occupied / total,
        "bounding_box": bbox,
        "centroid_x": centroid_x,
        "centroid_y": centroid_y,
        "quadrant_densities": _quadrant_densities(matrix),
        "edge_contacts": {
            "top": any(matrix[0]) if height else False,
            "right": any(row[-1] for row in matrix) if width else False,
            "bottom": any(matrix[-1]) if height else False,
            "left": any(row[0] for row in matrix) if width else False,
        },
        "connected_component_count": _component_count(matrix),
        "symmetry": {
            "horizontal": matrix == list(reversed(matrix)),
            "vertical": all(row == list(reversed(row)) for row in matrix),
            "diagonal_a": _diagonal_a(matrix),
            "diagonal_b": _diagonal_b(matrix),
        },
    }


def _quadrant_densities(matrix: list[list[bool]]) -> dict[str, float]:
    height = len(matrix)
    width = len(matrix[0]) if height else 0
    mid_x = width // 2
    mid_y = height // 2
    return {
        "top_left": _density(_cells(matrix, 0, mid_x, 0, mid_y)),
        "top_right": _density(_cells(matrix, mid_x, width, 0, mid_y)),
        "bottom_left": _density(_cells(matrix, 0, mid_x, mid_y, height)),
        "bottom_right": _density(_cells(matrix, mid_x, width, mid_y, height)),
    }


def _cells(
    matrix: list[list[bool]], left: int, right: int, top: int, bottom: int
) -> Iterable[bool]:
    for y in range(top, bottom):
        for x in range(left, right):
            yield matrix[y][x]


def _density(cells: Iterable[bool]) -> float:
    values = list(cells)
    return sum(1 for value in values if value) / len(values) if values else 0.0


def _component_count(matrix: list[list[bool]]) -> int:
    height = len(matrix)
    width = len(matrix[0]) if height else 0
    seen: set[tuple[int, int]] = set()
    count = 0
    for y in range(height):
        for x in range(width):
            if not matrix[y][x] or (x, y) in seen:
                continue
            count += 1
            queue: deque[tuple[int, int]] = deque([(x, y)])
            seen.add((x, y))
            while queue:
                cx, cy = queue.popleft()
                for nx, ny in ((cx - 1, cy), (cx + 1, cy), (cx, cy - 1), (cx, cy + 1)):
                    if 0 <= nx < width and 0 <= ny < height and matrix[ny][nx] and (nx, ny) not in seen:
                        seen.add((nx, ny))
                        queue.append((nx, ny))
    return count


def _diagonal_a(matrix: list[list[bool]]) -> bool:
    height = len(matrix)
    width = len(matrix[0]) if height else 0
    return height == width and all(matrix[y][x] == matrix[x][y] for y in range(height) for x in range(width))


def _diagonal_b(matrix: list[list[bool]]) -> bool:
    height = len(matrix)
    width = len(matrix[0]) if height else 0
    return height == width and all(
        matrix[y][x] == matrix[height - 1 - x][width - 1 - y]
        for y in range(height)
        for x in range(width)
    )
