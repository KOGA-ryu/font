from __future__ import annotations

from PIL import Image

from .schema import CELL_SIZE


def scale_nearest(image: Image.Image, factor: int) -> Image.Image:
    width, height = image.size
    return image.resize((width * factor, height * factor), Image.Resampling.NEAREST)


def rotate_90(stamp: Image.Image) -> Image.Image:
    return _from_matrix(_rotate_90(_to_matrix(stamp)))


def rotate_180(stamp: Image.Image) -> Image.Image:
    return rotate_90(rotate_90(stamp))


def rotate_270(stamp: Image.Image) -> Image.Image:
    return rotate_90(rotate_180(stamp))


def flip_horizontal(stamp: Image.Image) -> Image.Image:
    matrix = _to_matrix(stamp)
    return _from_matrix([list(reversed(row)) for row in matrix])


def flip_vertical(stamp: Image.Image) -> Image.Image:
    matrix = _to_matrix(stamp)
    return _from_matrix(list(reversed(matrix)))


def shift(stamp: Image.Image, dx: int, dy: int) -> Image.Image:
    source = _to_matrix(stamp)
    empty = _empty_matrix()
    for y, row in enumerate(source):
        for x, pixel in enumerate(row):
            nx = x + dx
            ny = y + dy
            if pixel[3] > 0 and 0 <= nx < CELL_SIZE and 0 <= ny < CELL_SIZE:
                empty[ny][nx] = pixel
    return _from_matrix(empty)


def normalize_to_top_left(stamp: Image.Image) -> Image.Image:
    matrix = _to_matrix(stamp)
    occupied = [
        (x, y)
        for y, row in enumerate(matrix)
        for x, pixel in enumerate(row)
        if pixel[3] > 0
    ]
    if not occupied:
        return _from_matrix(matrix)
    min_x = min(x for x, _ in occupied)
    min_y = min(y for _, y in occupied)
    return shift(stamp, -min_x, -min_y)


def stamp_to_bitmask(stamp: Image.Image) -> int:
    rgba = stamp.convert("RGBA")
    if rgba.size != (CELL_SIZE, CELL_SIZE):
        raise ValueError(f"expected {CELL_SIZE}x{CELL_SIZE} stamp, got {rgba.size}")
    pixels = rgba.load()
    bitmask = 0
    for y in range(CELL_SIZE):
        for x in range(CELL_SIZE):
            if pixels[x, y][3] > 0:
                bitmask |= 1 << (y * CELL_SIZE + x)
    return bitmask


def bitmask_to_stamp(
    bitmask: int,
    color: tuple[int, int, int, int] = (34, 32, 29, 255),
) -> Image.Image:
    stamp = Image.new("RGBA", (CELL_SIZE, CELL_SIZE), (0, 0, 0, 0))
    pixels = stamp.load()
    for y in range(CELL_SIZE):
        for x in range(CELL_SIZE):
            if bitmask & (1 << (y * CELL_SIZE + x)):
                pixels[x, y] = color
    return stamp


def _rotate_90(matrix: list[list[tuple[int, int, int, int]]]) -> list[list[tuple[int, int, int, int]]]:
    return [[matrix[CELL_SIZE - 1 - x][y] for x in range(CELL_SIZE)] for y in range(CELL_SIZE)]


def _to_matrix(stamp: Image.Image) -> list[list[tuple[int, int, int, int]]]:
    rgba = stamp.convert("RGBA")
    if rgba.size != (CELL_SIZE, CELL_SIZE):
        raise ValueError(f"expected {CELL_SIZE}x{CELL_SIZE} stamp, got {rgba.size}")
    pixels = rgba.load()
    return [[pixels[x, y] for x in range(CELL_SIZE)] for y in range(CELL_SIZE)]


def _from_matrix(matrix: list[list[tuple[int, int, int, int]]]) -> Image.Image:
    stamp = Image.new("RGBA", (CELL_SIZE, CELL_SIZE), (0, 0, 0, 0))
    pixels = stamp.load()
    for y, row in enumerate(matrix):
        for x, pixel in enumerate(row):
            pixels[x, y] = pixel
    return stamp


def _empty_matrix() -> list[list[tuple[int, int, int, int]]]:
    return [[(0, 0, 0, 0) for _ in range(CELL_SIZE)] for _ in range(CELL_SIZE)]
